"""Direct phone requests must never create a second checkout or collect owner OTPs."""
from unittest.mock import Mock, patch
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from .test_customer_checkout import CustomerCheckoutTests
from .models import Payment, Sale, MerchantPayout

@override_settings(MNOTIFY_API_KEY="", PAYMENT_GATEWAY="paystack", PAYMENT_GATEWAY_SECRET_KEY="sk_test_stockflow", MOBILE_MONEY_RESERVATION_MINUTES=5)
class DirectPromptTests(TestCase):
    setUp = CustomerCheckoutTests.setUp
    payload = CustomerCheckoutTests.payload
    verification_client = CustomerCheckoutTests.verification_client

    def prepare(self, provider_status="pay_offline"):
        cache.clear()
        self.api=APIClient();self.api.force_authenticate(self.owner)
        self.data=self.payload()
        self.data.update(customerId=str(self.customer.pk))
        self.data["items"][0]["productId"]=str(self.product.pk)
        self.gateway=Mock();self.gateway.secret_key="sk_test_stockflow"
        self.gateway.create_mobile_money_charge.side_effect=lambda **kw: {"reference":kw["reference"],"status":provider_status,"display_text":"Enter OTP here" if provider_status=="send_otp" else "Approve on your phone"}
        self.url=f"/api/businesses/{self.business.pk}/sales/"

    def create(self):
        with patch("sales.mobile_money_service.PaystackClient",return_value=self.gateway):
            r=self.api.post(self.url,self.data,format="json",HTTP_IDEMPOTENCY_KEY="direct-one")
        self.assertEqual(r.status_code,201,r.data)
        self.payment=Payment.objects.get()
        return r

    def test_direct_phone_number_full_fee_amount_no_sms_or_link_and_replay(self):
        self.prepare();self.create()
        args=self.gateway.create_mobile_money_charge.call_args.kwargs
        self.assertEqual(args["amount_subunit"],15195)
        self.assertEqual(args["provider"],"mtn")
        self.assertEqual(args["phone"],self.payment.mobile_money_number)
        self.assertEqual(self.payment.checkout_url,"")
        self.gateway.initialize_transaction.assert_not_called()
        self.product.refresh_from_db();self.assertEqual(self.product.stock,10)
        self.assertEqual(self.product.reserved_stock,1)
        self.assertFalse(MerchantPayout.objects.exists())
        self.data["mobileMoneyFlow"]="hosted"
        with patch("sales.mobile_money_service.PaystackClient") as gateway:
            r=self.api.post(self.url,self.data,format="json",HTTP_IDEMPOTENCY_KEY="direct-one")
            self.assertEqual(r.status_code,200,r.data)
            gateway.assert_not_called()
        self.assertEqual(Payment.objects.count(),1)

    def test_otp_response_does_not_start_another_charge_and_owner_cannot_submit(self):
        self.prepare("send_otp");self.create()
        self.assertIn("Do not ask",self.payment.note)
        self.assertNotIn("Enter OTP here",self.payment.note)
        self.gateway.initialize_transaction.assert_not_called()
        url=self.url+f"mobile-money/{self.payment.gateway_reference}/authenticate/"
        with patch("sales.mobile_money_auth.PaystackClient") as gateway:
            for data in ({"otp":"123456"},{"pin":"1234"}):
                r=self.api.post(url,data,format="json")
                self.assertEqual(r.status_code,400,r.data)
            gateway.assert_not_called()
        self.gateway.check_pending_charge.return_value={"status":"send_otp","display_text":"Give code to merchant"}
        with patch("sales.mobile_money_auth.PaystackClient",return_value=self.gateway):
            r=self.api.post(url,{},format="json")
        self.assertEqual(r.status_code,200,r.data)
        self.payment.refresh_from_db();self.assertIn("Do not ask",self.payment.note)
        self.gateway.submit_charge_otp.assert_not_called()
        self.assertEqual(Payment.objects.count(),1)

    def test_verified_direct_success_completes_once(self):
        self.prepare();self.create()
        gateway=self.verification_client(payment=self.payment)
        gateway.check_pending_charge.return_value={"status":"success"}
        url=self.url+f"mobile-money/{self.payment.gateway_reference}/authenticate/"
        with patch("sales.mobile_money_auth.PaystackClient",return_value=gateway):
            for _ in range(2):
                r=self.api.post(url,{},format="json")
                self.assertEqual(r.status_code,200,r.data)
                self.assertEqual(r.data["status"],"completed")
        self.product.refresh_from_db();self.assertEqual(self.product.stock,9)
        self.assertEqual(MerchantPayout.objects.count(),1)
        gateway.verify_transaction.assert_called_once()

    def test_invalid_flow_rejected_before_payment(self):
        self.prepare();self.data["mobileMoneyFlow"]="hosted"
        with patch("sales.mobile_money_service.PaystackClient") as gateway:
            r=self.api.post(self.url,self.data,format="json",HTTP_IDEMPOTENCY_KEY="bad-flow")
            self.assertEqual(r.status_code,400,r.data);gateway.assert_not_called()
        self.assertFalse(Payment.objects.exists())

    def test_removed_sms_action_is_rejected_and_links_not_exposed(self):
        self.prepare();r=self.create()
        self.assertNotIn("checkoutUrl",r.data["payments"][0])
        self.assertNotIn("checkoutSms",r.data["payments"][0])
        url=self.url+f"mobile-money/{self.payment.gateway_reference}/authenticate/"
        with patch("sales.mobile_money_auth.PaystackClient") as gateway:
            r=self.api.post(url,{"resendSms":True},format="json")
            self.assertEqual(r.status_code,400,r.data)
            gateway.assert_not_called()
