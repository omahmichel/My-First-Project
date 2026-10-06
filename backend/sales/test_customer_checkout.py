from decimal import Decimal
from datetime import timedelta
from unittest.mock import Mock, patch
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from businesses.paystack_client import PaystackClient, PaystackRequestError
from . import test_mobile_money_service as fixtures
from .mobile_money_service import initialize_mobile_money_sale, verify_and_finalize_mobile_money_sale, MobileMoneyPaymentError
from .mobile_money_auth import advance_sale_charge
from .models import Payment, Sale, MerchantPayout
from .serializers import SaleSerializer

@override_settings(MNOTIFY_API_KEY="", PAYMENT_GATEWAY="paystack", PAYMENT_GATEWAY_SECRET_KEY="sk_test_stockflow", MOBILE_MONEY_RESERVATION_MINUTES=5)
class CustomerCheckoutTests(TestCase):
    setUp = fixtures.MobileMoneySaleInitializationTests.setUp
    payload = fixtures.MobileMoneySaleInitializationTests.payload
    verification_client = fixtures.MobileMoneySaleInitializationTests.verification_client

    def gateway(self):
        c=Mock(); c.secret_key="sk_test_stockflow"
        c.initialize_transaction.side_effect=lambda **kw: {"reference":kw["reference"],"access_code":"private-access-code","authorization_url":"https://checkout.paystack.com/customer-example"}
        return c

    def start(self, client=None):
        self.gateway_client=client or self.gateway()
        self.sale,self.payment,_=initialize_mobile_money_sale(business=self.business,user=self.owner,data=self.payload(),idempotency_key="hosted-one",client=self.gateway_client,hosted_checkout=True)
        return self.gateway_client

    def test_checkout_has_full_amount_momo_only_and_no_phone_charge(self):
        c=self.start(); args=c.initialize_transaction.call_args.kwargs
        self.assertEqual(args["amount_subunit"],15195)
        self.assertEqual(args["channels"],["mobile_money"])
        self.assertEqual(args["reference"],self.payment.gateway_reference)
        c.create_mobile_money_charge.assert_not_called()
        self.assertEqual(self.payment.checkout_url,"https://checkout.paystack.com/customer-example")
        self.assertEqual(self.sale.status,"pending_payment")
        self.assertFalse(MerchantPayout.objects.exists())
        self.product.refresh_from_db(); self.assertEqual(self.product.stock,10)
        self.assertNotIn("checkoutUrl",SaleSerializer(self.sale).data["payments"][0])

    def test_duplicate_initialization_reuses_link(self):
        c=self.start()
        sale,p,replayed=initialize_mobile_money_sale(business=self.business,user=self.owner,data=self.payload(),idempotency_key="hosted-one",client=c,hosted_checkout=True)
        self.assertTrue(replayed); self.assertEqual(p.checkout_url,self.payment.checkout_url)
        self.assertEqual(c.initialize_transaction.call_count,1)

    def test_unsafe_or_mismatched_checkout_rejected(self):
        for url,reference in [("https://evil.example/pay",None),("javascript:alert(1)",None),("https://checkout.paystack.com/x","wrong")]:
            with self.subTest(url=url,reference=reference):
                c=self.gateway()
                c.initialize_transaction.side_effect=lambda **kw: {"reference":reference or kw["reference"],"access_code":"abc","authorization_url":url}
                with self.assertRaises(PaystackRequestError):
                    initialize_mobile_money_sale(business=self.business,user=self.owner,data=self.payload(),idempotency_key=url+str(reference),client=c,hosted_checkout=True)
        self.assertFalse(Payment.objects.exclude(checkout_url="").exists())

    def test_success_verified_once_without_otp(self):
        self.start(); c=self.verification_client(payment=self.payment)
        sale=advance_sale_charge(reference=self.payment.gateway_reference,client=c)
        self.assertEqual(sale.status,"completed")
        advance_sale_charge(reference=self.payment.gateway_reference,client=c)
        self.assertEqual(c.verify_transaction.call_count,1)
        c.check_pending_charge.assert_not_called(); c.submit_charge_otp.assert_not_called()
        self.assertEqual(MerchantPayout.objects.count(),1)
        self.assertEqual(MerchantPayout.objects.get().amount,Decimal("150.00"))

    def test_pending_and_unopened_checkout_do_not_release_stock(self):
        self.start(); c=self.verification_client(payment=self.payment)
        for status in ("pending","ongoing","abandoned"):
            c.verify_transaction.return_value["status"]=status
            sale=advance_sale_charge(reference=self.payment.gateway_reference,client=c)
            self.assertEqual(sale.status,"pending_payment")
        self.product.refresh_from_db(); self.assertEqual(self.product.reserved_stock,1)
        self.assertFalse(MerchantPayout.objects.exists())

    def test_abandoned_checkout_released_after_expiry(self):
        self.start(); c=self.verification_client(payment=self.payment)
        c.verify_transaction.return_value["status"]="abandoned"
        Sale.objects.filter(pk=self.sale.pk).update(reservation_expires_at=timezone.now()-timedelta(seconds=1))
        sale=advance_sale_charge(reference=self.payment.gateway_reference,client=c)
        self.assertEqual(sale.status,"cancelled")

    def test_mismatched_verified_amount_rejected(self):
        self.start(); c=self.verification_client(payment=self.payment)
        c.verify_transaction.return_value["amount"]=1
        with self.assertRaises(MobileMoneyPaymentError): advance_sale_charge(reference=self.payment.gateway_reference,client=c)
        self.assertFalse(MerchantPayout.objects.exists())

    def test_owner_api_rejects_otp_and_pin_without_gateway_calls(self):
        from django.core.cache import cache
        cache.clear(); self.start(); api=APIClient();api.force_authenticate(self.owner)
        url=f"/api/businesses/{self.business.pk}/sales/mobile-money/{self.payment.gateway_reference}/authenticate/"
        with patch("sales.mobile_money_auth.PaystackClient") as c:
            for body in ({"otp":"123456"},{"pin":"1234"}):
                response=api.post(url,body,format="json")
                self.assertEqual(response.status_code,400,response.data)
            c.assert_not_called()

    def test_channel_parameter_does_not_change_subscription_defaults(self):
        c=PaystackClient();c._request=Mock(return_value={"authorization_url":"https://checkout.paystack.com/x","access_code":"x","reference":"r"})
        c.initialize_transaction(email="a@example.com",amount_subunit=200,reference="r")
        self.assertNotIn("channels",c._request.call_args.kwargs["json"])
        c.initialize_transaction(email="a@example.com",amount_subunit=200,reference="r",channels=["mobile_money"])
        self.assertEqual(c._request.call_args.kwargs["json"]["channels"],["mobile_money"])

    def test_late_payment_recorded_for_review_without_stock_or_payout(self):
        self.start(); c=self.verification_client(payment=self.payment)
        c.verify_transaction.return_value["status"]="abandoned"
        Sale.objects.filter(pk=self.sale.pk).update(reservation_expires_at=timezone.now()-timedelta(seconds=1))
        advance_sale_charge(reference=self.payment.gateway_reference,client=c)
        c.verify_transaction.return_value["status"]="success"
        for _ in range(2):
            sale=advance_sale_charge(reference=self.payment.gateway_reference,client=c)
            self.assertEqual(sale.status,"cancelled")
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.gateway_charge_status,"requires_review")
        self.assertEqual(self.payment.status,"successful")
        self.product.refresh_from_db(); self.assertEqual(self.product.stock,10)
        self.assertFalse(MerchantPayout.objects.exists())
