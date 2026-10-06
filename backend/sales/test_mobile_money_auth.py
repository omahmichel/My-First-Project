from datetime import timedelta
from unittest.mock import Mock, patch
from django.test import TestCase, override_settings
from django.utils import timezone
from django.core.cache import cache
from rest_framework.test import APIClient
from businesses.paystack_client import PaystackConfigurationError, PaystackRequestError, PaystackClient
from . import test_mobile_money_service as fixtures
from .models import Payment, Sale, MerchantPayout
from .mobile_money_service import initialize_mobile_money_sale, MobileMoneyPaymentError
from .mobile_money_auth import advance_sale_charge

@override_settings(PAYMENT_GATEWAY="paystack", PAYMENT_GATEWAY_SECRET_KEY="sk_test_stockflow", MOBILE_MONEY_RESERVATION_MINUTES=5)
class ChargeAuthenticationTests(TestCase):
    setUp = fixtures.MobileMoneySaleInitializationTests.setUp
    payload = fixtures.MobileMoneySaleInitializationTests.payload
    successful_client = fixtures.MobileMoneySaleInitializationTests.successful_client
    verification_client = fixtures.MobileMoneySaleInitializationTests.verification_client

    def start(self):
        cache.clear()
        client = self.successful_client()
        client.create_mobile_money_charge.side_effect = lambda **kw: {"reference": kw["reference"], "status": "send_otp", "display_text": "Enter payment code."}
        self.sale, self.payment, _ = initialize_mobile_money_sale(business=self.business, user=self.owner, data=self.payload(), idempotency_key="otp-sale", client=client)
        self.client_gateway = self.verification_client(payment=self.payment)
        self.client_gateway.check_pending_charge.return_value = {"status": "send_otp", "reference": self.payment.gateway_reference}
        return self.client_gateway

    def run_action(self, **kw):
        return advance_sale_charge(reference=self.payment.gateway_reference, client=self.client_gateway, **kw)

    def test_initial_otp_action_persisted_without_fulfillment(self):
        self.start()
        self.assertEqual(self.payment.gateway_charge_status, "send_otp")
        self.assertEqual(self.sale.status, "pending_payment")
        self.assertFalse(MerchantPayout.objects.exists())

    def test_check_recovers_otp_after_refresh(self):
        self.start(); self.run_action()
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.gateway_charge_status, "send_otp")
        self.client_gateway.submit_charge_otp.assert_not_called()

    def test_otp_success_requires_verification_and_is_idempotent(self):
        c = self.start(); c.submit_charge_otp.return_value = {"status": "success"}
        sale = self.run_action(otp="123456")
        self.assertEqual(sale.status, "completed")
        self.run_action(otp="123456")
        self.assertEqual(c.submit_charge_otp.call_count, 1)
        self.assertEqual(MerchantPayout.objects.count(), 1)
        self.payment.refresh_from_db()
        self.assertNotIn("123456", self.payment.note)
        self.assertNotIn("123456", self.payment.failure_reason)

    def test_wrong_amount_cannot_complete(self):
        c=self.start(); c.submit_charge_otp.return_value={"status":"success"}
        c.verify_transaction.return_value["amount"]=1
        with self.assertRaises(MobileMoneyPaymentError): self.run_action(otp="123456")
        self.sale.refresh_from_db(); self.assertNotEqual(self.sale.status,"completed")
        self.assertFalse(MerchantPayout.objects.exists())

    def test_wrong_mode_blocked_before_otp(self):
        c=self.start(); c.secret_key="sk_live_example"
        with self.assertRaises(PaystackConfigurationError): self.run_action(otp="123456")
        c.check_pending_charge.assert_not_called(); c.submit_charge_otp.assert_not_called()

    def test_wrong_response_reference_blocked(self):
        c=self.start(); c.check_pending_charge.return_value["reference"]="another-payment"
        with self.assertRaises(PaystackRequestError): self.run_action()
        c.submit_charge_otp.assert_not_called()

    def test_wrong_response_domain_blocked(self):
        c=self.start(); c.check_pending_charge.return_value["domain"]="live"
        with self.assertRaises(PaystackConfigurationError): self.run_action()
        c.submit_charge_otp.assert_not_called()

    def test_pending_after_otp_does_not_finalize(self):
        c=self.start(); c.submit_charge_otp.return_value={"status":"pay_offline", "display_text":"Approve on phone"}
        sale=self.run_action(otp="123456")
        self.assertEqual(sale.status,"pending_payment")
        self.payment.refresh_from_db(); self.assertEqual(self.payment.gateway_charge_status,"pay_offline")
        c.verify_transaction.assert_not_called()

    def test_invalid_code_not_submitted(self):
        c=self.start()
        with self.assertRaises(MobileMoneyPaymentError): self.run_action(otp="abc")
        c.submit_charge_otp.assert_not_called()

    def test_expired_code_not_submitted(self):
        c=self.start(); self.sale.reservation_expires_at=timezone.now()-timedelta(seconds=1); self.sale.save()
        with self.assertRaises(MobileMoneyPaymentError): self.run_action(otp="123456")
        c.submit_charge_otp.assert_not_called()

    def test_failed_charge_returns_cancelled_sale_and_releases_stock(self):
        c=self.start(); c.check_pending_charge.return_value={"status":"abandoned"}; c.verify_transaction.return_value["status"]="abandoned"
        sale=self.run_action()
        self.assertEqual(sale.status,"cancelled")
        self.product.refresh_from_db(); self.assertEqual(self.product.reserved_stock,0)
        self.assertFalse(MerchantPayout.objects.exists())

    def test_rejected_otp_keeps_pending_for_retry(self):
        c=self.start(); c.submit_charge_otp.side_effect=PaystackRequestError("Invalid payment code")
        with self.assertRaises(PaystackRequestError): self.run_action(otp="123456")
        self.payment.refresh_from_db(); self.assertEqual(self.payment.status,"pending")

    def test_api_returns_terminal_state(self):
        c=self.start(); c.check_pending_charge.return_value={"status":"abandoned"}; c.verify_transaction.return_value["status"]="abandoned"
        api=APIClient(); api.force_authenticate(self.owner)
        with patch("sales.mobile_money_auth.PaystackClient", return_value=c):
            response=api.post(f"/api/businesses/{self.business.id}/sales/mobile-money/{self.payment.gateway_reference}/authenticate/", {}, format="json")
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data["status"],"cancelled")

    def test_other_business_cannot_submit_code(self):
        c=self.start()
        from accounts.models import User
        other=User.objects.create_user(email="other@stockflow.test",password="abc",full_name="Other")
        api=APIClient(); api.force_authenticate(other)
        with patch("sales.mobile_money_auth.PaystackClient",return_value=c):
            response=api.post(f"/api/businesses/{self.business.id}/sales/mobile-money/{self.payment.gateway_reference}/authenticate/", {"otp":"123456"},format="json")
        self.assertIn(response.status_code,(403,404)); c.submit_charge_otp.assert_not_called()

    def test_api_unauthenticated_blocked(self):
        self.start(); api=APIClient()
        response=api.post(f"/api/businesses/{self.business.id}/sales/mobile-money/{self.payment.gateway_reference}/authenticate/",{},format="json")
        self.assertIn(response.status_code,(401,403))

    def test_gateway_otp_endpoint_uses_existing_reference(self):
        self.start(); client=PaystackClient(); client._request=Mock(return_value={"status":"pay_offline"})
        client.submit_charge_otp(reference="known-reference",otp="123456")
        client._request.assert_called_once_with("POST","/charge/submit_otp",json={"reference":"known-reference","otp":"123456"})

    def test_timeout_recheck_does_not_resubmit_when_provider_has_advanced(self):
        c=self.start(); c.submit_charge_otp.side_effect=PaystackRequestError("Paystack did not respond in time.")
        with self.assertRaises(PaystackRequestError): self.run_action(otp="123456")
        c.check_pending_charge.return_value={"status":"pay_offline"}
        self.run_action(otp="123456")
        self.assertEqual(c.submit_charge_otp.call_count,1)
        self.assertFalse(MerchantPayout.objects.exists())

    def test_api_rate_limits_code_attempts(self):
        c=self.start(); api=APIClient(); api.force_authenticate(self.owner)
        url=f"/api/businesses/{self.business.id}/sales/mobile-money/{self.payment.gateway_reference}/authenticate/"
        with patch("sales.mobile_money_auth.PaystackClient",return_value=c):
            for _ in range(6): self.assertEqual(api.post(url,{},format="json").status_code,200)
            self.assertEqual(api.post(url,{},format="json").status_code,429)

    def test_requested_otp_submitted_without_preliminary_status_check(self):
        c=self.start()
        c.check_pending_charge.return_value={"status":"failed"}
        c.submit_charge_otp.return_value={"status":"pay_offline"}
        sale=self.run_action(otp="123456")
        c.check_pending_charge.assert_not_called()
        c.submit_charge_otp.assert_called_once_with(reference=self.payment.gateway_reference, otp="123456")
        self.assertEqual(sale.status,"pending_payment")
        self.assertFalse(MerchantPayout.objects.exists())

    def test_concurrent_submission_and_poll_do_not_interrupt_otp(self):
        c=self.start()
        def submit(**kwargs):
            self.run_action(otp="123456")
            self.run_action()
            return {"status":"pay_offline"}
        c.submit_charge_otp.side_effect=submit
        self.run_action(otp="123456")
        self.assertEqual(c.submit_charge_otp.call_count,1)
        c.check_pending_charge.assert_not_called()

    def test_unknown_submission_requires_recovery_before_retry(self):
        c=self.start(); c.submit_charge_otp.side_effect=PaystackRequestError("Unknown response")
        with self.assertRaises(PaystackRequestError): self.run_action(otp="123456")
        self.payment.refresh_from_db(); self.assertEqual(self.payment.gateway_charge_status,"otp_unknown")
        self.run_action(otp="123456")
        self.assertEqual(c.submit_charge_otp.call_count,1)
        self.payment.refresh_from_db(); self.assertEqual(self.payment.gateway_charge_status,"send_otp")
        c.submit_charge_otp.side_effect=None; c.submit_charge_otp.return_value={"status":"pay_offline"}
        self.run_action(otp="234567")
        self.assertEqual(c.submit_charge_otp.call_count,2)

    def test_crashed_submission_lease_can_be_recovered(self):
        c=self.start()
        Payment.objects.filter(pk=self.payment.pk).update(gateway_charge_status="otp_submitting",updated_at=timezone.now()-timedelta(seconds=61))
        self.run_action()
        self.payment.refresh_from_db(); self.assertEqual(self.payment.gateway_charge_status,"send_otp")
        c.submit_charge_otp.assert_not_called()

    def test_otp_response_reference_and_domain_validated(self):
        c=self.start(); c.submit_charge_otp.return_value={"status":"success","reference":"wrong"}
        with self.assertRaises(PaystackRequestError): self.run_action(otp="123456")
        c.verify_transaction.assert_not_called()
        self.assertFalse(MerchantPayout.objects.exists())
        self.run_action()  # Recover the requested action.
        c.submit_charge_otp.return_value={"status":"success","domain":"live"}
        with self.assertRaises(PaystackConfigurationError): self.run_action(otp="123456")
        self.assertFalse(MerchantPayout.objects.exists())

    def test_late_poll_cannot_overwrite_concurrent_otp_result(self):
        c=self.start(); c.submit_charge_otp.return_value={"status":"pay_offline"}
        def poll(reference):
            self.run_action(otp="123456")
            return {"status":"send_otp"}
        c.check_pending_charge.side_effect=poll
        self.run_action()
        self.payment.refresh_from_db(); self.assertEqual(self.payment.gateway_charge_status,"pay_offline")
