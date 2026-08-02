from decimal import Decimal

from django.test import TestCase

from accounts.models import User
from businesses.models import Business, SubscriptionPayment


class SubscriptionPaymentModelTests(TestCase):
    """Protects the fixed StockFlow 40-day payment audit structure."""

    def setUp(self):
        # Creates one owner and business for isolated payment model tests.
        self.owner = User.objects.create_user(
            email="payment.owner@stockflow.test",
            password="StrongPass123!",
            full_name="Payment Owner",
        )
        self.business = Business.objects.create(
            owner=self.owner,
            name="Payment Test Shop",
            slug="payment-test-shop",
            business_type=Business.BusinessType.BOUTIQUE,
        )

    def create_payment(self):
        # Creates one pending owner-initiated subscription attempt.
        return SubscriptionPayment.objects.create(
            business=self.business,
            initiated_by=self.owner,
            initiated_by_email=self.owner.email,
            initiated_by_name=self.owner.full_name,
        )

    def test_payment_uses_fixed_launch_terms(self):
        # The model snapshots the agreed price, currency and access period.
        payment = self.create_payment()

        self.assertEqual(payment.amount, Decimal("99.00"))
        self.assertEqual(payment.amount_subunit, 9900)
        self.assertEqual(payment.currency, "GHS")
        self.assertEqual(payment.duration_days, 40)
        self.assertEqual(
            payment.status,
            SubscriptionPayment.Status.PENDING,
        )
        self.assertEqual(
            payment.gateway,
            SubscriptionPayment.Gateway.PAYSTACK,
        )

    def test_payment_reference_is_unique_and_paystack_safe(self):
        # References contain only characters accepted by Paystack.
        first = self.create_payment()
        second = self.create_payment()

        self.assertNotEqual(first.reference, second.reference)
        self.assertRegex(
            first.reference,
            r"^STF-[0-9]{14}-[A-F0-9]{12}$",
        )

    def test_new_payment_is_not_fulfilled(self):
        # A pending payment must not grant subscription value.
        payment = self.create_payment()

        self.assertFalse(payment.is_fulfilled)
        self.assertIsNone(payment.fulfilled_at)
