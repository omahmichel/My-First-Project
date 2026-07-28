from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from businesses.models import Business, BusinessMembership
from .models import Product, StockMovement
from .serializers import (
    ProductSerializer,
    StockAdjustmentSerializer,
    StockMovementSerializer,
)


class BusinessProductAccessMixin:
    # Resolves one business visible to the authenticated user.

    def get_business_and_role(self):
        if hasattr(self, "_business_and_role"):
            return self._business_and_role

        user = self.request.user

        business = get_object_or_404(
            Business.objects.filter(
                Q(owner=user)
                | Q(
                    memberships__user=user,
                    memberships__is_active=True,
                )
            )
            .select_related("owner")
            .distinct(),
            pk=self.kwargs["business_id"],
            status=Business.Status.ACTIVE,
        )

        if business.owner_id == user.id:
            role = BusinessMembership.Role.OWNER
        else:
            membership = get_object_or_404(
                BusinessMembership,
                business=business,
                user=user,
                is_active=True,
            )
            role = membership.role

        self._business_and_role = (business, role)
        return self._business_and_role

    def require_inventory_write_access(self):
        # Owners, managers and inventory clerks can change inventory.
        business, role = self.get_business_and_role()

        if role not in (
            BusinessMembership.Role.OWNER,
            BusinessMembership.Role.MANAGER,
            BusinessMembership.Role.INVENTORY_CLERK,
        ):
            return None, Response(
                {
                    "detail": (
                        "Your role does not allow inventory changes."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        return business, None

    def get_serializer_context(self):
        business, role = self.get_business_and_role()

        return {
            "request": self.request,
            "business": business,
            "current_role": role,
        }

    def get_active_product(self):
        business, _ = self.get_business_and_role()

        return get_object_or_404(
            Product.objects.select_related("business"),
            pk=self.kwargs["product_id"],
            business=business,
            is_active=True,
        )


class BusinessProductListCreateAPIView(
    BusinessProductAccessMixin,
    APIView,
):
    # Lists active products and creates products inside one business.

    permission_classes = (IsAuthenticated,)

    def get(self, request, business_id):
        business, _ = self.get_business_and_role()

        products = (
            Product.objects.filter(
                business=business,
                is_active=True,
            )
            .select_related("business")
            .order_by("name", "sku")
        )

        serializer = ProductSerializer(
            products,
            many=True,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data)

    def post(self, request, business_id):
        business, denied_response = (
            self.require_inventory_write_access()
        )

        if denied_response:
            return denied_response

        serializer = ProductSerializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        product = serializer.save()

        return Response(
            ProductSerializer(
                product,
                context=self.get_serializer_context(),
            ).data,
            status=status.HTTP_201_CREATED,
        )


class BusinessProductDetailAPIView(
    BusinessProductAccessMixin,
    APIView,
):
    # Retrieves, updates or softly deactivates one isolated product.

    permission_classes = (IsAuthenticated,)

    def get(self, request, business_id, product_id):
        product = self.get_active_product()

        return Response(
            ProductSerializer(
                product,
                context=self.get_serializer_context(),
            ).data
        )

    def patch(self, request, business_id, product_id):
        _, denied_response = self.require_inventory_write_access()

        if denied_response:
            return denied_response

        product = self.get_active_product()
        serializer = ProductSerializer(
            product,
            data=request.data,
            partial=True,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)

    def put(self, request, business_id, product_id):
        _, denied_response = self.require_inventory_write_access()

        if denied_response:
            return denied_response

        product = self.get_active_product()
        serializer = ProductSerializer(
            product,
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)

    def delete(self, request, business_id, product_id):
        _, role = self.get_business_and_role()

        if role not in (
            BusinessMembership.Role.OWNER,
            BusinessMembership.Role.MANAGER,
        ):
            return Response(
                {
                    "detail": (
                        "Only the business owner or manager can "
                        "remove a product."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        product = self.get_active_product()

        # Soft deletion protects future invoice and sales-history links.
        product.is_active = False
        product.save(update_fields=("is_active", "updated_at"))

        return Response(status=status.HTTP_204_NO_CONTENT)


class BusinessStockMovementListAPIView(
    BusinessProductAccessMixin,
    APIView,
):
    # Lists the authenticated user's business-isolated stock history.

    permission_classes = (IsAuthenticated,)

    def get(self, request, business_id):
        business, _ = self.get_business_and_role()

        movements = (
            StockMovement.objects.filter(business=business)
            .select_related(
                "business",
                "product",
                "created_by",
            )
            .order_by("-created_at")
        )

        return Response(
            StockMovementSerializer(
                movements,
                many=True,
            ).data
        )


class ProductStockAdjustmentAPIView(
    BusinessProductAccessMixin,
    APIView,
):
    # Changes stock and records the movement in one locked transaction.

    permission_classes = (IsAuthenticated,)

    @transaction.atomic
    def post(self, request, business_id, product_id):
        business, denied_response = (
            self.require_inventory_write_access()
        )

        if denied_response:
            return denied_response

        serializer = StockAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        product = get_object_or_404(
            Product.objects.select_for_update().select_related(
                "business"
            ),
            pk=product_id,
            business=business,
            is_active=True,
        )

        previous_stock = product.stock
        new_stock = previous_stock + data["quantity"]

        if new_stock < 0:
            return Response(
                {
                    "quantity": (
                        "This adjustment would reduce stock below zero."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_stock < product.reserved_stock:
            return Response(
                {
                    "quantity": (
                        "This adjustment would reduce stock below "
                        f"{product.reserved_stock} unit(s) reserved "
                        "for pending payments."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        product.stock = new_stock
        product.save(update_fields=("stock", "updated_at"))

        movement = StockMovement.objects.create(
            business=business,
            product=product,
            movement_type=data["type"],
            quantity=data["quantity"],
            previous_stock=previous_stock,
            new_stock=new_stock,
            reason=data["reason"],
            created_by=request.user,
        )

        return Response(
            {
                "product": ProductSerializer(
                    product,
                    context=self.get_serializer_context(),
                ).data,
                "movement": StockMovementSerializer(movement).data,
            },
            status=status.HTTP_201_CREATED,
        )

