from django.db import transaction
from django.db.models import IntegerField, Prefetch, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from businesses.access import get_business_and_role_for_user
from businesses.branch_access import resolve_branch_for_user
from businesses.models import BusinessMembership
from .branch_service import (
    apply_locked_branch_change,
    locked_branch_inventory_map,
)
from .models import BranchInventory, BranchStockMovement, Product, StockMovement
from .serializers import (
    ProductSerializer,
    ProductStatusSerializer,
    StockAdjustmentSerializer,
    StockMovementSerializer,
)


def product_inventory_summary_queryset(queryset, *, branch=None):
    movement_filter = Q(
        stock_movements__movement_type=StockMovement.MovementType.SALE
    )
    if branch is not None:
        movement_filter &= Q(stock_movements__branch=branch)
        queryset = queryset.prefetch_related(
            Prefetch(
                "branch_inventories",
                queryset=BranchInventory.objects.filter(branch=branch),
                to_attr="selected_branch_inventory",
            )
        )

    return queryset.annotate(
        quantity_sold=-1 * Coalesce(
            Sum("stock_movements__quantity", filter=movement_filter),
            Value(0),
            output_field=IntegerField(),
        )
    )


class BusinessProductAccessMixin:
    # Resolves one business visible to the authenticated user.

    def get_business_and_role(self):
        if hasattr(self, "_business_and_role"):
            return self._business_and_role

        self._business_and_role = get_business_and_role_for_user(
            user=self.request.user,
            business_id=self.kwargs["business_id"],
        )
        return self._business_and_role

    def get_branch(self):
        if hasattr(self, "_selected_branch"):
            return self._selected_branch
        business, role = self.get_business_and_role()
        branch_id = (
            self.request.query_params.get("branchId")
            or self.request.data.get("branchId")
        )
        self._selected_branch = resolve_branch_for_user(
            business=business,
            user=self.request.user,
            role=role,
            branch_id=branch_id,
        )
        return self._selected_branch

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
            "branch": self.get_branch(),
        }

    def get_product(self):
        # Resolves active or inactive products inside the current business.
        business, _ = self.get_business_and_role()

        return get_object_or_404(
            product_inventory_summary_queryset(
                Product.objects.select_related("business"),
                branch=self.get_branch(),
            ),
            pk=self.kwargs["product_id"],
            business=business,
        )


class BusinessProductListCreateAPIView(
    BusinessProductAccessMixin,
    APIView,
):
    # Lists active products and creates products inside one business.

    permission_classes = (IsAuthenticated,)

    def get(self, request, business_id):
        business, _ = self.get_business_and_role()

        products = product_inventory_summary_queryset(
            Product.objects.filter(
                business=business,
            ).select_related("business"),
            branch=self.get_branch(),
        ).order_by("-is_active", "name", "sku")

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
        product = self.get_product()

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

        product = self.get_product()
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

        product = self.get_product()
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

        product = self.get_product()

        # Soft deletion protects future invoice and sales-history links.
        product.is_active = False
        product.save(update_fields=("is_active", "updated_at"))

        return Response(status=status.HTTP_204_NO_CONTENT)



class ProductStatusAPIView(
    BusinessProductAccessMixin,
    APIView,
):
    # Lets only owners and managers deactivate or restore a product.

    permission_classes = (IsAuthenticated,)

    def patch(self, request, business_id, product_id):
        _, role = self.get_business_and_role()

        if role not in (
            BusinessMembership.Role.OWNER,
            BusinessMembership.Role.MANAGER,
        ):
            return Response(
                {
                    "detail": (
                        "Only the business owner or manager can "
                        "change a product's active status."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        product = self.get_product()
        serializer = ProductStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product.is_active = serializer.validated_data["isActive"]
        product.save(update_fields=("is_active", "updated_at"))

        return Response(
            ProductSerializer(
                product,
                context=self.get_serializer_context(),
            ).data
        )


class BusinessStockMovementListAPIView(
    BusinessProductAccessMixin,
    APIView,
):
    # Lists the authenticated user's business-isolated stock history.

    permission_classes = (IsAuthenticated,)

    def get(self, request, business_id):
        business, _ = self.get_business_and_role()

        movements = (
            StockMovement.objects.filter(
                business=business,
                branch=self.get_branch(),
            )
            .select_related(
                "business",
                "branch",
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

        branch = self.get_branch()
        branch_inventory = locked_branch_inventory_map(
            branch=branch, products=[product]
        )[product.id]

        movement_map = {
            StockMovement.MovementType.STOCK_IN: BranchStockMovement.MovementType.STOCK_IN,
            StockMovement.MovementType.ADJUSTMENT: BranchStockMovement.MovementType.ADJUSTMENT,
            StockMovement.MovementType.DAMAGE: BranchStockMovement.MovementType.DAMAGE,
            StockMovement.MovementType.RETURN: BranchStockMovement.MovementType.RETURN,
        }
        try:
            movement, _ = apply_locked_branch_change(
                business=business,
                branch=branch,
                product=product,
                branch_inventory=branch_inventory,
                stock_delta=data["quantity"],
                reserved_delta=0,
                movement_type=movement_map[data["type"]],
                reason=data["reason"],
                user=request.user,
                business_movement_type=data["type"],
            )
        except serializers.ValidationError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)

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

