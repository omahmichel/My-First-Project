from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock

import requests
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from businesses.models import Business
from customers.models import Customer

from .debt_reminder_service import process_debt_reminders
from .models import (
    DebtOverdueCharge,
    DebtReminderAttempt,
    DebtReminderSchedule,
    Sale,
)


@override_settings(
    MNOTIFY_API_URL="https://api.mnotify.test/api/sms/quick",
    MNOTIFY_API_KEY="test-mnotify-key",
    MNOTIFY_SENDER_ID="StockFlow",
    MNOTIFY_TIMEOUT_SECONDS=5,
    DEBT_REMINDER_RETRY_MINUTES=1,
)
class DebtReminderServiceTests(TestCase):
    # Protects deterministic scheduling, access gates, retries, and audits.

    def setUp(self):
        self.owner = User.objects.create_user(
            email="debt.reminders@stockflow.test",
            password="StrongPass123!",
            full_name="Debt Reminder Owner",
        )
        self.business = Business.objects.create(
            owner=self.owner,
            name="Debt Reminder Shop",
            slug="debt-reminder-shop",
            business_type="building_materials",
            phone="0240000000",
            email="reminders@stockflow.test",
            invoice_prefix="INV",
            receipt_prefix="RCT",
        )
        self.customer = Customer.objects.create(
            business=self.business,
            name="Ama Reminder Customer",
            phone="0241234567",
            email="ama.reminder@example.com",
            outstanding_balance=Decimal("100.00"),
            total_purchases=Decimal("140.00"),
            created_by=self.owner,
        )
        self.sale = Sale.objects.create(
            business=self.business,
            customer=self.customer,
            sale_number="SAL-REMINDER-0001",
            invoice_number="INV-REMINDER-0001",
            payment_method=Sale.PaymentMethod.CREDIT,
            status=Sale.Status.PARTIALLY_PAID,
            subtotal=Decimal("140.00"),
            discount=Decimal("0.00"),
            total=Decimal("140.00"),
            amount_paid=Decimal("40.00"),
            outstanding_balance=Decimal("100.00"),
            debt_due_date=(
                timezone.localdate() - timedelta(days=10)
            ),
            debt_principal_at_due=Decimal("100.00"),
            cashier=self.owner,
            cashier_name=self.owner.full_name,
        )

    @staticmethod
    def _response(*, status_code=200, payload=None):
        response = Mock()
        response.status_code = status_code
        response.json.return_value = payload or {
            "status": "success",
            "code": 2000,
            "message": "messages sent successfully",
            "summary": {
                "message_id": "mnotify-message-001",
            },
        }
        return response

    def test_due_reminder_is_sent_once_with_current_total_due(self):
        # Day ten sends principal plus the current non-compounding charge.
        request_func = Mock(return_value=self._response())

        first = process_debt_reminders(
            request_func=request_func,
        )
        replay = process_debt_reminders(
            request_func=request_func,
        )

        self.assertEqual(first["created"], 1)
        self.assertEqual(first["sent"], 1)
        self.assertEqual(replay["sent"], 0)
        self.assertEqual(request_func.call_count, 1)
        self.assertEqual(DebtReminderSchedule.objects.count(), 1)
        self.assertEqual(DebtReminderAttempt.objects.count(), 1)
        self.assertEqual(DebtOverdueCharge.objects.count(), 1)

        payload = request_func.call_args.kwargs["json"]
        self.assertEqual(payload["recipient"], ["0241234567"])
        self.assertIn("GHS 105.00", payload["message"])

        schedule = DebtReminderSchedule.objects.get()
        attempt = DebtReminderAttempt.objects.get()
        self.assertEqual(
            schedule.status,
            DebtReminderSchedule.Status.SENT,
        )
        self.assertEqual(
            attempt.status,
            DebtReminderAttempt.Status.SENT,
        )
        self.assertEqual(
            attempt.provider_reference,
            "mnotify-message-001",
        )

    def test_missed_runs_create_only_the_latest_elapsed_slot(self):
        # A late worker sends one current reminder instead of catch-up spam.
        self.sale.debt_due_date = (
            timezone.localdate() - timedelta(days=25)
        )
        self.sale.save(
            update_fields=("debt_due_date", "updated_at")
        )
        request_func = Mock(return_value=self._response())

        summary = process_debt_reminders(
            request_func=request_func,
        )

        self.assertEqual(summary["created"], 1)
        self.assertEqual(summary["sent"], 1)
        schedule = DebtReminderSchedule.objects.get()
        self.assertEqual(schedule.reminder_sequence_number, 2)
        self.assertEqual(
            schedule.scheduled_for,
            self.sale.debt_due_date + timedelta(days=20),
        )

    def test_expired_business_access_skips_sms_safely(self):
        # Expired trial and subscription access must stop customer messages.
        self.business.subscription_status = (
            Business.SubscriptionStatus.EXPIRED
        )
        self.business.trial_ends_at = (
            timezone.now() - timedelta(days=1)
        )
        self.business.save(
            update_fields=(
                "subscription_status",
                "trial_ends_at",
                "updated_at",
            )
        )
        request_func = Mock()

        summary = process_debt_reminders(
            request_func=request_func,
        )

        self.assertEqual(summary["skipped"], 1)
        request_func.assert_not_called()
        schedule = DebtReminderSchedule.objects.get()
        attempt = DebtReminderAttempt.objects.get()
        self.assertEqual(
            schedule.status,
            DebtReminderSchedule.Status.SKIPPED,
        )
        self.assertEqual(
            attempt.status,
            DebtReminderAttempt.Status.SKIPPED,
        )
        self.assertIn(
            "subscription has expired",
            attempt.failure_reason,
        )

    def test_provider_failure_is_audited_and_retryable(self):
        # A failed provider call retries after the protected cooldown.
        failed_response = self._response(
            status_code=500,
            payload={
                "status": "error",
                "message": "temporary provider failure",
            },
        )
        request_func = Mock(
            side_effect=(
                failed_response,
                self._response(),
            )
        )

        first = process_debt_reminders(
            request_func=request_func,
        )

        self.assertEqual(first["failed"], 1)
        schedule = DebtReminderSchedule.objects.get()
        self.assertEqual(
            schedule.status,
            DebtReminderSchedule.Status.FAILED,
        )

        schedule.last_attempted_at = (
            timezone.now() - timedelta(minutes=2)
        )
        schedule.save(
            update_fields=(
                "last_attempted_at",
                "updated_at",
            )
        )

        second = process_debt_reminders(
            request_func=request_func,
        )

        self.assertEqual(second["sent"], 1)
        schedule.refresh_from_db()
        self.assertEqual(
            schedule.status,
            DebtReminderSchedule.Status.SENT,
        )
        self.assertEqual(
            list(
                schedule.attempts.values_list(
                    "status",
                    flat=True,
                )
            ),
            [
                DebtReminderAttempt.Status.FAILED,
                DebtReminderAttempt.Status.SENT,
            ],
        )

    def test_settled_debt_creates_no_reminder_slot(self):
        # Fully paid sales must not enter the reminder pipeline.
        self.sale.amount_paid = self.sale.total
        self.sale.outstanding_balance = Decimal("0.00")
        self.sale.status = Sale.Status.COMPLETED
        self.sale.save(
            update_fields=(
                "amount_paid",
                "outstanding_balance",
                "status",
                "updated_at",
            )
        )
        self.customer.outstanding_balance = Decimal("0.00")
        self.customer.save(
            update_fields=(
                "outstanding_balance",
                "updated_at",
            )
        )
        request_func = Mock()

        summary = process_debt_reminders(
            request_func=request_func,
        )

        self.assertEqual(summary["created"], 0)
        self.assertEqual(summary["scanned"], 0)
        request_func.assert_not_called()
        self.assertFalse(DebtReminderSchedule.objects.exists())

    def test_failed_slot_does_not_create_catch_up_sms(self):
        # A late retry sends once and blocks a second immediate reminder.
        failed_response = self._response(
            status_code=500,
            payload={
                "status": "error",
                "message": "temporary failure",
            },
        )
        request_func = Mock(
            side_effect=(
                failed_response,
                self._response(),
            )
        )

        first = process_debt_reminders(
            request_func=request_func,
        )
        self.assertEqual(first["failed"], 1)

        schedule = DebtReminderSchedule.objects.get()
        schedule.last_attempted_at = (
            timezone.now() - timedelta(minutes=2)
        )
        schedule.save(
            update_fields=(
                "last_attempted_at",
                "updated_at",
            )
        )

        future_date = timezone.localdate() + timedelta(days=10)
        retry = process_debt_reminders(
            as_of_date=future_date,
            request_func=request_func,
        )
        immediate_replay = process_debt_reminders(
            as_of_date=future_date + timedelta(days=1),
            request_func=request_func,
        )

        self.assertEqual(retry["created"], 0)
        self.assertEqual(retry["sent"], 1)
        self.assertEqual(immediate_replay["created"], 0)
        self.assertEqual(immediate_replay["sent"], 0)
        self.assertEqual(DebtReminderSchedule.objects.count(), 1)
        self.assertEqual(request_func.call_count, 2)

    def test_missing_business_phone_uses_no_customer_contact_number(self):
        # The SMS recipient number must never become the shop contact number.
        self.business.phone = ""
        self.business.save(
            update_fields=("phone", "updated_at")
        )
        request_func = Mock(return_value=self._response())

        summary = process_debt_reminders(
            request_func=request_func,
        )

        self.assertEqual(summary["sent"], 1)
        payload = request_func.call_args.kwargs["json"]
        self.assertEqual(payload["recipient"], ["0241234567"])
        self.assertNotIn("0241234567", payload["message"])
        self.assertIn(
            "contact Debt Reminder Shop",
            payload["message"],
        )

    def test_network_error_redacts_mnotify_key_from_audit(self):
        # Provider failures must not store the secret API key.
        request_func = Mock(
            side_effect=requests.ConnectionError(
                "Failed request using test-mnotify-key",
            )
        )

        summary = process_debt_reminders(
            request_func=request_func,
        )

        self.assertEqual(summary["failed"], 1)
        attempt = DebtReminderAttempt.objects.get()
        self.assertNotIn(
            "test-mnotify-key",
            attempt.provider_response_summary,
        )
        self.assertIn(
            "[REDACTED]",
            attempt.provider_response_summary,
        )
