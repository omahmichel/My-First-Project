from django.db.models import Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from businesses.access import get_business_and_role_for_user
from businesses.branch_access import branch_queryset_for_user, resolve_branch_for_user
from businesses.models import BusinessMembership

from .branch_serializers import (
    BranchInventorySerializer,
    BranchTransferCreateSerializer,
    BranchTransferSerializer,
)
from .branch_service import create_branch_transfer
from .models import BranchInventory, BranchTransfer


BRANCH_OPERATION_ROLES = (
    BusinessMembership.Role.OWNER,
    BusinessMembership.Role.MANAGER,
    BusinessMembership.Role.INVENTORY_CLERK,
)
TRANSFER_ROLES = (
    BusinessMembership.Role.OWNER,
    BusinessMembership.Role.MANAGER,
    BusinessMembership.Role.INVENTORY_CLERK,
)


class BranchInventoryAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, business_id):
        business, role = get_business_and_role_for_user(
            user=request.user,
            business_id=business_id,
            membership_roles=BRANCH_OPERATION_ROLES,
        )
        branch = resolve_branch_for_user(
            business=business,
            user=request.user,
            role=role,
            branch_id=request.query_params.get("branchId"),
        )
        rows = BranchInventory.objects.filter(
            branch=branch, product__is_active=True
        ).select_related("branch", "product").order_by("product__name")
        return Response(BranchInventorySerializer(rows, many=True).data)


class BranchTransferListCreateAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def business_and_role(self, request, business_id):
        return get_business_and_role_for_user(
            user=request.user,
            business_id=business_id,
            membership_roles=TRANSFER_ROLES,
        )

    def get(self, request, business_id):
        business, role = self.business_and_role(request, business_id)
        allowed = branch_queryset_for_user(
            business=business, user=request.user, role=role
        ).values_list("id", flat=True)
        transfers = BranchTransfer.objects.filter(
            business=business
        ).filter(
            Q(source_branch_id__in=allowed) | Q(destination_branch_id__in=allowed)
        ).select_related(
            "source_branch", "destination_branch", "created_by"
        ).prefetch_related("items")
        return Response(BranchTransferSerializer(transfers, many=True).data)

    def post(self, request, business_id):
        business, role = self.business_and_role(request, business_id)
        serializer = BranchTransferCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        source = resolve_branch_for_user(
            business=business, user=request.user, role=role,
            branch_id=data["sourceBranchId"],
        )
        destination = resolve_branch_for_user(
            business=business, user=request.user, role=role,
            branch_id=data["destinationBranchId"],
        )
        transfer = create_branch_transfer(
            business=business, source_branch=source, destination_branch=destination,
            user=request.user, items=data["items"], reason=data.get("reason", ""),
        )
        transfer = BranchTransfer.objects.select_related(
            "source_branch", "destination_branch", "created_by"
        ).prefetch_related("items").get(pk=transfer.pk)
        return Response(
            BranchTransferSerializer(transfer).data,
            status=status.HTTP_201_CREATED,
        )
