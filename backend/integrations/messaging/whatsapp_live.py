import json
import re

import requests
from rest_framework import serializers

from integrations.messaging.provider import MessagingProviderError
from integrations.provider_credentials import (
    delete_provider_credential,
    get_provider_credential,
    save_provider_credential,
    touch_provider_credential,
)


PROVIDER_NAME = "whatsapp_cloud_api"


def normalize_whatsapp_recipient(value):
    digits = re.sub(r"\D+", "", str(value or ""))
    if len(digits) == 10 and digits.startswith("0"):
        digits = "233" + digits[1:]
    elif len(digits) == 9:
        digits = "233" + digits
    if len(digits) < 8 or len(digits) > 15:
        raise ValueError("Enter a valid WhatsApp phone number.")
    return digits


def whatsapp_configured(business):
    row, payload = get_provider_credential(
        business=business,
        category="messaging",
        provider="whatsapp",
    )
    return bool(
        row
        and payload
        and payload.get("access_token")
        and payload.get("phone_number_id")
        and payload.get("api_version")
    )


def save_whatsapp_credentials(
    *,
    business,
    access_token,
    phone_number_id,
    api_version,
    created_by=None,
):
    access_token = str(access_token or "").strip()
    phone_number_id = str(phone_number_id or "").strip()
    api_version = str(api_version or "").strip()
    if not access_token:
        raise serializers.ValidationError(
            {"accessToken": "WhatsApp access token is required."}
        )
    if not re.fullmatch(r"\d+", phone_number_id):
        raise serializers.ValidationError(
            {"phoneNumberId": "WhatsApp phone number ID must contain digits only."}
        )
    if not re.fullmatch(r"v\d+\.\d+", api_version):
        raise serializers.ValidationError(
            {"apiVersion": "Use a Meta Graph API version such as v23.0."}
        )
    return save_provider_credential(
        business=business,
        category="messaging",
        provider="whatsapp",
        created_by=created_by,
        payload={
            "access_token": access_token,
            "phone_number_id": phone_number_id,
            "api_version": api_version,
        },
    )


def delete_whatsapp_credentials(*, business):
    return delete_provider_credential(
        business=business,
        category="messaging",
        provider="whatsapp",
    )


def _safe_summary(payload):
    try:
        return json.dumps(payload, sort_keys=True, default=str)[:1000]
    except (TypeError, ValueError):
        return str(payload)[:1000]


def send_whatsapp_text(*, business, recipient, message):
    row, payload = get_provider_credential(
        business=business,
        category="messaging",
        provider="whatsapp",
        required=True,
    )
    try:
        recipient = normalize_whatsapp_recipient(recipient)
    except ValueError as exc:
        raise MessagingProviderError(str(exc)) from exc

    try:
        response = requests.post(
            (
                f"https://graph.facebook.com/{payload['api_version']}/"
                f"{payload['phone_number_id']}/messages"
            ),
            headers={
                "Authorization": f"Bearer {payload['access_token']}",
                "Content-Type": "application/json",
            },
            json={
                "messaging_product": "whatsapp",
                "to": recipient,
                "type": "text",
                "text": {"body": str(message or "")[:4096]},
            },
            timeout=20,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        raise MessagingProviderError(
            "The WhatsApp provider could not be reached."
        ) from exc

    try:
        data = response.json()
    except ValueError:
        data = {}
    summary = _safe_summary(data)
    if not 200 <= response.status_code < 300:
        raise MessagingProviderError(
            "WhatsApp Cloud API rejected the message.",
            response_summary=summary,
        )

    touch_provider_credential(row)
    messages = data.get("messages") if isinstance(data, dict) else None
    message_id = (
        messages[0].get("id", "")
        if isinstance(messages, list) and messages and isinstance(messages[0], dict)
        else ""
    )
    return {
        "provider": PROVIDER_NAME,
        "provider_reference": str(message_id)[:120],
        "provider_response_summary": summary,
    }
