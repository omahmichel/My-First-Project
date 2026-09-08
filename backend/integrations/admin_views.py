from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from businesses.access import get_business_and_role_for_user
from businesses.models import BusinessMembership

from .accounting.registry import accounting_capabilities
from .admin_serializers import (
    API_SCOPES,
    WEBHOOK_EVENTS,
    AccountingConnectionWriteSerializer,
    ApiCredentialCreateSerializer,
    WebhookEndpointWriteSerializer,
)
from .models import AccountingConnection, ApiCredential, WebhookEndpoint
from .security import generate_api_key_material
from .webhooks.service import endpoint_signing_secret, queue_test_delivery


def _owner_business(request, business_id):
    business, role = get_business_and_role_for_user(
        user=request.user, business_id=business_id
    )
    if role != BusinessMembership.Role.OWNER:
        raise PermissionDenied(
            "Only the business owner can manage external integrations."
        )
    return business


class IntegrationAdminAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "integration_admin"


def _credential_payload(row):
    return {
        "id": str(row.id), "name": row.name, "keyPrefix": row.key_prefix,
        "scopes": row.scopes, "isActive": bool(row.is_active and not row.revoked_at),
        "expiresAt": row.expires_at, "lastUsedAt": row.last_used_at,
        "createdAt": row.created_at,
    }


class ApiCredentialCollectionAPIView(IntegrationAdminAPIView):
    def get(self, request, business_id):
        business = _owner_business(request, business_id)
        rows = ApiCredential.objects.filter(business=business)
        return Response({
            "supportedScopes": list(API_SCOPES),
            "credentials": [_credential_payload(row) for row in rows],
        })

    def post(self, request, business_id):
        business = _owner_business(request, business_id)
        serializer = ApiCredentialCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        key_prefix, raw_key, secret_hash = generate_api_key_material()
        row = ApiCredential.objects.create(
            business=business, name=serializer.validated_data["name"],
            key_prefix=key_prefix, secret_hash=secret_hash,
            scopes=serializer.validated_data["scopes"],
            expires_at=serializer.validated_data.get("expiresAt"),
            created_by=request.user,
        )
        payload = _credential_payload(row)
        payload.update({"apiKey": raw_key, "apiKeyShownOnce": True})
        return Response(payload, status=status.HTTP_201_CREATED)


class ApiCredentialRevokeAPIView(IntegrationAdminAPIView):
    def post(self, request, business_id, credential_id):
        business = _owner_business(request, business_id)
        row = get_object_or_404(ApiCredential, id=credential_id, business=business)
        if not row.revoked_at:
            row.revoked_at = timezone.now()
            row.is_active = False
            row.save(update_fields=("revoked_at", "is_active", "updated_at"))
        return Response(_credential_payload(row))


def _endpoint_payload(row):
    return {
        "id": str(row.id), "name": row.name, "url": row.url,
        "events": row.events, "isActive": row.is_active,
        "createdAt": row.created_at, "updatedAt": row.updated_at,
    }


class WebhookEndpointCollectionAPIView(IntegrationAdminAPIView):
    def get(self, request, business_id):
        business = _owner_business(request, business_id)
        rows = WebhookEndpoint.objects.filter(business=business)
        return Response({
            "supportedEvents": list(WEBHOOK_EVENTS),
            "endpoints": [_endpoint_payload(row) for row in rows],
        })

    def post(self, request, business_id):
        business = _owner_business(request, business_id)
        serializer = WebhookEndpointWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = WebhookEndpoint.objects.create(
            business=business, name=serializer.validated_data["name"],
            url=serializer.validated_data["url"],
            events=serializer.validated_data["events"],
            is_active=serializer.validated_data.get("isActive", True),
            created_by=request.user,
        )
        payload = _endpoint_payload(row)
        payload.update({
            "signingSecret": endpoint_signing_secret(row),
            "signingSecretShownOnce": True,
        })
        return Response(payload, status=status.HTTP_201_CREATED)


class WebhookEndpointDetailAPIView(IntegrationAdminAPIView):
    def patch(self, request, business_id, endpoint_id):
        business = _owner_business(request, business_id)
        row = get_object_or_404(WebhookEndpoint, id=endpoint_id, business=business)
        serializer = WebhookEndpointWriteSerializer(data={
            "name": request.data.get("name", row.name),
            "url": request.data.get("url", row.url),
            "events": request.data.get("events", row.events),
            "isActive": request.data.get("isActive", row.is_active),
        })
        serializer.is_valid(raise_exception=True)
        row.name = serializer.validated_data["name"]
        row.url = serializer.validated_data["url"]
        row.events = serializer.validated_data["events"]
        row.is_active = serializer.validated_data["isActive"]
        row.save()
        return Response(_endpoint_payload(row))


class WebhookEndpointTestAPIView(IntegrationAdminAPIView):
    def post(self, request, business_id, endpoint_id):
        business = _owner_business(request, business_id)
        endpoint = get_object_or_404(
            WebhookEndpoint, id=endpoint_id, business=business, is_active=True
        )
        delivery = queue_test_delivery(endpoint)
        return Response({
            "queued": True, "deliveryId": str(delivery.id),
            "event": delivery.event.event_type,
        }, status=status.HTTP_202_ACCEPTED)


def _connection_payload(row):
    return {
        "id": str(row.id), "provider": row.provider, "name": row.name,
        "status": row.status, "externalCompanyId": row.external_company_id,
        "externalCompanyName": row.external_company_name,
        "settings": row.settings, "lastSyncedAt": row.last_synced_at,
        "lastError": row.last_error, "createdAt": row.created_at,
        "updatedAt": row.updated_at,
    }


class AccountingCapabilityAPIView(IntegrationAdminAPIView):
    def get(self, request, business_id):
        _owner_business(request, business_id)
        return Response(accounting_capabilities())


class AccountingConnectionCollectionAPIView(IntegrationAdminAPIView):
    def get(self, request, business_id):
        business = _owner_business(request, business_id)
        rows = AccountingConnection.objects.filter(business=business)
        return Response({
            "capabilities": accounting_capabilities(),
            "connections": [_connection_payload(row) for row in rows],
        })

    def post(self, request, business_id):
        business = _owner_business(request, business_id)
        serializer = AccountingConnectionWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = AccountingConnection.objects.create(
            business=business, provider=serializer.validated_data["provider"],
            name=serializer.validated_data["name"],
            settings=serializer.validated_data.get("settings", {}),
            created_by=request.user,
        )
        return Response(_connection_payload(row), status=status.HTTP_201_CREATED)
