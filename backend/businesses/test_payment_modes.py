from unittest.mock import Mock
from django.test import TestCase, override_settings
from .payment_modes import gateway_mode, require_mode, require_response_mode
from .paystack_client import PaystackConfigurationError
from .models import BusinessPaymentAccount
from . import test_subscription_service as subscription_fixtures
from .subscription_service import verify_and_fulfill_subscription_payment

@override_settings(PAYMENT_GATEWAY_SECRET_KEY='sk_test_isolated', PAYMENT_GATEWAY='paystack')
class PaymentModeTests(TestCase):
    setUp = subscription_fixtures.SubscriptionPaymentServiceTests.setUp
    initialize_payment = subscription_fixtures.SubscriptionPaymentServiceTests.initialize_payment
    mock_manager_create = subscription_fixtures.SubscriptionPaymentServiceTests.mock_manager_create
    successful_verification = subscription_fixtures.SubscriptionPaymentServiceTests.successful_verification

    def test_subscription_records_mode(self):
        payment = self.initialize_payment()
        self.assertEqual(payment.gateway_mode, 'test')

    def test_test_subscription_blocked_before_live_network_call(self):
        payment = self.initialize_payment()
        with override_settings(PAYMENT_GATEWAY_SECRET_KEY='sk_live_isolated'):
            with self.assertRaises(PaystackConfigurationError):
                verify_and_fulfill_subscription_payment(reference=payment.reference,client=self.client)
        self.client.verify_transaction.assert_not_called()

    def test_unknown_subscription_cannot_be_verified_live(self):
        payment = self.initialize_payment()
        payment.gateway_mode='';payment.save()
        with override_settings(PAYMENT_GATEWAY_SECRET_KEY='sk_live_isolated'):
            with self.assertRaises(PaystackConfigurationError):
                verify_and_fulfill_subscription_payment(reference=payment.reference,client=self.client)
        self.client.verify_transaction.assert_not_called()

    def test_mismatching_response_cannot_grant_subscription(self):
        payment = self.initialize_payment()
        self.client.verify_transaction.return_value=self.successful_verification(payment,domain='live')
        with self.assertRaises(PaystackConfigurationError):
            verify_and_fulfill_subscription_payment(reference=payment.reference,client=self.client)
        payment.refresh_from_db();self.assertFalse(payment.is_fulfilled)

    def test_missing_response_domain_is_rejected(self):
        with self.assertRaises(PaystackConfigurationError):require_response_mode({},'live')

    def test_unknown_key_is_rejected(self):
        with override_settings(PAYMENT_GATEWAY_SECRET_KEY=''):
            with self.assertRaises(PaystackConfigurationError):gateway_mode()

    def test_recipient_ready_only_in_matching_mode(self):
        a=BusinessPaymentAccount(account_type='mobile_money',is_active=True,paystack_recipient_code='RCP_test',paystack_recipient_mode='test')
        self.assertTrue(a.payout_ready)
        with override_settings(PAYMENT_GATEWAY_SECRET_KEY='sk_live_isolated'):
            self.assertFalse(a.payout_ready)
            self.assertEqual(a.payout_status,'pending')
        a.clear_paystack_recipient();self.assertEqual(a.paystack_recipient_mode,'')
