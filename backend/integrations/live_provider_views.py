from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from businesses.access import get_business_and_role_for_user
from businesses.models import BusinessMembership

from .accounting.live import (
    accounting_authorization_url,
    complete_accounting_oauth,
    disconnect_accounting_connection,
    select_xero_tenant,
    test_accounting_connection,
)
from .commerce.live import (
    complete_shopify_oauth,
    disconnect_commerce_connection,
    save_woocommerce_credentials,
    shopify_authorization_url,
    test_commerce_connection,
)
from .messaging.provider import MessagingProviderError
from .messaging.service import delivery_payload, send_test_whatsapp
from .messaging.whatsapp_live import (
    delete_whatsapp_credentials,
    save_whatsapp_credentials,
    whatsapp_configured,
)
from .models import AccountingConnection, CommerceConnection


def _owner_business(request, business_id):
    business, role = get_business_and_role_for_user(
        user=request.user,
        business_id=business_id,
    )
    if role != BusinessMembership.Role.OWNER:
        raise PermissionDenied(
            "Only the business owner can manage live provider credentials."
        )
    return business


def _accounting_payload(row):
    return {
        "id": str(row.id),
        "provider": row.provider,
        "name": row.name,
        "status": row.status,
        "externalCompanyId": row.external_company_id,
        "externalCompanyName": row.external_company_name,
        "lastSyncedAt": row.last_synced_at,
        "lastError": row.last_error,
    }


def _commerce_payload(row):
    return {
        "id": str(row.id),
        "provider": row.provider,
        "name": row.name,
        "shopUrl": row.shop_url,
        "status": row.status,
        "lastSyncedAt": row.last_synced_at,
        "lastError": row.last_error,
    }


class OwnerIntegrationAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "integration_admin"


class AccountingAuthorizeAPIView(OwnerIntegrationAPIView):
    def get(self, request, business_id, connection_id):
        business = _owner_business(request, business_id)
        connection = get_object_or_404(
            AccountingConnection,
            id=connection_id,
            business=business,
        )
        return Response(
            {
                "provider": connection.provider,
                "authorizationUrl": accounting_authorization_url(
                    connection=connection,
                    request=request,
                ),
                "credentialsReturnedToClient": False,
            }
        )


class ProviderCallbackAPIView(APIView):
    permission_classes = (AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "integration_admin"


class AccountingOAuthCallbackAPIView(ProviderCallbackAPIView):
    def get(self, request, provider):
        if provider not in AccountingConnection.Provider.values:
            return Response(
                {"detail": "Unsupported accounting provider."},
                status=status.HTTP_404_NOT_FOUND,
            )
        query = request.query_params.copy()
        query["_stockflow_callback_uri"] = request.build_absolute_uri(
            reverse(
                "integrations:accounting-oauth-callback",
                kwargs={"provider": provider},
            )
        )
        connection, extra = complete_accounting_oauth(
            provider=provider,
            query_params=query,
        )
        return Response(
            {
                "connection": _accounting_payload(connection),
                **extra,
                "credentialsReturnedToClient": False,
            }
        )


class XeroTenantSerializer(serializers.Serializer):
    tenantId = serializers.CharField(max_length=120)


class AccountingTenantSelectAPIView(OwnerIntegrationAPIView):
    def post(self, request, business_id, connection_id):
        business = _owner_business(request, business_id)
        connection = get_object_or_404(
            AccountingConnection,
            id=connection_id,
            business=business,
            provider=AccountingConnection.Provider.XERO,
        )
        serializer = XeroTenantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        connection = select_xero_tenant(
            connection=connection,
            tenant_id=serializer.validated_data["tenantId"],
        )
        return Response(_accounting_payload(connection))


class AccountingConnectionTestAPIView(OwnerIntegrationAPIView):
    def post(self, request, business_id, connection_id):
        business = _owner_business(request, business_id)
        connection = get_object_or_404(
            AccountingConnection,
            id=connection_id,
            business=business,
        )
        return Response(_accounting_payload(test_accounting_connection(connection)))


class AccountingConnectionDisconnectAPIView(OwnerIntegrationAPIView):
    def post(self, request, business_id, connection_id):
        business = _owner_business(request, business_id)
        connection = get_object_or_404(
            AccountingConnection,
            id=connection_id,
            business=business,
        )
        return Response(
            _accounting_payload(disconnect_accounting_connection(connection))
        )


class CommerceAuthorizeAPIView(OwnerIntegrationAPIView):
    def get(self, request, business_id, connection_id):
        business = _owner_business(request, business_id)
        connection = get_object_or_404(
            CommerceConnection,
            id=connection_id,
            business=business,
        )
        if connection.provider != CommerceConnection.Provider.SHOPIFY:
            raise serializers.ValidationError(
                {
                    "provider": (
                        "WooCommerce uses encrypted REST API credentials "
                        "instead of the Shopify OAuth flow."
                    )
                }
            )
        return Response(
            {
                "provider": connection.provider,
                "authorizationUrl": shopify_authorization_url(
                    connection=connection,
                    request=request,
                ),
                "credentialsReturnedToClient": False,
            }
        )


class ShopifyOAuthCallbackAPIView(ProviderCallbackAPIView):
    def get(self, request):
        connection = complete_shopify_oauth(query_params=request.query_params)
        return Response(
            {
                "connection": _commerce_payload(connection),
                "credentialsReturnedToClient": False,
            }
        )


class WooCommerceCredentialSerializer(serializers.Serializer):
    consumerKey = serializers.CharField(
        max_length=255,
        trim_whitespace=False,
        write_only=True,
    )
    consumerSecret = serializers.CharField(
        max_length=255,
        trim_whitespace=False,
        write_only=True,
    )


class WooCommerceCredentialAPIView(OwnerIntegrationAPIView):
    def put(self, request, business_id, connection_id):
        business = _owner_business(request, business_id)
        connection = get_object_or_404(
            CommerceConnection,
            id=connection_id,
            business=business,
            provider=CommerceConnection.Provider.WOOCOMMERCE,
        )
        serializer = WooCommerceCredentialSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        connection = save_woocommerce_credentials(
            connection=connection,
            consumer_key=serializer.validated_data["consumerKey"],
            consumer_secret=serializer.validated_data["consumerSecret"],
            created_by=request.user,
        )
        return Response(
            {
                "connection": _commerce_payload(connection),
                "credentialsReturnedToClient": False,
            }
        )

    post = put


class CommerceConnectionTestAPIView(OwnerIntegrationAPIView):
    def post(self, request, business_id, connection_id):
        business = _owner_business(request, business_id)
        connection = get_object_or_404(
            CommerceConnection,
            id=connection_id,
            business=business,
        )
        return Response(_commerce_payload(test_commerce_connection(connection)))


class CommerceConnectionDisconnectAPIView(OwnerIntegrationAPIView):
    def post(self, request, business_id, connection_id):
        business = _owner_business(request, business_id)
        connection = get_object_or_404(
            CommerceConnection,
            id=connection_id,
            business=business,
        )
        return Response(_commerce_payload(disconnect_commerce_connection(connection)))


class WhatsAppCredentialSerializer(serializers.Serializer):
    accessToken = serializers.CharField(
        max_length=4096,
        trim_whitespace=False,
        write_only=True,
    )
    phoneNumberId = serializers.CharField(max_length=120, write_only=True)
    apiVersion = serializers.CharField(max_length=20, write_only=True)


class WhatsAppCredentialAPIView(OwnerIntegrationAPIView):
    def get(self, request, business_id):
        business = _owner_business(request, business_id)
        return Response(
            {
                "provider": "whatsapp_cloud_api",
                "configured": whatsapp_configured(business),
                "credentialsReturnedToClient": False,
            }
        )

    def put(self, request, business_id):
        business = _owner_business(request, business_id)
        serializer = WhatsAppCredentialSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        save_whatsapp_credentials(
            business=business,
            access_token=serializer.validated_data["accessToken"],
            phone_number_id=serializer.validated_data["phoneNumberId"],
            api_version=serializer.validated_data["apiVersion"],
            created_by=request.user,
        )
        return Response(
            {
                "provider": "whatsapp_cloud_api",
                "configured": True,
                "credentialsReturnedToClient": False,
            }
        )

    def delete(self, request, business_id):
        business = _owner_business(request, business_id)
        delete_whatsapp_credentials(business=business)
        return Response(
            {
                "provider": "whatsapp_cloud_api",
                "configured": False,
                "credentialsReturnedToClient": False,
            }
        )


class WhatsAppTestSerializer(serializers.Serializer):
    recipient = serializers.CharField(max_length=40)
    message = serializers.CharField(max_length=4096)


class WhatsAppTestAPIView(OwnerIntegrationAPIView):
    def post(self, request, business_id):
        business = _owner_business(request, business_id)
        serializer = WhatsAppTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            delivery = send_test_whatsapp(
                business=business,
                recipient=serializer.validated_data["recipient"],
                message=serializer.validated_data["message"],
            )
        except (ValueError, MessagingProviderError) as exc:
            raise serializers.ValidationError({"provider": str(exc)}) from exc
        response_status = (
            status.HTTP_201_CREATED
            if delivery.status == delivery.Status.SENT
            else status.HTTP_502_BAD_GATEWAY
        )
        return Response(delivery_payload(delivery), status=response_status)
