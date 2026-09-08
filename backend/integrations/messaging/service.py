import uuid

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from intelligence.models import AutomationEvent

from ..models import MessageDelivery, MessagingPreference
from .provider import MessagingProviderError
from .sms import MNotifySmsProvider
from .templates import intelligence_event_sms, test_sms_message


SEVERITY_RANK = {
    AutomationEvent.Severity.INFO: 1,
    AutomationEvent.Severity.ATTENTION: 2,
    AutomationEvent.Severity.HIGH: 3,
}


def normalize_ghana_phone(value):
    raw = str(value or "").strip()
    digits = "".join(character for character in raw if character.isdigit())
    if digits.startswith("233") and len(digits) == 12:
        digits = "0" + digits[3:]
    elif len(digits) == 9:
        digits = "0" + digits
    if len(digits) != 10 or not digits.startswith("0"):
        raise ValueError("Use a valid Ghana phone number for StockFlow messaging.")
    return digits


def messaging_capabilities():
    sms_configured = all(
        str(getattr(settings, key, "") or "").strip()
        for key in ("MNOTIFY_API_KEY", "MNOTIFY_SENDER_ID", "MNOTIFY_API_URL")
    )
    return {
        "sms": {
            "provider": "mnotify",
            "available": sms_configured,
        },
        "whatsapp": {
            "provider": None,
            "available": False,
            "foundationReady": True,
        },
    }


def delivery_payload(delivery):
    return {
        "id": str(delivery.id),
        "channel": delivery.channel,
        "messageType": delivery.message_type,
        "sourceType": delivery.source_type,
        "sourceId": delivery.source_id,
        "recipient": delivery.recipient,
        "message": delivery.message,
        "provider": delivery.provider,
        "status": delivery.status,
        "providerReference": delivery.provider_reference,
        "failureReason": delivery.failure_reason,
        "attemptCount": delivery.attempt_count,
        "sentAt": delivery.sent_at,
        "createdAt": delivery.created_at,
    }


def list_deliveries(*, business, limit=100):
    rows = MessageDelivery.objects.filter(business=business)[: max(1, min(int(limit), 200))]
    return [delivery_payload(row) for row in rows]


def _attempt_sms(delivery):
    provider = MNotifySmsProvider()
    delivery.attempt_count += 1
    delivery.provider = provider.provider_name
    try:
        result = provider.send(
            recipient=delivery.recipient,
            message=delivery.message,
        )
    except MessagingProviderError as exc:
        delivery.status = MessageDelivery.Status.FAILED
        delivery.failure_reason = str(exc)[:255]
        delivery.provider_response_summary = exc.response_summary[:1000]
        delivery.save(
            update_fields=(
                "attempt_count",
                "provider",
                "status",
                "failure_reason",
                "provider_response_summary",
                "updated_at",
            )
        )
        return delivery

    delivery.status = MessageDelivery.Status.SENT
    delivery.provider_reference = str(result.get("provider_reference", ""))[:120]
    delivery.provider_response_summary = str(
        result.get("provider_response_summary", "")
    )[:1000]
    delivery.failure_reason = ""
    delivery.sent_at = timezone.now()
    delivery.save(
        update_fields=(
            "attempt_count",
            "provider",
            "status",
            "provider_reference",
            "provider_response_summary",
            "failure_reason",
            "sent_at",
            "updated_at",
        )
    )
    return delivery


def send_test_sms(*, business, preference):
    try:
        recipient = normalize_ghana_phone(preference.recipient_phone)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    delivery = MessageDelivery.objects.create(
        business=business,
        channel=MessageDelivery.Channel.SMS,
        message_type="test",
        source_type="manual_test",
        source_id="",
        dedupe_key=f"manual-test:{business.id}:{uuid.uuid4()}",
        recipient=recipient,
        message=test_sms_message(business),
    )
    return _attempt_sms(delivery)


def _event_is_enabled(*, preference, event):
    minimum = SEVERITY_RANK.get(preference.minimum_severity, 2)
    actual = SEVERITY_RANK.get(event.severity, 1)
    if actual < minimum:
        return False
    enabled_types = [str(value) for value in (preference.event_types or [])]
    if enabled_types and event.event_type not in enabled_types:
        return False
    return True


def _event_sms_delivery(*, preference, event):
    recipient = normalize_ghana_phone(preference.recipient_phone)
    dedupe_key = (
        f"intelligence-event:{event.business_id}:{event.id}:sms:{recipient}"
    )
    try:
        with transaction.atomic():
            delivery, created = MessageDelivery.objects.get_or_create(
                dedupe_key=dedupe_key,
                defaults={
                    "business": event.business,
                    "channel": MessageDelivery.Channel.SMS,
                    "message_type": event.event_type,
                    "source_type": "intelligence_event",
                    "source_id": str(event.id),
                    "recipient": recipient,
                    "message": intelligence_event_sms(event),
                },
            )
    except IntegrityError:
        delivery = MessageDelivery.objects.get(dedupe_key=dedupe_key)
        created = False
    if created:
        _attempt_sms(delivery)
    return delivery, created


def dispatch_intelligence_events(*, business, rule=None, since=None):
    preference, _ = MessagingPreference.objects.get_or_create(business=business)
    if not preference.sms_enabled or not preference.recipient_phone:
        return {"eligible": 0, "created": 0, "sent": 0, "failed": 0}

    events = AutomationEvent.objects.filter(business=business)
    if rule is not None:
        events = events.filter(rule=rule)
    if since is not None:
        events = events.filter(generated_at__gte=since)
    events = events.order_by("generated_at", "id")

    eligible = created_count = sent = failed = 0
    for event in events:
        if not _event_is_enabled(preference=preference, event=event):
            continue
        eligible += 1
        try:
            delivery, created = _event_sms_delivery(
                preference=preference,
                event=event,
            )
        except ValueError:
            # Invalid recipient configuration must not make Intelligence
            # automation fail. The preference remains available for correction.
            failed += 1
            continue
        if not created:
            continue
        created_count += 1
        if delivery.status == MessageDelivery.Status.SENT:
            sent += 1
        elif delivery.status == MessageDelivery.Status.FAILED:
            failed += 1

    return {
        "eligible": eligible,
        "created": created_count,
        "sent": sent,
        "failed": failed,
    }
