from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from businesses.access import get_business_and_role_for_user
from businesses.branch_access import resolve_branch_for_user
from businesses.models import BusinessMembership

from .restock_models import RestockPurchase, Supplier
from .restock_serializers import (
    RestockCreateSerializer,
    RestockPaymentCreateSerializer,
    RestockPurchaseSerializer,
    SupplierSerializer,
)
from .restock_service import create_restock, record_payment


ALLOWED_ROLES = (
    BusinessMembership.Role.OWNER,
    BusinessMembership.Role.MANAGER,
    BusinessMembership.Role.INVENTORY_CLERK,
)


class RestockAccessMixin:
    def get_business_and_role(self):
        if hasattr(self, "_restock_business_role"):
            return self._restock_business_role
        business, role = get_business_and_role_for_user(
            user=self.request.user,
            business_id=self.kwargs["business_id"],
        )
        if role not in ALLOWED_ROLES:
            raise PermissionDenied(
                "Your role does not allow supplier or restocking access."
            )
        self._restock_business_role = (business, role)
        return self._restock_business_role

    def get_business(self):
        return self.get_business_and_role()[0]

    def get_branch(self, branch_id=None):
        business, role = self.get_business_and_role()
        requested_id = (
            branch_id
            or self.request.query_params.get("branchId")
            or self.request.data.get("branchId")
        )
        return resolve_branch_for_user(
            business=business,
            user=self.request.user,
            role=role,
            branch_id=requested_id,
        )


class BusinessSupplierListCreateAPIView(RestockAccessMixin, APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, business_id):
        suppliers = (
            Supplier.objects.filter(business=self.get_business())
            .prefetch_related("restock_purchases")
            .order_by("-is_active", "name")
        )
        return Response(SupplierSerializer(suppliers, many=True).data)

    def post(self, request, business_id):
        serializer = SupplierSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        supplier = serializer.save(business=self.get_business())
        return Response(
            SupplierSerializer(supplier).data,
            status=status.HTTP_201_CREATED,
        )


class BusinessSupplierDetailAPIView(RestockAccessMixin, APIView):
    permission_classes = (IsAuthenticated,)

    def supplier(self):
        return get_object_or_404(
            Supplier,
            pk=self.kwargs["supplier_id"],
            business=self.get_business(),
        )

    def patch(self, request, business_id, supplier_id):
        serializer = SupplierSerializer(
            self.supplier(), data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        supplier = serializer.save()
        supplier = (
            Supplier.objects.prefetch_related("restock_purchases")
            .get(pk=supplier.pk)
        )
        return Response(SupplierSerializer(supplier).data)

    def delete(self, request, business_id, supplier_id):
        supplier = self.supplier()
        supplier.is_active = False
        supplier.save(update_fields=("is_active", "updated_at"))
        return Response(status=status.HTTP_204_NO_CONTENT)


class BusinessRestockListCreateAPIView(RestockAccessMixin, APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, business_id):
        purchases = (
            RestockPurchase.objects.filter(
                business=self.get_business(),
                branch=self.get_branch(),
            )
            .select_related("branch", "supplier", "created_by")
            .prefetch_related("items")
        )
        return Response(RestockPurchaseSerializer(purchases, many=True).data)

    def post(self, request, business_id):
        serializer = RestockCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        purchase = create_restock(
            business=self.get_business(),
            branch=self.get_branch(serializer.validated_data.get("branchId")),
            user=request.user,
            data=serializer.validated_data,
        )
        purchase = (
            RestockPurchase.objects.select_related("branch", "supplier", "created_by")
            .prefetch_related("items")
            .get(pk=purchase.pk)
        )
        return Response(
            RestockPurchaseSerializer(purchase).data,
            status=status.HTTP_201_CREATED,
        )


class BusinessRestockPaymentAPIView(RestockAccessMixin, APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, business_id, purchase_id):
        serializer = RestockPaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        purchase = record_payment(
            business=self.get_business(),
            purchase_id=purchase_id,
            user=request.user,
            data=serializer.validated_data,
        )
        purchase = (
            RestockPurchase.objects.select_related("branch", "supplier", "created_by")
            .prefetch_related("items")
            .get(pk=purchase.pk)
        )
        return Response(RestockPurchaseSerializer(purchase).data)
