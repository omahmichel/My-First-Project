from datetime import timedelta
from unittest.mock import Mock

from django.http import Http404
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from businesses.models import Business, SubscriptionPayment
from businesses.subscription_service import (
    SubscriptionPaymentError,
    initialize_subscription_payment,
    verify_and_fulfill_subscription_payment,
)


class SubscriptionPaymentServiceTests(TestCase):
    """Protects secure initialization and one-time subscription value."""

    def setUp(self):
        # Creates an owner, a non-owner and one expired business.
        self.owner = User.objects.create_user(
            email="service.owner@stockflow.test",
            password="StrongPass123!",
            full_name="Service Owner",
        )
        self.other_user = User.objects.create_user(
            email="service.other@stockflow.test",
            password="StrongPass123!",
            full_name="Other User",
        )
        self.business = Business.objects.create(
            owner=self.owner,
            name="Service Test Shop",
            slug="service-test-shop",
            business_type=Business.BusinessType.BOUTIQUE,
            trial_started_at=timezone.now() - timedelta(days=61),
            trial_ends_at=timezone.now() - timedelta(days=1),
        )
        self.client = Mock()

    def initialize_payment(self):
        # Creates one Paystack checkout attempt using a mocked client.
        self.client.initialize_transaction.return_value = {
            "authorization_url": (
                "https://checkout.paystack.com/service-test"
            ),
            "access_code": "service-test",
            "reference": "temporary",
        }

        original_create = SubscriptionPayment.objects.create

        def create_with_known_response(*args, **kwargs):
            payment = original_create(*args, **kwargs)
            self.client.initialize_transaction.return_value[
                "reference"
            ] = payment.reference
            return payment

        with self.mock_manager_create(create_with_known_response):
            return initialize_subscription_payment(
                user=self.owner,
                business_id=self.business.id,
                callback_url=(
                    "https://stockflow.test/subscription/callback"
                ),
                client=self.client,
            )

    def mock_manager_create(self, side_effect):
        # Patches only this model manager call for deterministic references.
        from unittest.mock import patch

        return patch.object(
            SubscriptionPayment.objects,
            "create",
            side_effect=side_effect,
        )

    def successful_verification(self, payment, **overrides):
        # Builds a verified Paystack response matching the payment record.
        response = {
            "id": 123456,
            "status": "success",
            "reference": payment.reference,
            "amount": payment.amount_subunit,
            "currency": payment.currency,
            "channel": "mobile_money",
            "paid_at": "2026-08-02T13:00:00.000Z",
        }
        response.update(overrides)
        return response

    def test_only_owner_can_initialize_subscription_payment(self):
        # Staff or unrelated users cannot pay for a business as its owner.
        with self.assertRaises(Http404):
            initialize_subscription_payment(
                user=self.other_user,
                business_id=self.business.id,
                client=self.client,
            )

        self.assertFalse(
            SubscriptionPayment.objects.exists()
        )
        self.client.initialize_transaction.assert_not_called()

    def test_initialize_uses_fixed_stockflow_terms(self):
        # The server sends ₵99, GHS and protected ownership metadata.
        payment = self.initialize_payment()

        self.assertEqual(
            payment.status,
            SubscriptionPayment.Status.PENDING,
        )
        self.assertTrue(payment.authorization_url)
        self.client.initialize_transaction.assert_called_once_with(
            email=self.owner.email,
            amount_subunit=9900,
            reference=payment.reference,
            currency="GHS",
            callback_url=(
                "https://stockflow.test/subscription/callback"
            ),
            metadata={
                "business_id": str(self.business.id),
                "subscription_payment_id": str(payment.id),
                "subscription_days": 40,
            },
        )

    def test_successful_verification_activates_exactly_40_days(self):
        # A matching successful transaction grants one paid period.
        payment = self.initialize_payment()
        self.client.verify_transaction.return_value = (
            self.successful_verification(payment)
        )

        before = timezone.now()
        verified, business, activated = (
            verify_and_fulfill_subscription_payment(
                reference=payment.reference,
                client=self.client,
            )
        )
        after = timezone.now()

        self.assertTrue(activated)
        self.assertEqual(
            verified.status,
            SubscriptionPayment.Status.SUCCESSFUL,
        )
        self.assertIsNotNone(verified.fulfilled_at)
        self.assertEqual(
            business.subscription_status,
            Business.SubscriptionStatus.ACTIVE,
        )
        self.assertGreaterEqual(
            business.subscription_ends_at,
            before + timedelta(days=40),
        )
        self.assertLessEqual(
            business.subscription_ends_at,
            after + timedelta(days=40),
        )

    def test_duplicate_verification_does_not_extend_twice(self):
        # Callback retries return the original fulfillment unchanged.
        payment = self.initialize_payment()
        self.client.verify_transaction.return_value = (
            self.successful_verification(payment)
        )

        first_payment, first_business, first_activated = (
            verify_and_fulfill_subscription_payment(
                reference=payment.reference,
                client=self.client,
            )
        )
        first_end = first_business.subscription_ends_at

        second_payment, second_business, second_activated = (
            verify_and_fulfill_subscription_payment(
                reference=payment.reference,
                client=self.client,
            )
        )

        self.assertTrue(first_activated)
        self.assertFalse(second_activated)
        self.assertEqual(
            first_payment.fulfilled_at,
            second_payment.fulfilled_at,
        )
        self.assertEqual(
            first_end,
            second_business.subscription_ends_at,
        )
        self.client.verify_transaction.assert_called_once_with(
            payment.reference
        )

    def test_renewal_extends_from_current_paid_expiry(self):
        # Early renewal preserves every already-paid remaining day.
        payment = self.initialize_payment()
        current_end = timezone.now() + timedelta(days=12)
        self.business.subscription_status = (
            Business.SubscriptionStatus.ACTIVE
        )
        self.business.subscription_started_at = timezone.now()
        self.business.subscription_ends_at = current_end
        self.business.save(
            update_fields=(
                "subscription_status",
                "subscription_started_at",
                "subscription_ends_at",
            )
        )
        self.client.verify_transaction.return_value = (
            self.successful_verification(payment)
        )

        _, business, activated = (
            verify_and_fulfill_subscription_payment(
                reference=payment.reference,
                client=self.client,
            )
        )

        self.assertTrue(activated)
        self.assertEqual(
            business.subscription_ends_at,
            current_end + timedelta(days=40),
        )

    def test_wrong_amount_is_rejected_without_access(self):
        # A successful status cannot hide an underpayment or overpayment.
        payment = self.initialize_payment()
        self.client.verify_transaction.return_value = (
            self.successful_verification(
                payment,
                amount=5000,
            )
        )

        with self.assertRaises(SubscriptionPaymentError) as context:
            verify_and_fulfill_subscription_payment(
                reference=payment.reference,
                client=self.client,
            )

        payment.refresh_from_db()
        self.business.refresh_from_db()

        self.assertEqual(
            context.exception.code,
            "subscription_payment_mismatch",
        )
        self.assertEqual(
            payment.status,
            SubscriptionPayment.Status.FAILED,
        )
        self.assertIsNone(payment.fulfilled_at)
        self.assertFalse(self.business.has_active_subscription)

    def test_verification_snapshot_excludes_sensitive_gateway_data(self):
        # Audit evidence must not retain authorization or customer secrets.
        payment = self.initialize_payment()
        self.client.verify_transaction.return_value = (
            self.successful_verification(
                payment,
                authorization={
                    "authorization_code": "AUTH_sensitive_code",
                },
                customer={
                    "email": "private.customer@stockflow.test",
                },
            )
        )

        verified, _, activated = (
            verify_and_fulfill_subscription_payment(
                reference=payment.reference,
                client=self.client,
            )
        )

        snapshot = verified.provider_response["verification"]

        self.assertTrue(activated)
        self.assertNotIn("authorization", snapshot)
        self.assertNotIn("customer", snapshot)
        self.assertNotIn(
            "AUTH_sensitive_code",
            str(verified.provider_response),
        )

    def test_pending_verification_does_not_activate_access(self):
        # OTP or MoMo approval still in progress remains unfulfilled.
        payment = self.initialize_payment()
        self.client.verify_transaction.return_value = (
            self.successful_verification(
                payment,
                status="ongoing",
            )
        )

        with self.assertRaises(SubscriptionPaymentError) as context:
            verify_and_fulfill_subscription_payment(
                reference=payment.reference,
                client=self.client,
            )

        payment.refresh_from_db()
        self.business.refresh_from_db()

        self.assertEqual(
            context.exception.code,
            "subscription_payment_not_successful",
        )
        self.assertEqual(
            payment.status,
            SubscriptionPayment.Status.PENDING,
        )
        self.assertEqual(payment.provider_status, "ongoing")
        self.assertEqual(
            payment.provider_response["verification"]["status"],
            "ongoing",
        )
        self.assertIsNone(payment.fulfilled_at)
        self.assertFalse(self.business.has_active_subscription)
