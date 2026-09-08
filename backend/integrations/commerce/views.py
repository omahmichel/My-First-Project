from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from businesses.access import get_business_and_role_for_user
from businesses.models import BusinessMembership

from integrations.models import (
    CommerceConnection,
    CommerceExternalReference,
    ExternalCommerceOrder,
)

from .registry import commerce_capabilities
from .serializers import (
    CommerceConnectionWriteSerializer,
    CommerceProductMappingSerializer,
    ExternalCommerceOrderStageSerializer,
)
from .service import order_payload, stage_external_order, upsert_product_mapping


def _owner_business(request, business_id):
    business, role = get_business_and_role_for_user(
        user=request.user,
        business_id=business_id,
    )
    if role != BusinessMembership.Role.OWNER:
        raise PermissionDenied(
            "Only the business owner can manage commerce integrations."
        )
    return business


def _operational_business(request, business_id):
    business, role = get_business_and_role_for_user(
        user=request.user,
        business_id=business_id,
    )
    if role not in {
        BusinessMembership.Role.OWNER,
        BusinessMembership.Role.MANAGER,
    }:
        raise PermissionDenied(
            "Your role does not allow external order review."
        )
    return business


class CommerceAdminAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "integration_admin"


def _connection_payload(row):
    return {
        "id": str(row.id),
        "provider": row.provider,
        "name": row.name,
        "shopUrl": row.shop_url,
        "status": row.status,
        "settings": row.settings,
        "lastSyncedAt": row.last_synced_at,
        "lastError": row.last_error,
        "createdAt": row.created_at,
        "updatedAt": row.updated_at,
    }


class CommerceCapabilitiesAPIView(CommerceAdminAPIView):
    def get(self, request, business_id):
        _owner_business(request, business_id)
        return Response(commerce_capabilities())


class CommerceConnectionCollectionAPIView(CommerceAdminAPIView):
    def get(self, request, business_id):
        business = _owner_business(request, business_id)
        rows = CommerceConnection.objects.filter(business=business)
        return Response(
            {
                "capabilities": commerce_capabilities(),
                "connections": [_connection_payload(row) for row in rows],
            }
        )

    def post(self, request, business_id):
        business = _owner_business(request, business_id)
        serializer = CommerceConnectionWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = CommerceConnection.objects.create(
            business=business,
            provider=serializer.validated_data["provider"],
            name=serializer.validated_data["name"],
            shop_url=serializer.validated_data.get("shopUrl", ""),
            settings=serializer.validated_data.get("settings", {}),
            created_by=request.user,
        )
        return Response(
            _connection_payload(row),
            status=status.HTTP_201_CREATED,
        )


class CommerceProductMappingAPIView(CommerceAdminAPIView):
    def get(self, request, business_id, connection_id):
        business = _owner_business(request, business_id)
        connection = get_object_or_404(
            CommerceConnection,
            business=business,
            id=connection_id,
        )
        rows = CommerceExternalReference.objects.filter(
            connection=connection,
            entity_type="product",
        ).order_by("external_id")
        return Response(
            {
                "connectionId": str(connection.id),
                "mappings": [
                    {
                        "id": str(row.id),
                        "externalProductId": row.external_id,
                        "productId": row.stockflow_id,
                        "syncedAt": row.synced_at,
                    }
                    for row in rows
                ],
            }
        )

    def post(self, request, business_id, connection_id):
        business = _owner_business(request, business_id)
        connection = get_object_or_404(
            CommerceConnection,
            business=business,
            id=connection_id,
        )
        serializer = CommerceProductMappingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = upsert_product_mapping(
            business=business,
            connection=connection,
            external_product_id=serializer.validated_data["externalProductId"],
            product_id=serializer.validated_data["productId"],
        )
        return Response(
            {
                "id": str(row.id),
                "externalProductId": row.external_id,
                "productId": row.stockflow_id,
            },
            status=status.HTTP_201_CREATED,
        )


class CommerceOrderCollectionAPIView(CommerceAdminAPIView):
    def get(self, request, business_id):
        business = _operational_business(request, business_id)
        rows = (
            ExternalCommerceOrder.objects.filter(business=business)
            .select_related("connection")
            .prefetch_related("items")
            .order_by("-staged_at")[:200]
        )
        return Response(
            {
                "orders": [order_payload(row) for row in rows],
                "readOnlyStaging": True,
                "stockMutation": False,
                "saleCreation": False,
            }
        )


class CommerceOrderStageAPIView(CommerceAdminAPIView):
    def post(self, request, business_id):
        business = _operational_business(request, business_id)
        serializer = ExternalCommerceOrderStageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order, replay = stage_external_order(
            business=business,
            user=request.user,
            data=serializer.validated_data,
        )
        order = (
            ExternalCommerceOrder.objects.select_related("connection")
            .prefetch_related("items")
            .get(id=order.id)
        )
        payload = order_payload(order)
        payload["idempotentReplay"] = replay
        payload["stockMutation"] = False
        payload["saleCreation"] = False
        return Response(
            payload,
            status=status.HTTP_200_OK if replay else status.HTTP_201_CREATED,
        )
