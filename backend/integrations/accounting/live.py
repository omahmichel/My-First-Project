from datetime import timedelta
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import serializers

from integrations.models import AccountingConnection
from integrations.oauth_state import create_oauth_state, read_oauth_state
from integrations.provider_credentials import (
    delete_provider_credential,
    get_provider_credential,
    rotate_provider_credential,
    save_provider_credential,
    touch_provider_credential,
)


QUICKBOOKS_AUTHORIZE_URL = "https://appcenter.intuit.com/connect/oauth2"
QUICKBOOKS_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
QUICKBOOKS_REVOKE_URL = "https://developer.api.intuit.com/v2/oauth2/tokens/revoke"
XERO_AUTHORIZE_URL = "https://login.xero.com/identity/connect/authorize"
XERO_TOKEN_URL = "https://identity.xero.com/connect/token"
XERO_CONNECTIONS_URL = "https://api.xero.com/connections"
XERO_REVOKE_URL = "https://identity.xero.com/connect/revocation"

# Xero apps created from March 2026 use granular Accounting API scopes.
# StockFlow needs invoices/bills, payments, contacts and item/settings access;
# the deprecated broad accounting.transactions scope is intentionally absent.
XERO_SCOPES = (
    "openid profile email offline_access "
    "accounting.invoices accounting.payments accounting.contacts accounting.settings"
)

REFRESH_EARLY_SECONDS = 5 * 60
XERO_REFRESH_LIFETIME_SECONDS = 60 * 24 * 60 * 60


def provider_configuration_available(provider):
    if provider == AccountingConnection.Provider.QUICKBOOKS:
        return bool(settings.QUICKBOOKS_CLIENT_ID and settings.QUICKBOOKS_CLIENT_SECRET)
    if provider == AccountingConnection.Provider.XERO:
        return bool(settings.XERO_CLIENT_ID and settings.XERO_CLIENT_SECRET)
    return False


def _callback_url(request, provider):
    return request.build_absolute_uri(
        reverse(
            "integrations:accounting-oauth-callback",
            kwargs={"provider": provider},
        )
    )


def accounting_authorization_url(*, connection, request):
    provider = connection.provider
    if not provider_configuration_available(provider):
        raise serializers.ValidationError(
            {
                "provider": (
                    f"{connection.get_provider_display()} application credentials "
                    "are not configured on this deployment."
                )
            }
        )

    state = create_oauth_state(
        category="accounting",
        provider=provider,
        business_id=connection.business_id,
        connection_id=connection.id,
        user_id=request.user.id,
    )
    redirect_uri = _callback_url(request, provider)

    if provider == AccountingConnection.Provider.QUICKBOOKS:
        params = {
            "client_id": settings.QUICKBOOKS_CLIENT_ID,
            "response_type": "code",
            "scope": "com.intuit.quickbooks.accounting",
            "redirect_uri": redirect_uri,
            "state": state,
        }
        return f"{QUICKBOOKS_AUTHORIZE_URL}?{urlencode(params)}"

    params = {
        "response_type": "code",
        "client_id": settings.XERO_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": XERO_SCOPES,
        "state": state,
    }
    return f"{XERO_AUTHORIZE_URL}?{urlencode(params)}"


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
            fault = payload.get("Fault") or {}
            fault_errors = fault.get("Error") if isinstance(fault, dict) else None
            fault_message = ""
            if isinstance(fault_errors, list) and fault_errors:
                fault_message = str((fault_errors[0] or {}).get("Message", ""))
            message = str(
                payload.get("error_description")
                or payload.get("error")
                or fault_message
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


def _quickbooks_base_url():
    if settings.QUICKBOOKS_ENVIRONMENT == "sandbox":
        return "https://sandbox-quickbooks.api.intuit.com"
    return "https://quickbooks.api.intuit.com"


def _quickbooks_company_info(*, realm_id, access_token):
    url = (
        f"{_quickbooks_base_url()}/v3/company/{realm_id}/"
        f"companyinfo/{realm_id}"
    )
    payload = _request_json(
        "GET",
        url,
        "QuickBooks",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
        timeout=20,
        allow_redirects=False,
    )
    company = payload.get("CompanyInfo") or {}
    return company.get("CompanyName", "")


def _xero_connections(access_token):
    payload = _request_json(
        "GET",
        XERO_CONNECTIONS_URL,
        "Xero",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
        timeout=20,
        allow_redirects=False,
    )
    if not isinstance(payload, list):
        raise serializers.ValidationError(
            {"provider": "Xero returned an invalid organization list."}
        )
    return payload


def _refresh_quickbooks(row, payload):
    refresh_token = str(payload.get("refresh_token") or "")
    if not refresh_token:
        raise serializers.ValidationError(
            {"provider": "QuickBooks requires reconnection because its refresh token is missing."}
        )
    token = _request_json(
        "POST",
        QUICKBOOKS_TOKEN_URL,
        "QuickBooks",
        auth=(settings.QUICKBOOKS_CLIENT_ID, settings.QUICKBOOKS_CLIENT_SECRET),
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        headers={"Accept": "application/json"},
        timeout=20,
    )
    replacement = {
        "access_token": token.get("access_token", ""),
        "refresh_token": token.get("refresh_token", ""),
        "token_type": token.get("token_type", payload.get("token_type", "bearer")),
        "scope": token.get("scope", payload.get("scope", "")),
    }
    if not replacement["access_token"] or not replacement["refresh_token"]:
        raise serializers.ValidationError(
            {"provider": "QuickBooks returned an incomplete refreshed token pair."}
        )
    refresh_expiry = (
        _expiry(token.get("x_refresh_token_expires_in"))
        if token.get("x_refresh_token_expires_in") is not None
        else row.refresh_expires_at
    )
    return rotate_provider_credential(
        row=row,
        expected_refresh_token=refresh_token,
        replacement_payload=replacement,
        access_expires_at=_expiry(token.get("expires_in")),
        refresh_expires_at=refresh_expiry,
    )


def _refresh_xero(row, payload):
    refresh_token = str(payload.get("refresh_token") or "")
    if not refresh_token:
        raise serializers.ValidationError(
            {"provider": "Xero requires reconnection because its refresh token is missing."}
        )
    token = _request_json(
        "POST",
        XERO_TOKEN_URL,
        "Xero",
        auth=(settings.XERO_CLIENT_ID, settings.XERO_CLIENT_SECRET),
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        headers={"Accept": "application/json"},
        timeout=20,
    )
    replacement = {
        "access_token": token.get("access_token", ""),
        "refresh_token": token.get("refresh_token", ""),
        "token_type": token.get("token_type", payload.get("token_type", "Bearer")),
        "scope": token.get("scope", payload.get("scope", "")),
    }
    if not replacement["access_token"] or not replacement["refresh_token"]:
        raise serializers.ValidationError(
            {"provider": "Xero returned an incomplete refreshed token pair."}
        )
    return rotate_provider_credential(
        row=row,
        expected_refresh_token=refresh_token,
        replacement_payload=replacement,
        access_expires_at=_expiry(token.get("expires_in")),
        refresh_expires_at=_expiry(XERO_REFRESH_LIFETIME_SECONDS),
    )


def accounting_access_token(connection):
    row, payload = get_provider_credential(
        business=connection.business,
        category="accounting",
        provider=connection.provider,
        connection=connection,
        required=True,
    )
    if _needs_refresh(row):
        if connection.provider == AccountingConnection.Provider.QUICKBOOKS:
            row, payload, _changed = _refresh_quickbooks(row, payload)
        elif connection.provider == AccountingConnection.Provider.XERO:
            row, payload, _changed = _refresh_xero(row, payload)
    access_token = str(payload.get("access_token") or "")
    if not access_token:
        raise serializers.ValidationError(
            {"provider": "The stored provider access token is unavailable."}
        )
    return row, payload, access_token


def complete_accounting_oauth(*, provider, query_params):
    raw_state = query_params.get("state", "")
    code = query_params.get("code", "")
    if not raw_state or not code:
        raise serializers.ValidationError(
            {"provider": "The provider callback is missing state or code."}
        )

    try:
        state = read_oauth_state(
            raw_state,
            category="accounting",
            provider=provider,
        )
    except ValueError as exc:
        raise serializers.ValidationError({"provider": str(exc)}) from exc

    connection = (
        AccountingConnection.objects.select_related("business")
        .filter(
            id=state["connectionId"],
            business_id=state["businessId"],
            provider=provider,
        )
        .first()
    )
    if connection is None:
        raise serializers.ValidationError(
            {"provider": "The accounting connection no longer exists."}
        )

    callback_uri = str(query_params.get("_stockflow_callback_uri") or "")
    if not callback_uri:
        raise serializers.ValidationError(
            {"provider": "The StockFlow callback URI could not be resolved."}
        )

    if provider == AccountingConnection.Provider.QUICKBOOKS:
        realm_id = str(query_params.get("realmId", "")).strip()
        if not realm_id:
            raise serializers.ValidationError(
                {"provider": "QuickBooks did not return a company ID."}
            )
        token = _request_json(
            "POST",
            QUICKBOOKS_TOKEN_URL,
            "QuickBooks",
            auth=(settings.QUICKBOOKS_CLIENT_ID, settings.QUICKBOOKS_CLIENT_SECRET),
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": callback_uri,
            },
            headers={"Accept": "application/json"},
            timeout=20,
        )
        access_token = str(token.get("access_token") or "")
        refresh_token = str(token.get("refresh_token") or "")
        if not access_token or not refresh_token:
            raise serializers.ValidationError(
                {"provider": "QuickBooks did not return the required OAuth token pair."}
            )
        company_name = _quickbooks_company_info(
            realm_id=realm_id,
            access_token=access_token,
        )
        save_provider_credential(
            business=connection.business,
            category="accounting",
            provider=provider,
            connection=connection,
            created_by=connection.created_by,
            payload={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": token.get("token_type", "bearer"),
                "scope": token.get("scope", ""),
                "realm_id": realm_id,
            },
            access_expires_at=_expiry(token.get("expires_in")),
            refresh_expires_at=_expiry(token.get("x_refresh_token_expires_in")),
        )
        connection.external_company_id = realm_id
        connection.external_company_name = company_name
        connection.status = AccountingConnection.Status.CONNECTED
        connection.last_error = ""
        connection.save(
            update_fields=(
                "external_company_id",
                "external_company_name",
                "status",
                "last_error",
                "updated_at",
            )
        )
        return connection, {"requiresTenantSelection": False}

    token = _request_json(
        "POST",
        XERO_TOKEN_URL,
        "Xero",
        auth=(settings.XERO_CLIENT_ID, settings.XERO_CLIENT_SECRET),
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": callback_uri,
        },
        headers={"Accept": "application/json"},
        timeout=20,
    )
    access_token = str(token.get("access_token") or "")
    refresh_token = str(token.get("refresh_token") or "")
    if not access_token or not refresh_token:
        raise serializers.ValidationError(
            {"provider": "Xero did not return the required OAuth token pair."}
        )
    tenants = _xero_connections(access_token)
    tenant_summary = [
        {
            "id": str(item.get("tenantId", "")),
            "name": str(item.get("tenantName", "")),
            "connectionId": str(item.get("id", "")),
        }
        for item in tenants
        if item.get("tenantId")
    ]
    save_provider_credential(
        business=connection.business,
        category="accounting",
        provider=provider,
        connection=connection,
        created_by=connection.created_by,
        payload={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": token.get("token_type", "Bearer"),
            "scope": token.get("scope", ""),
            "tenants": tenant_summary,
        },
        access_expires_at=_expiry(token.get("expires_in")),
        refresh_expires_at=_expiry(XERO_REFRESH_LIFETIME_SECONDS),
    )

    if len(tenant_summary) == 1:
        chosen = tenant_summary[0]
        connection.external_company_id = chosen["id"]
        connection.external_company_name = chosen["name"]
        connection.status = AccountingConnection.Status.CONNECTED
        connection.last_error = ""
        requires_selection = False
    else:
        connection.external_company_id = ""
        connection.external_company_name = ""
        connection.status = AccountingConnection.Status.DISCONNECTED
        connection.last_error = (
            "Select the Xero organization to connect."
            if tenant_summary
            else "Xero returned no authorized organizations."
        )
        requires_selection = True
    connection.save(
        update_fields=(
            "external_company_id",
            "external_company_name",
            "status",
            "last_error",
            "updated_at",
        )
    )
    return connection, {
        "requiresTenantSelection": requires_selection,
        "tenants": tenant_summary,
    }


def select_xero_tenant(*, connection, tenant_id):
    row, payload = get_provider_credential(
        business=connection.business,
        category="accounting",
        provider=AccountingConnection.Provider.XERO,
        connection=connection,
        required=True,
    )
    tenant = next(
        (
            item
            for item in payload.get("tenants", [])
            if str(item.get("id")) == str(tenant_id)
        ),
        None,
    )
    if tenant is None:
        raise serializers.ValidationError(
            {"tenantId": "Select an organization returned by Xero."}
        )
    connection.external_company_id = tenant["id"]
    connection.external_company_name = tenant.get("name", "")
    connection.status = AccountingConnection.Status.CONNECTED
    connection.last_error = ""
    connection.save(
        update_fields=(
            "external_company_id",
            "external_company_name",
            "status",
            "last_error",
            "updated_at",
        )
    )
    touch_provider_credential(row)
    return connection


def test_accounting_connection(connection):
    row, _payload, access_token = accounting_access_token(connection)
    if connection.provider == AccountingConnection.Provider.QUICKBOOKS:
        if not connection.external_company_id:
            raise serializers.ValidationError(
                {"provider": "QuickBooks company ID is not available."}
            )
        name = _quickbooks_company_info(
            realm_id=connection.external_company_id,
            access_token=access_token,
        )
        connection.external_company_name = name or connection.external_company_name
    else:
        tenants = _xero_connections(access_token)
        if not any(
            str(item.get("tenantId")) == connection.external_company_id
            for item in tenants
        ):
            raise serializers.ValidationError(
                {"provider": "The selected Xero organization is no longer authorized."}
            )

    connection.status = AccountingConnection.Status.CONNECTED
    connection.last_error = ""
    connection.save(
        update_fields=(
            "external_company_name",
            "status",
            "last_error",
            "updated_at",
        )
    )
    touch_provider_credential(row)
    return connection


def disconnect_accounting_connection(connection):
    row, payload = get_provider_credential(
        business=connection.business,
        category="accounting",
        provider=connection.provider,
        connection=connection,
    )
    if row and payload:
        token = payload.get("refresh_token") or payload.get("access_token")
        if token:
            try:
                if connection.provider == AccountingConnection.Provider.QUICKBOOKS:
                    requests.post(
                        QUICKBOOKS_REVOKE_URL,
                        auth=(
                            settings.QUICKBOOKS_CLIENT_ID,
                            settings.QUICKBOOKS_CLIENT_SECRET,
                        ),
                        json={"token": token},
                        timeout=15,
                    )
                else:
                    requests.post(
                        XERO_REVOKE_URL,
                        auth=(settings.XERO_CLIENT_ID, settings.XERO_CLIENT_SECRET),
                        data={"token": token},
                        timeout=15,
                    )
            except requests.RequestException:
                # Local encrypted credentials are still deleted so StockFlow no
                # longer retains access if the provider revoke call is unavailable.
                pass

    delete_provider_credential(
        business=connection.business,
        category="accounting",
        provider=connection.provider,
        connection=connection,
    )
    connection.status = AccountingConnection.Status.DISCONNECTED
    connection.external_company_id = ""
    connection.external_company_name = ""
    connection.last_error = ""
    connection.save(
        update_fields=(
            "status",
            "external_company_id",
            "external_company_name",
            "last_error",
            "updated_at",
        )
    )
    return connection
