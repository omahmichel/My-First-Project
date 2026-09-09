import hashlib
import hmac
from datetime import timedelta
from urllib.parse import urlencode, urlparse

import requests
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import serializers

from integrations.models import CommerceConnection
from integrations.oauth_state import create_oauth_state, read_oauth_state
from integrations.provider_credentials import (
    delete_provider_credential,
    get_provider_credential,
    rotate_provider_credential,
    save_provider_credential,
    touch_provider_credential,
)
from integrations.webhooks.validation import assert_public_destination


SHOPIFY_SCOPES = (
    "read_products,write_products,read_inventory,write_inventory,read_orders"
)
REFRESH_EARLY_SECONDS = 5 * 60


def provider_configuration_available(provider):
    if provider == CommerceConnection.Provider.SHOPIFY:
        return bool(settings.SHOPIFY_CLIENT_ID and settings.SHOPIFY_CLIENT_SECRET)
    if provider == CommerceConnection.Provider.WOOCOMMERCE:
        # WooCommerce credentials are business-specific and supplied after the
        # connection record is created; no deployment-level app secret is needed.
        return True
    return False


def _expiry(seconds):
    try:
        seconds = int(seconds or 0)
    except (TypeError, ValueError):
        seconds = 0
    return timezone.now() + timedelta(seconds=seconds) if seconds > 0 else None


def _needs_refresh(row):
    return bool(
        row.access_expires_at
        and row.access_expires_at <= timezone.now() + timedelta(seconds=REFRESH_EARLY_SECONDS)
    )


def _request_json(method, url, label, **kwargs):
    try:
        response = requests.request(method, url, **kwargs)
    except requests.RequestException as exc:
        raise serializers.ValidationError(
            {"provider": f"{label} could not be reached."}
        ) from exc
    try:
        payload = response.json()
    except ValueError as exc:
        raise serializers.ValidationError(
            {"provider": f"{label} returned an invalid response."}
        ) from exc
    if not 200 <= response.status_code < 300:
        message = ""
        if isinstance(payload, dict):
            message = str(
                payload.get("error_description")
                or payload.get("error")
                or payload.get("message")
                or ""
            )
        raise serializers.ValidationError(
            {
                "provider": (
                    f"{label} rejected the request."
                    + (f" {message}" if message else "")
                )
            }
        )
    return payload


def _shopify_host(connection):
    parsed = urlparse(connection.shop_url or "")
    host = (parsed.hostname or "").lower().strip(".")
    if (
        parsed.scheme != "https"
        or not host.endswith(".myshopify.com")
        or host == "myshopify.com"
    ):
        raise serializers.ValidationError(
            {
                "shopUrl": (
                    "Shopify connections must use the HTTPS "
                    "*.myshopify.com store domain."
                )
            }
        )
    return host


def _shopify_callback_url(request):
    return request.build_absolute_uri(reverse("integrations:shopify-oauth-callback"))


def shopify_authorization_url(*, connection, request):
    if not provider_configuration_available(connection.provider):
        raise serializers.ValidationError(
            {"provider": "Shopify application credentials are not configured."}
        )
    host = _shopify_host(connection)
    state = create_oauth_state(
        category="commerce",
        provider="shopify",
        business_id=connection.business_id,
        connection_id=connection.id,
        user_id=request.user.id,
    )
    params = {
        "client_id": settings.SHOPIFY_CLIENT_ID,
        "scope": SHOPIFY_SCOPES,
        "redirect_uri": _shopify_callback_url(request),
        "state": state,
    }
    return f"https://{host}/admin/oauth/authorize?{urlencode(params)}"


def _verify_shopify_hmac(query_params):
    provided = str(query_params.get("hmac", ""))
    if not provided:
        raise serializers.ValidationError(
            {"provider": "Shopify callback signature is missing."}
        )

    pairs = []
    for key in query_params.keys():
        if key in {"hmac", "signature", "_stockflow_callback_uri"}:
            continue
        for value in query_params.getlist(key):
            pairs.append((key, value))
    pairs.sort(key=lambda item: (item[0], item[1]))
    message = urlencode(pairs)
    expected = hmac.new(
        settings.SHOPIFY_CLIENT_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(provided, expected):
        raise serializers.ValidationError(
            {"provider": "Shopify callback signature is invalid."}
        )


def complete_shopify_oauth(*, query_params):
    _verify_shopify_hmac(query_params)
    raw_state = query_params.get("state", "")
    code = query_params.get("code", "")
    shop = str(query_params.get("shop", "")).lower().strip()
    if not raw_state or not code or not shop:
        raise serializers.ValidationError(
            {"provider": "Shopify callback data is incomplete."}
        )

    try:
        state = read_oauth_state(
            raw_state,
            category="commerce",
            provider="shopify",
        )
    except ValueError as exc:
        raise serializers.ValidationError({"provider": str(exc)}) from exc

    connection = (
        CommerceConnection.objects.select_related("business")
        .filter(
            id=state["connectionId"],
            business_id=state["businessId"],
            provider=CommerceConnection.Provider.SHOPIFY,
        )
        .first()
    )
    if connection is None:
        raise serializers.ValidationError(
            {"provider": "The Shopify connection no longer exists."}
        )
    if shop != _shopify_host(connection):
        raise serializers.ValidationError(
            {"provider": "Shopify returned a different store domain."}
        )

    token = _request_json(
        "POST",
        f"https://{shop}/admin/oauth/access_token",
        "Shopify",
        data={
            "client_id": settings.SHOPIFY_CLIENT_ID,
            "client_secret": settings.SHOPIFY_CLIENT_SECRET,
            "code": code,
            # Public apps created in 2026 use expiring offline tokens.
            "expiring": "1",
        },
        headers={"Accept": "application/json"},
        timeout=20,
        allow_redirects=False,
    )
    access_token = str(token.get("access_token") or "")
    refresh_token = str(token.get("refresh_token") or "")
    if not access_token or not refresh_token:
        raise serializers.ValidationError(
            {"provider": "Shopify did not return the required expiring token pair."}
        )

    save_provider_credential(
        business=connection.business,
        category="commerce",
        provider="shopify",
        connection=connection,
        created_by=connection.created_by,
        payload={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "scope": token.get("scope", ""),
            "shop": shop,
        },
        access_expires_at=_expiry(token.get("expires_in")),
        refresh_expires_at=_expiry(token.get("refresh_token_expires_in")),
    )
    connection.status = CommerceConnection.Status.CONNECTED
    connection.last_error = ""
    connection.save(update_fields=("status", "last_error", "updated_at"))
    return connection


def _refresh_shopify(row, payload, connection):
    refresh_token = str(payload.get("refresh_token") or "")
    if not refresh_token:
        raise serializers.ValidationError(
            {"provider": "Shopify requires reconnection because its refresh token is missing."}
        )
    host = _shopify_host(connection)
    token = _request_json(
        "POST",
        f"https://{host}/admin/oauth/access_token",
        "Shopify",
        data={
            "grant_type": "refresh_token",
            "client_id": settings.SHOPIFY_CLIENT_ID,
            "client_secret": settings.SHOPIFY_CLIENT_SECRET,
            "refresh_token": refresh_token,
        },
        headers={"Accept": "application/json"},
        timeout=20,
        allow_redirects=False,
    )
    replacement = {
        "access_token": token.get("access_token", ""),
        "refresh_token": token.get("refresh_token", ""),
        "scope": token.get("scope", payload.get("scope", "")),
        "shop": host,
    }
    if not replacement["access_token"] or not replacement["refresh_token"]:
        raise serializers.ValidationError(
            {"provider": "Shopify returned an incomplete refreshed token pair."}
        )
    return rotate_provider_credential(
        row=row,
        expected_refresh_token=refresh_token,
        replacement_payload=replacement,
        access_expires_at=_expiry(token.get("expires_in")),
        refresh_expires_at=_expiry(token.get("refresh_token_expires_in")),
    )


def shopify_access_token(connection):
    row, payload = get_provider_credential(
        business=connection.business,
        category="commerce",
        provider="shopify",
        connection=connection,
        required=True,
    )
    if _needs_refresh(row):
        row, payload, _changed = _refresh_shopify(row, payload, connection)
    token = str(payload.get("access_token") or "")
    if not token:
        raise serializers.ValidationError(
            {"provider": "The stored Shopify access token is unavailable."}
        )
    return row, payload, token


def _shopify_graphql(*, connection, token, query):
    host = _shopify_host(connection)
    payload = _request_json(
        "POST",
        (
            f"https://{host}/admin/api/"
            f"{settings.SHOPIFY_ADMIN_API_VERSION}/graphql.json"
        ),
        "Shopify",
        headers={
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": token,
        },
        json={"query": query},
        timeout=20,
        allow_redirects=False,
    )
    if payload.get("errors"):
        raise serializers.ValidationError(
            {"provider": "Shopify GraphQL returned an error."}
        )
    return payload


def save_woocommerce_credentials(
    *,
    connection,
    consumer_key,
    consumer_secret,
    created_by=None,
):
    if connection.provider != CommerceConnection.Provider.WOOCOMMERCE:
        raise serializers.ValidationError(
            {"provider": "This connection is not a WooCommerce connection."}
        )
    if not str(consumer_key or "").strip() or not str(consumer_secret or "").strip():
        raise serializers.ValidationError(
            {"provider": "WooCommerce consumer key and secret are required."}
        )
    assert_public_destination(connection.shop_url)
    save_provider_credential(
        business=connection.business,
        category="commerce",
        provider="woocommerce",
        connection=connection,
        created_by=created_by,
        payload={
            "consumer_key": str(consumer_key).strip(),
            "consumer_secret": str(consumer_secret).strip(),
        },
    )
    test_commerce_connection(connection)
    return connection


def _woocommerce_products_request(*, connection, key, secret):
    base = connection.shop_url.rstrip("/")
    assert_public_destination(base)
    return _request_json(
        "GET",
        f"{base}/wp-json/wc/v3/products",
        "WooCommerce",
        params={"per_page": 1},
        auth=(key, secret),
        headers={"Accept": "application/json"},
        timeout=20,
        allow_redirects=False,
    )


def test_commerce_connection(connection):
    if connection.provider == CommerceConnection.Provider.SHOPIFY:
        row, _payload, token = shopify_access_token(connection)
        _shopify_graphql(
            connection=connection,
            token=token,
            query="{ shop { id name } }",
        )
    else:
        row, payload = get_provider_credential(
            business=connection.business,
            category="commerce",
            provider=connection.provider,
            connection=connection,
            required=True,
        )
        key = payload.get("consumer_key", "")
        secret = payload.get("consumer_secret", "")
        if not key or not secret:
            raise serializers.ValidationError(
                {"provider": "WooCommerce credentials are incomplete."}
            )
        _woocommerce_products_request(
            connection=connection,
            key=key,
            secret=secret,
        )

    connection.status = CommerceConnection.Status.CONNECTED
    connection.last_error = ""
    connection.save(update_fields=("status", "last_error", "updated_at"))
    touch_provider_credential(row)
    return connection


def disconnect_commerce_connection(connection):
    delete_provider_credential(
        business=connection.business,
        category="commerce",
        provider=connection.provider,
        connection=connection,
    )
    connection.status = CommerceConnection.Status.DISCONNECTED
    connection.last_error = ""
    connection.save(update_fields=("status", "last_error", "updated_at"))
    return connection
