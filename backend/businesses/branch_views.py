from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .access import get_business_and_role_for_user
from .branch_access import branch_queryset_for_user, ensure_main_branch
from .branch_serializers import (
    BranchAccessUpdateSerializer,
    BranchSerializer,
    BranchWriteSerializer,
)
from .models import Branch, BranchAccess, BusinessMembership


READ_ROLES = (
    BusinessMembership.Role.OWNER,
    BusinessMembership.Role.MANAGER,
    BusinessMembership.Role.CASHIER,
    BusinessMembership.Role.INVENTORY_CLERK,
)
MANAGE_ROLES = (
    BusinessMembership.Role.OWNER,
    BusinessMembership.Role.MANAGER,
)


class BranchAccessMixin:
    def business_and_role(self, *, manage=False):
        return get_business_and_role_for_user(
            user=self.request.user,
            business_id=self.kwargs["business_id"],
            membership_roles=(MANAGE_ROLES if manage else READ_ROLES),
        )


class BusinessBranchListCreateAPIView(BranchAccessMixin, APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, business_id):
        business, role = self.business_and_role()
        ensure_main_branch(business=business, created_by=request.user)
        branches = branch_queryset_for_user(
            business=business,
            user=request.user,
            role=role,
            active_only=False,
        ).prefetch_related("access_assignments")
        return Response(BranchSerializer(branches, many=True).data)

    @transaction.atomic
    def post(self, request, business_id):
        business, _ = self.business_and_role(manage=True)
        serializer = BranchWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if Branch.objects.filter(
            business=business, code__iexact=data["code"]
        ).exists():
            return Response(
                {"code": "A branch with this code already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        branch = Branch.objects.create(
            business=business,
            created_by=request.user,
            **data,
        )

        from inventory.branch_service import seed_branch_inventory

        seed_branch_inventory(branch=branch)
        return Response(
            BranchSerializer(branch).data,
            status=status.HTTP_201_CREATED,
        )


class BusinessBranchDetailAPIView(BranchAccessMixin, APIView):
    permission_classes = (IsAuthenticated,)

    def branch(self, business):
        return get_object_or_404(
            Branch, pk=self.kwargs["branch_id"], business=business
        )

    @transaction.atomic
    def patch(self, request, business_id, branch_id):
        business, _ = self.business_and_role(manage=True)
        branch = self.branch(business)
        serializer = BranchWriteSerializer(
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if "code" in data and Branch.objects.filter(
            business=business, code__iexact=data["code"]
        ).exclude(pk=branch.pk).exists():
            return Response(
                {"code": "A branch with this code already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for field, value in data.items():
            setattr(branch, field, value)
        branch.save()
        return Response(BranchSerializer(branch).data)

    @transaction.atomic
    def delete(self, request, business_id, branch_id):
        business, _ = self.business_and_role(manage=True)
        branch = self.branch(business)
        if branch.is_main:
            return Response(
                {"detail": "The main branch cannot be deactivated."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from inventory.models import BranchInventory

        has_stock = BranchInventory.objects.filter(
            branch=branch
        ).filter(
            stock__gt=0
        ).exists()
        has_reserved = BranchInventory.objects.filter(
            branch=branch, reserved_stock__gt=0
        ).exists()
        if has_stock or has_reserved:
            return Response(
                {
                    "detail": (
                        "Move or adjust all stock out of this branch before deactivating it."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        branch.is_active = False
        branch.save(update_fields=("is_active", "updated_at"))
        return Response(status=status.HTTP_204_NO_CONTENT)


class BusinessBranchMemberAccessAPIView(BranchAccessMixin, APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, business_id, branch_id):
        business, _ = self.business_and_role(manage=True)
        branch = get_object_or_404(Branch, pk=branch_id, business=business)
        return Response(
            {
                "branchId": str(branch.id),
                "membershipIds": [
                    str(value)
                    for value in branch.access_assignments.filter(
                        is_active=True
                    ).values_list("membership_id", flat=True)
                ],
            }
        )

    @transaction.atomic
    def put(self, request, business_id, branch_id):
        business, _ = self.business_and_role(manage=True)
        branch = get_object_or_404(Branch, pk=branch_id, business=business)
        serializer = BranchAccessUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        requested_ids = set(serializer.validated_data["membershipIds"])
        memberships = list(
            BusinessMembership.objects.filter(
                business=business,
                is_active=True,
                id__in=requested_ids,
            )
        )
        if len(memberships) != len(requested_ids):
            return Response(
                {"membershipIds": "One or more team memberships are invalid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        active_by_id = {item.membership_id: item for item in branch.access_assignments.all()}
        for membership in memberships:
            assignment = active_by_id.get(membership.id)
            if assignment:
                if not assignment.is_active:
                    assignment.is_active = True
                    assignment.save(update_fields=("is_active", "updated_at"))
            else:
                BranchAccess.objects.create(
                    branch=branch,
                    membership=membership,
                    is_active=True,
                )

        branch.access_assignments.exclude(
            membership_id__in=requested_ids
        ).update(is_active=False)

        return Response(
            {
                "branchId": str(branch.id),
                "membershipIds": [str(value) for value in requested_ids],
            }
        )
