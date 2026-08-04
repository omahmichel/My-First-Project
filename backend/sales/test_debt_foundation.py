from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from businesses.models import Business
from customers.models import Customer

from .models import (
    DebtOverdueCharge,
    DebtReminderAttempt,
    DebtReminderSchedule,
    Sale,
)


class DebtFoundationModelTests(TestCase):
    # Verifies the debt foundation without changing live payment behavior.

    def setUp(self):
        self.owner = User.objects.create_user(
            email="debt.foundation@stockflow.local",
            password="StrongPass123!",
            full_name="Debt Foundation Owner",
        )
        self.business = Business.objects.create(
            owner=self.owner,
            name="Debt Foundation Shop",
            slug="debt-foundation-shop",
            business_type="building_materials",
            invoice_prefix="INV",
            receipt_prefix="RCT",
        )
        self.other_business = Business.objects.create(
            owner=self.owner,
            name="Other Debt Shop",
            slug="other-debt-shop",
            business_type="boutique",
            invoice_prefix="INV",
            receipt_prefix="RCT",
        )
        self.customer = Customer.objects.create(
            business=self.business,
            name="Akosua Debt Customer",
            phone="0551234567",
            email="akosua.debt@example.com",
            address="Kumasi",
            created_by=self.owner,
        )
        self.other_customer = Customer.objects.create(
            business=self.other_business,
            name="Other Debt Customer",
            phone="0241234567",
            email="other.debt@example.com",
            address="Accra",
            created_by=self.owner,
        )
        self.sale = Sale.objects.create(
            business=self.business,
            customer=self.customer,
            sale_number="SAL-DEBT-0001",
            invoice_number="INV-DEBT-0001",
            payment_method=Sale.PaymentMethod.CREDIT,
            status=Sale.Status.PARTIALLY_PAID,
            subtotal=Decimal("1000.00"),
            discount=Decimal("0.00"),
            total=Decimal("1000.00"),
            amount_paid=Decimal("0.00"),
            outstanding_balance=Decimal("1000.00"),
            debt_due_date=timezone.localdate(),
            debt_principal_at_due=Decimal("1000.00"),
            cashier=self.owner,
            cashier_name=self.owner.full_name,
        )

    def test_sale_debt_fields_preserve_original_invoice_totals(self):
        # Debt metadata must not alter the original invoice invariant.
        self.assertEqual(self.sale.total, Decimal("1000.00"))
        self.assertEqual(
            self.sale.outstanding_balance,
            Decimal("1000.00"),
        )
        self.assertEqual(
            self.sale.debt_principal_at_due,
            Decimal("1000.00"),
        )
        self.assertEqual(
            self.sale.outstanding_balance,
            self.sale.total - self.sale.amount_paid,
        )

    def test_overdue_charge_rejects_cross_business_customer(self):
        # Overdue audit records must stay inside one business account.
        charge = DebtOverdueCharge(
            business=self.business,
            customer=self.other_customer,
            sale=self.sale,
            tier_percentage=5,
            principal_base=Decimal("1000.00"),
            total_charge_required=Decimal("50.00"),
            incremental_amount=Decimal("50.00"),
        )

        with self.assertRaises(ValidationError):
            charge.full_clean()

    def test_one_overdue_record_is_allowed_per_sale_and_tier(self):
        # Reprocessing the same tier must not duplicate its audit record.
        DebtOverdueCharge.objects.create(
            business=self.business,
            customer=self.customer,
            sale=self.sale,
            tier_percentage=5,
            principal_base=Decimal("1000.00"),
            total_charge_required=Decimal("50.00"),
            incremental_amount=Decimal("50.00"),
        )

        with self.assertRaises(ValidationError):
            DebtOverdueCharge.objects.create(
                business=self.business,
                customer=self.customer,
                sale=self.sale,
                tier_percentage=5,
                principal_base=Decimal("1000.00"),
                total_charge_required=Decimal("50.00"),
                incremental_amount=Decimal("50.00"),
            )

    def test_one_schedule_is_allowed_per_sale_and_date(self):
        # One deterministic reminder slot must exist for each due date.
        schedule_date = timezone.localdate()
        DebtReminderSchedule.objects.create(
            business=self.business,
            customer=self.customer,
            sale=self.sale,
            scheduled_for=schedule_date,
            reminder_sequence_number=1,
        )

        with self.assertRaises(ValidationError):
            DebtReminderSchedule.objects.create(
                business=self.business,
                customer=self.customer,
                sale=self.sale,
                scheduled_for=schedule_date,
                reminder_sequence_number=1,
            )

    def test_multiple_attempts_are_allowed_for_one_schedule(self):
        # A failed provider call can be retried without losing its audit.
        schedule = DebtReminderSchedule.objects.create(
            business=self.business,
            customer=self.customer,
            sale=self.sale,
            scheduled_for=timezone.localdate(),
            reminder_sequence_number=1,
        )

        first_attempt = DebtReminderAttempt.objects.create(
            schedule=schedule,
            business=self.business,
            customer=self.customer,
            sale=self.sale,
            attempt_number=1,
            status=DebtReminderAttempt.Status.FAILED,
            recipient_snapshot="233551234567",
            message_snapshot="First reminder attempt.",
            provider="mnotify",
            failure_reason="Temporary provider failure.",
        )
        second_attempt = DebtReminderAttempt.objects.create(
            schedule=schedule,
            business=self.business,
            customer=self.customer,
            sale=self.sale,
            attempt_number=2,
            status=DebtReminderAttempt.Status.SENT,
            recipient_snapshot="233551234567",
            message_snapshot="Second reminder attempt.",
            provider="mnotify",
            provider_reference="TEST-REFERENCE-001",
        )

        self.assertEqual(schedule.attempts.count(), 2)
        self.assertEqual(
            first_attempt.status,
            DebtReminderAttempt.Status.FAILED,
        )
        self.assertEqual(
            second_attempt.status,
            DebtReminderAttempt.Status.SENT,
        )

    def test_attempt_number_cannot_repeat_for_one_schedule(self):
        # One retry number cannot be recorded twice for the same slot.
        schedule = DebtReminderSchedule.objects.create(
            business=self.business,
            customer=self.customer,
            sale=self.sale,
            scheduled_for=timezone.localdate(),
            reminder_sequence_number=1,
        )
        DebtReminderAttempt.objects.create(
            schedule=schedule,
            business=self.business,
            customer=self.customer,
            sale=self.sale,
            attempt_number=1,
            status=DebtReminderAttempt.Status.FAILED,
        )

        with self.assertRaises(ValidationError):
            DebtReminderAttempt.objects.create(
                schedule=schedule,
                business=self.business,
                customer=self.customer,
                sale=self.sale,
                attempt_number=1,
                status=DebtReminderAttempt.Status.SENT,
            )

    def test_attempt_rejects_schedule_account_mismatch(self):
        # An attempt must match the schedule business, customer, and sale.
        schedule = DebtReminderSchedule.objects.create(
            business=self.business,
            customer=self.customer,
            sale=self.sale,
            scheduled_for=timezone.localdate(),
            reminder_sequence_number=1,
        )
        attempt = DebtReminderAttempt(
            schedule=schedule,
            business=self.other_business,
            customer=self.customer,
            sale=self.sale,
            attempt_number=1,
            status=DebtReminderAttempt.Status.SKIPPED,
        )

        with self.assertRaises(ValidationError):
            attempt.full_clean()
