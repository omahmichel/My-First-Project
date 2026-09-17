import hashlib
import hmac
from datetime import timedelta
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponseRedirect
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from businesses.access import get_business_and_role_for_user
from integrations.provider_credentials import (
    delete_provider_credential,
    get_provider_credential,
    save_provider_credential,
)

from .management import owner_business
from .serializers import StrictInputSerializer


PROVIDER = "facebook"
CATEGORY = "social"
STATE_SALT = "stockflow.meta.facebook.business-login.v1"
STATE_MAX_AGE_SECONDS = 600


class MetaConnectionUnavailable(APIException):
    status_code = 503
    default_detail = "Meta connection is not configured for this StockFlow environment."


def _require_meta_settings():
    values = {
        "app_id": settings.META_APP_ID,
        "app_secret": settings.META_APP_SECRET,
        "config_id": settings.META_FACEBOOK_CONFIG_ID,
        "redirect_uri": settings.META_FACEBOOK_REDIRECT_URI,
        "version": settings.META_GRAPH_API_VERSION,
        "return_url": settings.META_SOCIAL_RETURN_URL,
    }
    if not all(values.values()):
        raise MetaConnectionUnavailable()
    return values


def _appsecret_proof(access_token):
    secret = settings.META_APP_SECRET.encode("utf-8")
    return hmac.new(secret, str(access_token).encode("utf-8"), hashlib.sha256).hexdigest()


def _graph_url(path):
    return f"https://graph.facebook.com/{settings.META_GRAPH_API_VERSION}/{path.lstrip('/')}"


def _safe_meta_error(response, fallback):
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    error = payload.get("error") if isinstance(payload, dict) else None
    code = error.get("code") if isinstance(error, dict) else None
    return f"{fallback}{f' (Meta code {code})' if code is not None else ''}."


def _fetch_pages(system_access_token, include_tokens=False):
    fields = "id,name,tasks,instagram_business_account" + (",access_token" if include_tokens else "")
    try:
        response = requests.get(
            _graph_url("me/accounts"),
            params={
                "fields": fields,
                "limit": 100,
                "access_token": system_access_token,
                "appsecret_proof": _appsecret_proof(system_access_token),
            },
            timeout=20,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        raise ValidationError(
            {"facebook": "Meta could not be reached while reading the authorized Pages."}
        ) from exc

    if not 200 <= response.status_code < 300:
        raise ValidationError(
            {"facebook": _safe_meta_error(response, "Meta rejected the Page lookup")}
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise ValidationError({"facebook": "Meta returned an invalid Page response."}) from exc

    pages = data.get("data") if isinstance(data, dict) else None
    if not isinstance(pages, list):
        raise ValidationError({"facebook": "Meta did not return a valid Page list."})

    normalized = []
    for page in pages:
        if not isinstance(page, dict):
            continue
        page_id = str(page.get("id", "")).strip()
        name = str(page.get("name", "")).strip()
        if not page_id or not name:
            continue
        item = {
            "id": page_id[:80],
            "name": name[:180],
            "tasks": [str(task)[:60] for task in page.get("tasks", []) if task],
        }
        instagram_account = page.get("instagram_business_account")
        if isinstance(instagram_account, dict) and instagram_account.get("id"):
            item["instagram_account_id"] = str(instagram_account["id"])[:80]
        if include_tokens and page.get("access_token"):
            item["access_token"] = str(page["access_token"])
        normalized.append(item)
    return normalized


def _fetch_instagram_profile(page_access_token, instagram_account_id):
    if not page_access_token or not instagram_account_id:
        return {}
    try:
        response = requests.get(
            _graph_url(str(instagram_account_id)),
            params={
                "fields": "id,username",
                "access_token": page_access_token,
                "appsecret_proof": _appsecret_proof(page_access_token),
            },
            timeout=20,
            allow_redirects=False,
        )
    except requests.RequestException:
        return {"id": str(instagram_account_id)[:80], "username": ""}

    if not 200 <= response.status_code < 300:
        return {"id": str(instagram_account_id)[:80], "username": ""}

    try:
        data = response.json()
    except ValueError:
        return {"id": str(instagram_account_id)[:80], "username": ""}

    if not isinstance(data, dict):
        return {"id": str(instagram_account_id)[:80], "username": ""}

    return {
        "id": str(data.get("id") or instagram_account_id)[:80],
        "username": str(data.get("username", "")).strip()[:180],
    }


def _selected_page_payload(page):
    result = {
        "page_id": page["id"],
        "page_name": page["name"],
        "page_access_token": page.get("access_token", ""),
    }
    instagram_account_id = str(page.get("instagram_account_id", "")).strip()
    if instagram_account_id and result["page_access_token"]:
        instagram = _fetch_instagram_profile(
            result["page_access_token"],
            instagram_account_id,
        )
        result["instagram_account_id"] = instagram.get("id", instagram_account_id)
        result["instagram_username"] = instagram.get("username", "")
    return result


def _credential(business):
    return get_provider_credential(
        business=business,
        category=CATEGORY,
        provider=PROVIDER,
    )


def _connection_base():
    return {
        "connectionStatus": "not_connected",
        "deliveryAvailable": False,
        "accountName": "",
        "availableAccounts": [],
    }


def facebook_connection_summary(business):
    row, payload = _credential(business)
    base = _connection_base()
    if row is None or not payload:
        return base

    if row.access_expires_at and row.access_expires_at <= timezone.now():
        return {**base, "connectionStatus": "expired"}

    page_id = str(payload.get("page_id", "")).strip()
    page_name = str(payload.get("page_name", "")).strip()
    if page_id and payload.get("page_access_token"):
        return {
            **base,
            "connectionStatus": "connected",
            "deliveryAvailable": True,
            "accountName": page_name,
        }

    candidates = payload.get("candidate_pages")
    if isinstance(candidates, list) and candidates:
        safe_candidates = [
            {"id": str(item.get("id", ""))[:80], "name": str(item.get("name", ""))[:180]}
            for item in candidates
            if isinstance(item, dict) and item.get("id") and item.get("name")
        ]
        if safe_candidates:
            return {
                **base,
                "connectionStatus": "selection_required",
                "availableAccounts": safe_candidates,
            }
    return base


def instagram_connection_summary(business):
    row, payload = _credential(business)
    base = _connection_base()
    if row is None or not payload:
        return base

    if row.access_expires_at and row.access_expires_at <= timezone.now():
        return {**base, "connectionStatus": "expired"}

    page_id = str(payload.get("page_id", "")).strip()
    page_access_token = str(payload.get("page_access_token", "")).strip()
    instagram_account_id = str(payload.get("instagram_account_id", "")).strip()
    instagram_username = str(payload.get("instagram_username", "")).strip()

    if page_id and page_access_token and instagram_account_id:
        return {
            **base,
            "connectionStatus": "connected",
            "deliveryAvailable": True,
            "accountName": instagram_username or "Instagram professional account",
        }
    return base


def _signed_state(*, business, user):
    return signing.dumps(
        {"business_id": str(business.id), "user_id": str(user.pk)},
        salt=STATE_SALT,
        compress=True,
    )


def _return_redirect(status):
    config = _require_meta_settings()
    separator = "&" if "?" in config["return_url"] else "?"
    return HttpResponseRedirect(
        config["return_url"] + separator + urlencode({"social": status})
    )


def _owner_from_state(raw_state):
    try:
        data = signing.loads(
            raw_state,
            salt=STATE_SALT,
            max_age=STATE_MAX_AGE_SECONDS,
        )
    except signing.BadSignature as exc:
        raise PermissionDenied("The Meta connection request is invalid or expired.") from exc

    user = get_user_model().objects.filter(pk=data.get("user_id")).first()
    if user is None:
        raise PermissionDenied("The StockFlow user for this Meta connection no longer exists.")
    business, role = get_business_and_role_for_user(
        user=user,
        business_id=data.get("business_id"),
    )
    if role != "owner":
        raise PermissionDenied("Only the business owner can connect a Facebook Page.")
    return user, business


class FacebookConnectAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, business_id):
        business = owner_business(request, business_id)
        config = _require_meta_settings()
        params = {
            "client_id": config["app_id"],
            "redirect_uri": config["redirect_uri"],
            "config_id": config["config_id"],
            "response_type": "code",
            "override_default_response_type": "true",
            "state": _signed_state(business=business, user=request.user),
        }
        response = Response({
            "authorizeUrl": (
                f"https://www.facebook.com/{config['version']}/dialog/oauth?"
                + urlencode(params)
            )
        })
        response["Cache-Control"] = "no-store"
        return response


class FacebookOAuthCallbackAPIView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get(self, request):
        if request.query_params.get("error"):
            return _return_redirect("facebook-cancelled")

        code = str(request.query_params.get("code", "")).strip()
        state = str(request.query_params.get("state", "")).strip()
        if not code or not state:
            return _return_redirect("facebook-error")

        try:
            user, business = _owner_from_state(state)
            config = _require_meta_settings()
            response = requests.get(
                _graph_url("oauth/access_token"),
                params={
                    "client_id": config["app_id"],
                    "client_secret": config["app_secret"],
                    "redirect_uri": config["redirect_uri"],
                    "code": code,
                },
                timeout=20,
                allow_redirects=False,
            )
            if not 200 <= response.status_code < 300:
                return _return_redirect("facebook-error")

            try:
                token_data = response.json()
            except ValueError:
                return _return_redirect("facebook-error")

            system_token = str(token_data.get("access_token", "")).strip()
            if not system_token:
                return _return_redirect("facebook-error")

            expires_in = token_data.get("expires_in")
            try:
                expires_at = (
                    timezone.now() + timedelta(seconds=int(expires_in))
                    if int(expires_in or 0) > 0 else None
                )
            except (TypeError, ValueError):
                expires_at = None

            pages = _fetch_pages(system_token, include_tokens=True)
            if not pages:
                return _return_redirect("facebook-no-pages")

            safe_candidates = [
                {"id": page["id"], "name": page["name"], "tasks": page.get("tasks", [])}
                for page in pages
            ]
            payload = {
                "system_access_token": system_token,
                "candidate_pages": safe_candidates,
                "graph_api_version": config["version"],
            }
            result = "facebook-select-page"
            if len(pages) == 1:
                payload.update(_selected_page_payload(pages[0]))
                if payload["page_access_token"]:
                    result = "facebook-connected"

            save_provider_credential(
                business=business,
                category=CATEGORY,
                provider=PROVIDER,
                payload=payload,
                created_by=user,
                access_expires_at=expires_at,
            )
            return _return_redirect(result)
        except (PermissionDenied, ValidationError, ImproperlyConfigured):
            return _return_redirect("facebook-error")
        except requests.RequestException:
            return _return_redirect("facebook-error")


class FacebookPageSelectionInput(StrictInputSerializer):
    pageId = serializers.CharField(max_length=80)


class FacebookPageSelectionAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, business_id):
        business = owner_business(request, business_id)
        serializer = FacebookPageSelectionInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        page_id = serializer.validated_data["pageId"].strip()

        row, payload = _credential(business)
        if row is None or not payload:
            raise ValidationError({"facebook": "Connect Facebook before choosing a Page."})
        if row.access_expires_at and row.access_expires_at <= timezone.now():
            raise ValidationError({"facebook": "The Meta authorization has expired. Reconnect Facebook."})

        candidates = payload.get("candidate_pages") or []
        allowed_ids = {
            str(item.get("id"))
            for item in candidates
            if isinstance(item, dict) and item.get("id")
        }
        if page_id not in allowed_ids:
            raise ValidationError({"pageId": "Choose a Page returned by the current Meta authorization."})

        pages = _fetch_pages(payload["system_access_token"], include_tokens=True)
        chosen = next((page for page in pages if page["id"] == page_id), None)
        if chosen is None or not chosen.get("access_token"):
            raise ValidationError({"pageId": "Meta no longer grants access to that Page."})

        replacement = {
            **payload,
            **_selected_page_payload(chosen),
        }
        save_provider_credential(
            business=business,
            category=CATEGORY,
            provider=PROVIDER,
            payload=replacement,
            created_by=request.user,
            access_expires_at=row.access_expires_at,
            refresh_expires_at=row.refresh_expires_at,
        )
        response = Response(facebook_connection_summary(business))
        response["Cache-Control"] = "no-store"
        return response


class FacebookDisconnectAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def delete(self, request, business_id):
        business = owner_business(request, business_id)
        delete_provider_credential(
            business=business,
            category=CATEGORY,
            provider=PROVIDER,
        )
        return Response(status=204)
