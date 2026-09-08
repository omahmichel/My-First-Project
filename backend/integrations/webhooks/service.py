import hashlib
import hmac
import json
import uuid
from datetime import timedelta

import requests
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from ..models import WebhookDelivery, WebhookEndpoint, WebhookEvent
from .validation import assert_public_destination

MAX_ATTEMPTS = 6
RETRY_SECONDS = (60, 300, 900, 3600, 21600)


def endpoint_signing_secret(endpoint):
    material = f"stockflow-webhook:v1:{endpoint.id}:{endpoint.secret_salt}"
    digest = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        material.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"whsec_{digest}"


def _json_safe(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def emit_webhook_event(*, business, event_type, payload, source_type="", source_id=""):
    endpoints = [
        row for row in WebhookEndpoint.objects.filter(
            business=business, is_active=True
        )
        if event_type in (row.events or [])
    ]
    if not endpoints:
        return None
    safe_payload = _json_safe(payload)
    digest = hashlib.sha256(
        json.dumps(safe_payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    dedupe_key = f"{event_type}:{source_type}:{source_id}:{digest}"[:255]
    with transaction.atomic():
        event, _ = WebhookEvent.objects.get_or_create(
            business=business,
            dedupe_key=dedupe_key,
            defaults={
                "event_type": event_type,
                "source_type": str(source_type or "")[:80],
                "source_id": str(source_id or "")[:80],
                "payload": safe_payload,
            },
        )
        for endpoint in endpoints:
            WebhookDelivery.objects.get_or_create(event=event, endpoint=endpoint)
    return event


def queue_test_delivery(endpoint):
    event = WebhookEvent.objects.create(
        business=endpoint.business,
        event_type="integration.test",
        source_type="webhook_endpoint",
        source_id=str(endpoint.id),
        dedupe_key=f"integration.test:{endpoint.id}:{uuid.uuid4()}",
        payload={"message": "StockFlow webhook delivery test."},
    )
    return WebhookDelivery.objects.create(event=event, endpoint=endpoint)


def _event_body(event):
    return json.dumps({
        "id": str(event.id),
        "version": "1",
        "type": event.event_type,
        "createdAt": event.created_at.isoformat(),
        "businessId": str(event.business_id),
        "data": event.payload,
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _signature(endpoint, timestamp, body):
    secret = endpoint_signing_secret(endpoint)
    digest = hmac.new(
        secret.encode("utf-8"),
        str(timestamp).encode("utf-8") + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={digest}"


def _claim(delivery_id):
    now = timezone.now()
    stale = now - timedelta(minutes=10)
    with transaction.atomic():
        row = (WebhookDelivery.objects.select_for_update()
               .select_related("event", "endpoint")
               .filter(id=delivery_id).first())
        if not row or not row.endpoint.is_active or row.status == row.Status.SENT:
            return None
        if row.attempt_count >= MAX_ATTEMPTS:
            return None
        if row.status == row.Status.PROCESSING and row.claimed_at and row.claimed_at > stale:
            return None
        if row.status == row.Status.FAILED and (not row.next_attempt_at or row.next_attempt_at > now):
            return None
        row.status = row.Status.PROCESSING
        row.attempt_count += 1
        row.claimed_at = now
        row.last_attempt_at = now
        row.save(update_fields=(
            "status", "attempt_count", "claimed_at", "last_attempt_at", "updated_at"
        ))
        return row


def process_webhook_delivery(delivery_id, request_func=None):
    row = _claim(delivery_id)
    if not row:
        return None
    response = None
    now = timezone.now()
    body = _event_body(row.event)
    timestamp = int(now.timestamp())
    sender = request_func or requests.post
    try:
        assert_public_destination(row.endpoint.url)
        response = sender(
            row.endpoint.url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "StockFlow-Webhooks/1.0",
                "X-StockFlow-Event": row.event.event_type,
                "X-StockFlow-Delivery": str(row.id),
                "X-StockFlow-Timestamp": str(timestamp),
                "X-StockFlow-Signature": _signature(row.endpoint, timestamp, body),
            },
            timeout=10,
            allow_redirects=False,
        )
        if not 200 <= int(response.status_code) < 300:
            raise RuntimeError(f"Webhook endpoint returned HTTP {response.status_code}.")
    except Exception as exc:
        row.status = row.Status.FAILED
        row.response_code = int(getattr(response, "status_code", 0) or 0)
        row.response_summary = str(getattr(response, "text", "") or "")[:1000]
        row.failure_reason = str(exc)[:255]
        if row.attempt_count < MAX_ATTEMPTS:
            index = min(row.attempt_count - 1, len(RETRY_SECONDS) - 1)
            row.next_attempt_at = now + timedelta(seconds=RETRY_SECONDS[index])
        else:
            row.next_attempt_at = None
        row.claimed_at = None
        row.save(update_fields=(
            "status", "response_code", "response_summary", "failure_reason",
            "next_attempt_at", "claimed_at", "updated_at"
        ))
        return row

    row.status = row.Status.SENT
    row.response_code = int(response.status_code)
    row.response_summary = str(response.text or "")[:1000]
    row.failure_reason = ""
    row.next_attempt_at = None
    row.claimed_at = None
    row.delivered_at = timezone.now()
    row.save(update_fields=(
        "status", "response_code", "response_summary", "failure_reason",
        "next_attempt_at", "claimed_at", "delivered_at", "updated_at"
    ))
    return row


def process_due_webhook_deliveries(limit=50, request_func=None):
    now = timezone.now()
    stale = now - timedelta(minutes=10)
    ids = list(
        WebhookDelivery.objects.filter(
            Q(status=WebhookDelivery.Status.PENDING)
            | Q(status=WebhookDelivery.Status.FAILED, next_attempt_at__lte=now)
            | Q(status=WebhookDelivery.Status.PROCESSING, claimed_at__lte=stale),
            attempt_count__lt=MAX_ATTEMPTS,
            endpoint__is_active=True,
        ).order_by("created_at").values_list("id", flat=True)[:max(1, min(int(limit), 200))]
    )
    result = {"processed": 0, "sent": 0, "failed": 0}
    for delivery_id in ids:
        row = process_webhook_delivery(delivery_id, request_func=request_func)
        if not row:
            continue
        result["processed"] += 1
        if row.status == row.Status.SENT:
            result["sent"] += 1
        elif row.status == row.Status.FAILED:
            result["failed"] += 1
    return result
