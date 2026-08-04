from __future__ import annotations

import json
import re
from datetime import timedelta
from decimal import Decimal

import requests
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Exists, F, Max, OuterRef, Q, Sum
from django.utils import timezone

from .models import (
    DebtPaymentAllocation,
    DebtReminderAttempt,
    DebtReminderSchedule,
    Sale,
)
from .services import ensure_current_overdue_charges


ZERO = Decimal("0.00")
REMINDER_INTERVAL_DAYS = 10
PROVIDER_NAME = "mnotify"
MAX_PROVIDER_SUMMARY_LENGTH = 4000
MAX_SMS_LENGTH = 160


class DebtReminderProviderError(Exception):
    # Carries a safe provider summary without exposing the API key.

    def __init__(self, message, *, response_summary=""):
        super().__init__(message)
        self.response_summary = response_summary


def normalize_ghana_phone(phone):
    # Converts common Ghana formats into the local 10-digit SMS format.
    digits = re.sub(r"\D", "", phone or "")

    if digits.startswith("233") and len(digits) == 12:
        digits = f"0{digits[3:]}"

    if len(digits) != 10 or not digits.startswith("0"):
        raise ValueError(
            "Customer phone number must be a valid 10-digit Ghana number."
        )

    return digits


def latest_due_reminder_slot(*, sale, as_of_date):
    # Returns only the latest elapsed 10-day slot to avoid catch-up SMS spam.
    if not sale.debt_due_date:
        return None

    days_since_due = (as_of_date - sale.debt_due_date).days

    if days_since_due < REMINDER_INTERVAL_DAYS:
        return None

    sequence_number = days_since_due // REMINDER_INTERVAL_DAYS
    scheduled_for = sale.debt_due_date + timedelta(
        days=sequence_number * REMINDER_INTERVAL_DAYS,
    )
    return sequence_number, scheduled_for


def ensure_due_reminder_schedules(*, as_of_date=None, batch_size=100):
    # Creates at most one open reminder without catch-up SMS duplication.
    current_date = as_of_date or timezone.localdate()
    earliest_due_date = current_date - timedelta(
        days=REMINDER_INTERVAL_DAYS,
    )
    recent_sent_cutoff = timezone.now() - timedelta(
        days=REMINDER_INTERVAL_DAYS,
    )
    open_schedules = DebtReminderSchedule.objects.filter(
        sale_id=OuterRef("pk"),
        status__in=(
            DebtReminderSchedule.Status.PENDING,
            DebtReminderSchedule.Status.FAILED,
        ),
    )
    recent_sent_attempts = DebtReminderAttempt.objects.filter(
        sale_id=OuterRef("pk"),
        status=DebtReminderAttempt.Status.SENT,
        attempted_at__gt=recent_sent_cutoff,
    )
    eligible_sales = (
        Sale.objects.select_related(
            "business",
            "customer",
        )
        .annotate(
            has_open_reminder=Exists(open_schedules),
            has_recent_sent_reminder=Exists(recent_sent_attempts),
        )
        .filter(
            customer__isnull=False,
            debt_due_date__isnull=False,
            debt_due_date__lte=earliest_due_date,
            outstanding_balance__gt=ZERO,
            has_open_reminder=False,
            has_recent_sent_reminder=False,
        )
        .exclude(
            status__in=(
                Sale.Status.PENDING_PAYMENT,
                Sale.Status.CANCELLED,
                Sale.Status.FAILED,
            )
        )
        .order_by("debt_due_date", "created_at")
    )
    created_count = 0

    for sale in eligible_sales.iterator(chunk_size=200):
        if created_count >= batch_size:
            break

        slot = latest_due_reminder_slot(
            sale=sale,
            as_of_date=current_date,
        )

        if not slot:
            continue

        sequence_number, scheduled_for = slot

        try:
            _, created = DebtReminderSchedule.objects.get_or_create(
                sale=sale,
                scheduled_for=scheduled_for,
                defaults={
                    "business": sale.business,
                    "customer": sale.customer,
                    "reminder_sequence_number": sequence_number,
                },
            )
        except IntegrityError:
            # A concurrent worker may have created the same protected slot.
            created = False

        if created:
            created_count += 1

    return created_count


def _unpaid_overdue_charge(*, sale):
    # Calculates the audited overdue charge that has not yet been paid.
    total_charged = (
        sale.overdue_charges.aggregate(
            total=Sum("incremental_amount"),
        )["total"]
        or ZERO
    )
    total_paid = (
        DebtPaymentAllocation.objects.filter(
            sale=sale,
        ).aggregate(
            total=Sum("overdue_charge_paid"),
        )["total"]
        or ZERO
    )
    return max(ZERO, total_charged - total_paid)


def _total_debt_due(*, sale, as_of_date):
    # Includes current overdue charges without changing the principal invariant.
    ensure_current_overdue_charges(
        sale=sale,
        as_of_date=as_of_date,
    )
    return sale.outstanding_balance + _unpaid_overdue_charge(
        sale=sale,
    )


def _business_contact_phone(*, sale):
    # Uses only a valid business number as the customer's contact point.
    try:
        return normalize_ghana_phone(sale.business.phone)
    except ValueError:
        return ""


def _compact_sms_message(*, sale, amount_due):
    # Produces a concise reminder without exposing the customer's own number.
    business_name = " ".join(sale.business.name.split())
    invoice_number = " ".join(sale.invoice_number.split())
    contact = _business_contact_phone(sale=sale)
    contact_instruction = (
        f"Please contact {contact} to arrange payment."
        if contact
        else f"Please contact {business_name} to arrange payment."
    )
    message = (
        f"Payment reminder from {business_name}: invoice "
        f"{invoice_number} has GHS {amount_due:.2f} outstanding. "
        f"{contact_instruction}"
    )

    if len(message) <= MAX_SMS_LENGTH:
        return message

    shortened_business = business_name[:35].rstrip()
    shortened_invoice = invoice_number[:25].rstrip()
    shortened_contact = (
        f"Contact {contact}."
        if contact
        else f"Contact {shortened_business}."
    )
    shortened = (
        f"{shortened_business}: GHS {amount_due:.2f} remains due "
        f"on invoice {shortened_invoice}. {shortened_contact}"
    )
    return shortened[:MAX_SMS_LENGTH].rstrip()


def _safe_json_summary(payload):
    # Stores a bounded provider response without serializing secrets.
    try:
        summary = json.dumps(
            payload,
            sort_keys=True,
            default=str,
        )
    except (TypeError, ValueError):
        summary = str(payload)

    return summary[:MAX_PROVIDER_SUMMARY_LENGTH]


def _safe_exception_summary(exc):
    # Redacts the mNotify key before an exception enters the audit trail.
    summary = f"{exc.__class__.__name__}: {exc}"
    api_key = getattr(settings, "MNOTIFY_API_KEY", "").strip()

    if api_key:
        summary = summary.replace(api_key, "[REDACTED]")

    return summary[:MAX_PROVIDER_SUMMARY_LENGTH]


def _provider_reference(payload):
    # Extracts the most useful mNotify campaign identifier when available.
    summary = payload.get("summary")

    if isinstance(summary, dict):
        for key in ("message_id", "_id", "id"):
            value = summary.get(key)

            if value:
                return str(value)[:120]

    for key in ("message_id", "_id", "id"):
        value = payload.get(key)

        if value:
            return str(value)[:120]

    return ""


def _mnotify_configuration():
    # Validates required secrets only when a reminder is ready to send.
    api_key = getattr(settings, "MNOTIFY_API_KEY", "").strip()
    sender_id = getattr(settings, "MNOTIFY_SENDER_ID", "").strip()
    api_url = getattr(settings, "MNOTIFY_API_URL", "").strip()
    timeout = getattr(settings, "MNOTIFY_TIMEOUT_SECONDS", 15)

    missing = []

    if not api_key:
        missing.append("MNOTIFY_API_KEY")

    if not sender_id:
        missing.append("MNOTIFY_SENDER_ID")

    if not api_url:
        missing.append("MNOTIFY_API_URL")

    if missing:
        raise DebtReminderProviderError(
            "Missing SMS configuration: " + ", ".join(missing) + ".",
        )

    return {
        "api_key": api_key,
        "sender_id": sender_id,
        "api_url": api_url,
        "timeout": timeout,
    }


def send_mnotify_sms(*, recipient, message, request_func=None):
    # Sends one regular SMS through the official mNotify quick endpoint.
    config = _mnotify_configuration()
    sender = request_func or requests.post
    payload = {
        "recipient": [recipient],
        "sender": config["sender_id"],
        "message": message,
        "is_schedule": False,
        "schedule_date": "",
    }

    try:
        response = sender(
            config["api_url"],
            params={"key": config["api_key"]},
            json=payload,
            timeout=config["timeout"],
        )
    except requests.RequestException as exc:
        raise DebtReminderProviderError(
            "The SMS provider could not be reached.",
            response_summary=_safe_exception_summary(exc),
        ) from exc

    try:
        response_payload = response.json()
    except (TypeError, ValueError):
        response_payload = {
            "raw_response": getattr(response, "text", ""),
        }

    response_summary = _safe_json_summary(response_payload)
    provider_status = str(
        response_payload.get("status", ""),
    ).lower()

    if not 200 <= response.status_code < 300 or provider_status != "success":
        raise DebtReminderProviderError(
            "The SMS provider rejected the reminder.",
            response_summary=response_summary,
        )

    return {
        "provider": PROVIDER_NAME,
        "provider_reference": _provider_reference(response_payload),
        "provider_response_summary": response_summary,
    }


def _next_attempt_number(*, schedule):
    # Allocates the next protected audit sequence for one reminder slot.
    maximum = (
        schedule.attempts.aggregate(
            maximum=Max("attempt_number"),
        )["maximum"]
        or 0
    )
    return maximum + 1


def _record_attempt(
    *,
    schedule,
    sale,
    attempt_number,
    status,
    recipient="",
    message="",
    provider="",
    provider_reference="",
    provider_response_summary="",
    failure_reason="",
):
    # Persists an immutable snapshot of one reminder outcome.
    return DebtReminderAttempt.objects.create(
        schedule=schedule,
        business=sale.business,
        customer=sale.customer,
        sale=sale,
        attempt_number=attempt_number,
        status=status,
        recipient_snapshot=recipient,
        message_snapshot=message,
        provider=provider,
        provider_reference=provider_reference,
        provider_response_summary=provider_response_summary,
        failure_reason=failure_reason,
    )


def _skip_locked_schedule(
    *,
    schedule,
    sale,
    attempt_number,
    reason,
    recipient="",
):
    # Closes a reminder slot safely when sending is no longer permitted.
    _record_attempt(
        schedule=schedule,
        sale=sale,
        attempt_number=attempt_number,
        status=DebtReminderAttempt.Status.SKIPPED,
        recipient=recipient,
        provider=PROVIDER_NAME,
        failure_reason=reason,
    )
    schedule.status = DebtReminderSchedule.Status.SKIPPED
    schedule.save(
        update_fields=(
            "status",
            "last_attempted_at",
            "updated_at",
        )
    )
    return {
        "action": "skipped",
        "reason": reason,
    }


@transaction.atomic
def _claim_reminder_schedule(*, schedule_id, as_of_date):
    # Claims one slot with a retry cooldown before any external API call.
    schedule = (
        DebtReminderSchedule.objects.select_for_update()
        .select_related(
            "business",
            "customer",
            "sale",
        )
        .get(id=schedule_id)
    )

    if schedule.status in (
        DebtReminderSchedule.Status.SENT,
        DebtReminderSchedule.Status.SKIPPED,
    ):
        return {"action": "deferred"}

    if schedule.scheduled_for > as_of_date:
        return {"action": "deferred"}

    retry_minutes = getattr(
        settings,
        "DEBT_REMINDER_RETRY_MINUTES",
        15,
    )
    now = timezone.now()
    retry_after = now - timedelta(minutes=retry_minutes)

    if (
        schedule.last_attempted_at
        and schedule.last_attempted_at > retry_after
    ):
        return {"action": "deferred"}

    sale = (
        Sale.objects.select_for_update()
        .select_related(
            "business",
            "customer",
        )
        .get(id=schedule.sale_id)
    )
    attempt_number = _next_attempt_number(schedule=schedule)
    schedule.last_attempted_at = now
    schedule.save(
        update_fields=(
            "last_attempted_at",
            "updated_at",
        )
    )

    if sale.outstanding_balance <= ZERO:
        return _skip_locked_schedule(
            schedule=schedule,
            sale=sale,
            attempt_number=attempt_number,
            reason="The debt was already settled.",
        )

    if not sale.business.has_system_access:
        return _skip_locked_schedule(
            schedule=schedule,
            sale=sale,
            attempt_number=attempt_number,
            reason=(
                "The business trial or paid subscription has expired."
            ),
        )

    try:
        recipient = normalize_ghana_phone(
            sale.customer.phone or sale.customer_phone,
        )
    except ValueError as exc:
        return _skip_locked_schedule(
            schedule=schedule,
            sale=sale,
            attempt_number=attempt_number,
            reason=str(exc),
        )

    amount_due = _total_debt_due(
        sale=sale,
        as_of_date=as_of_date,
    )
    message = _compact_sms_message(
        sale=sale,
        amount_due=amount_due,
    )
    return {
        "action": "send",
        "schedule_id": schedule.id,
        "attempt_number": attempt_number,
        "recipient": recipient,
        "message": message,
    }


@transaction.atomic
def _finalize_reminder_attempt(
    *,
    claim,
    status,
    provider="",
    provider_reference="",
    provider_response_summary="",
    failure_reason="",
):
    # Finalizes the claimed slot and its immutable provider audit record.
    schedule = (
        DebtReminderSchedule.objects.select_for_update()
        .select_related(
            "business",
            "customer",
            "sale",
        )
        .get(id=claim["schedule_id"])
    )
    sale = schedule.sale

    if schedule.attempts.filter(
        attempt_number=claim["attempt_number"],
    ).exists():
        return schedule

    _record_attempt(
        schedule=schedule,
        sale=sale,
        attempt_number=claim["attempt_number"],
        status=status,
        recipient=claim["recipient"],
        message=claim["message"],
        provider=provider,
        provider_reference=provider_reference,
        provider_response_summary=provider_response_summary,
        failure_reason=failure_reason,
    )
    schedule.status = (
        DebtReminderSchedule.Status.SENT
        if status == DebtReminderAttempt.Status.SENT
        else DebtReminderSchedule.Status.FAILED
    )
    schedule.save(
        update_fields=(
            "status",
            "last_attempted_at",
            "updated_at",
        )
    )
    return schedule


def process_debt_reminders(
    *,
    as_of_date=None,
    batch_size=100,
    request_func=None,
):
    # Creates, sends, retries, and audits one bounded reminder batch.
    if batch_size < 1:
        raise ValueError("batch_size must be greater than zero.")

    current_date = as_of_date or timezone.localdate()
    created_count = ensure_due_reminder_schedules(
        as_of_date=current_date,
        batch_size=batch_size,
    )
    retry_minutes = getattr(
        settings,
        "DEBT_REMINDER_RETRY_MINUTES",
        15,
    )
    retry_after = timezone.now() - timedelta(minutes=retry_minutes)
    schedule_ids = list(
        DebtReminderSchedule.objects.filter(
            Q(last_attempted_at__isnull=True)
            | Q(last_attempted_at__lte=retry_after),
            scheduled_for__lte=current_date,
            status__in=(
                DebtReminderSchedule.Status.PENDING,
                DebtReminderSchedule.Status.FAILED,
            ),
        )
        .order_by(
            F("last_attempted_at").asc(nulls_first=True),
            "scheduled_for",
            "created_at",
        )
        .values_list("id", flat=True)[:batch_size]
    )
    summary = {
        "created": created_count,
        "scanned": len(schedule_ids),
        "sent": 0,
        "failed": 0,
        "skipped": 0,
        "deferred": 0,
    }

    for schedule_id in schedule_ids:
        claim = _claim_reminder_schedule(
            schedule_id=schedule_id,
            as_of_date=current_date,
        )

        if claim["action"] == "deferred":
            summary["deferred"] += 1
            continue

        if claim["action"] == "skipped":
            summary["skipped"] += 1
            continue

        try:
            result = send_mnotify_sms(
                recipient=claim["recipient"],
                message=claim["message"],
                request_func=request_func,
            )
        except DebtReminderProviderError as exc:
            _finalize_reminder_attempt(
                claim=claim,
                status=DebtReminderAttempt.Status.FAILED,
                provider=PROVIDER_NAME,
                provider_response_summary=exc.response_summary,
                failure_reason=str(exc),
            )
            summary["failed"] += 1
            continue
        except Exception as exc:
            # One unexpected provider error must not stop the full batch.
            _finalize_reminder_attempt(
                claim=claim,
                status=DebtReminderAttempt.Status.FAILED,
                provider=PROVIDER_NAME,
                failure_reason=_safe_exception_summary(exc),
            )
            summary["failed"] += 1
            continue

        _finalize_reminder_attempt(
            claim=claim,
            status=DebtReminderAttempt.Status.SENT,
            provider=result["provider"],
            provider_reference=result["provider_reference"],
            provider_response_summary=(
                result["provider_response_summary"]
            ),
        )
        summary["sent"] += 1

    return summary
