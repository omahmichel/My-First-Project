import secrets

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Business, BusinessMembership
from .team_serializers import (
    TeamMemberCreateSerializer,
    TeamMemberSerializer,
)

User = get_user_model()


class BusinessTeamAccessMixin:
    # Resolves only businesses the requester is allowed to manage.

    def get_manageable_business(self):
        user = self.request.user

        queryset = (
            Business.objects.filter(
                Q(owner=user)
                | Q(
                    memberships__user=user,
                    memberships__is_active=True,
                    memberships__role__in=(
                        BusinessMembership.Role.OWNER,
                        BusinessMembership.Role.MANAGER,
                    ),
                )
            )
            .select_related("owner")
            .distinct()
        )

        return get_object_or_404(
            queryset,
            pk=self.kwargs["business_id"],
        )

    def requester_is_owner(self, business):
        # Treats the database owner field as the final ownership authority.
        return business.owner_id == self.request.user.id


class BusinessTeamListCreateAPIView(
    BusinessTeamAccessMixin,
    APIView,
):
    # Lists active staff and adds members to one isolated business.

    permission_classes = (IsAuthenticated,)

    def get(self, request, business_id):
        business = self.get_manageable_business()

        memberships = (
            business.memberships.filter(is_active=True)
            .select_related("user")
            .order_by("role", "user__full_name", "user__email")
        )

        return Response(
            TeamMemberSerializer(memberships, many=True).data
        )

    @transaction.atomic
    def post(self, request, business_id):
        business = self.get_manageable_business()

        serializer = TeamMemberCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if (
            data["role"] == BusinessMembership.Role.MANAGER
            and not self.requester_is_owner(business)
        ):
            return Response(
                {
                    "role": (
                        "Only the business owner can add "
                        "another manager."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        existing_user = User.objects.filter(
            email=data["email"]
        ).first()

        if (
            existing_user
            and existing_user.id == business.owner_id
        ):
            return Response(
                {
                    "email": (
                        "The business owner already has protected "
                        "access to this business."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        temporary_password = None
        created_user = False

        if existing_user:
            user = existing_user

            # Fills missing profile details without overwriting saved data.
            changed_fields = []

            if not user.full_name and data["name"]:
                user.full_name = data["name"]
                changed_fields.append("full_name")

            if not user.phone and data.get("phone"):
                user.phone = data["phone"]
                changed_fields.append("phone")

            if changed_fields:
                user.save(update_fields=changed_fields)
        else:
            temporary_password = secrets.token_urlsafe(12)

            user = User.objects.create_user(
                email=data["email"],
                full_name=data["name"],
                phone=data.get("phone", ""),
                password=temporary_password,
            )
            created_user = True

        membership = BusinessMembership.objects.filter(
            business=business,
            user=user,
        ).first()

        if membership and membership.is_active:
            return Response(
                {
                    "email": (
                        "This user is already an active member "
                        "of the business."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if membership:
            # Reactivates a previously removed membership safely.
            membership.role = data["role"]
            membership.is_active = True
            membership.last_active_at = None
            membership.save(
                update_fields=(
                    "role",
                    "is_active",
                    "last_active_at",
                    "updated_at",
                )
            )
            response_status = status.HTTP_200_OK
        else:
            membership = BusinessMembership.objects.create(
                business=business,
                user=user,
                role=data["role"],
                is_active=True,
            )
            response_status = status.HTTP_201_CREATED

        response_data = TeamMemberSerializer(membership).data
        response_data["isNewUser"] = created_user

        # Returns a new account password once until email invitations are added.
        if temporary_password:
            response_data["temporaryPassword"] = temporary_password

        return Response(response_data, status=response_status)


class BusinessTeamDeleteAPIView(
    BusinessTeamAccessMixin,
    APIView,
):
    # Removes business access without deleting the staff user's account.

    permission_classes = (IsAuthenticated,)

    @transaction.atomic
    def delete(self, request, business_id, membership_id):
        business = self.get_manageable_business()

        membership = get_object_or_404(
            business.memberships.select_related("user"),
            pk=membership_id,
            is_active=True,
        )

        if membership.user_id == business.owner_id:
            return Response(
                {
                    "detail": (
                        "The business owner account cannot be removed."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if (
            membership.role == BusinessMembership.Role.MANAGER
            and not self.requester_is_owner(business)
        ):
            return Response(
                {
                    "detail": (
                        "Only the business owner can remove a manager."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if membership.user_id == request.user.id:
            return Response(
                {
                    "detail": (
                        "You cannot remove your own active membership."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Soft removal preserves historical links for future audit records.
        membership.is_active = False
        membership.save(
            update_fields=(
                "is_active",
                "updated_at",
            )
        )

        return Response(status=status.HTTP_204_NO_CONTENT)
