from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .access import get_business_and_role_for_user
from .models import BusinessMembership, BusinessPaymentAccount
from .payment_account_serializers import BusinessPaymentAccountSerializer


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


class BusinessPaymentAccountAccessMixin:
    # Resolves every payment-account action inside one authorized workspace.

    def get_business_for_read(self):
        return get_business_and_role_for_user(
            user=self.request.user,
            business_id=self.kwargs["business_id"],
            membership_roles=READ_ROLES,
            active_only=False,
        )

    def get_business_for_manage(self):
        return get_business_and_role_for_user(
            user=self.request.user,
            business_id=self.kwargs["business_id"],
            membership_roles=MANAGE_ROLES,
            active_only=False,
        )


class BusinessPaymentAccountListCreateAPIView(
    BusinessPaymentAccountAccessMixin,
    APIView,
):
    # Staff can read active receiving accounts; owners/managers can manage all.

    permission_classes = (IsAuthenticated,)

    def get(self, request, business_id):
        business, role = self.get_business_for_read()

        accounts = business.payment_accounts.all()

        if role not in MANAGE_ROLES:
            accounts = accounts.filter(is_active=True)

        return Response(
            BusinessPaymentAccountSerializer(accounts, many=True).data
        )

    def post(self, request, business_id):
        business, _ = self.get_business_for_manage()

        serializer = BusinessPaymentAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = serializer.save(
            business=business,
            created_by=request.user,
            updated_by=request.user,
        )

        return Response(
            BusinessPaymentAccountSerializer(account).data,
            status=status.HTTP_201_CREATED,
        )


class BusinessPaymentAccountDetailAPIView(
    BusinessPaymentAccountAccessMixin,
    APIView,
):
    # Owners/managers can edit or safely deactivate one business account.

    permission_classes = (IsAuthenticated,)

    def patch(self, request, business_id, account_id):
        business, _ = self.get_business_for_manage()

        account = get_object_or_404(
            BusinessPaymentAccount,
            pk=account_id,
            business=business,
        )

        serializer = BusinessPaymentAccountSerializer(
            account,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        account = serializer.save(updated_by=request.user)

        return Response(
            BusinessPaymentAccountSerializer(account).data
        )

    def delete(self, request, business_id, account_id):
        business, _ = self.get_business_for_manage()

        account = get_object_or_404(
            BusinessPaymentAccount,
            pk=account_id,
            business=business,
            is_active=True,
        )

        # Soft deactivation preserves historical payment references.
        account.is_active = False
        account.is_default = False
        account.updated_by = request.user
        account.save(
            update_fields=(
                "is_active",
                "is_default",
                "updated_by",
                "updated_at",
            )
        )

        return Response(status=status.HTTP_204_NO_CONTENT)
