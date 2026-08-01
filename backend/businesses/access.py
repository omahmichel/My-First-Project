from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied

from .models import Business, BusinessMembership


SUBSCRIPTION_REQUIRED_ERROR = {
    "detail": (
        "Your StockFlow free trial or subscription has expired. "
        "Renew your subscription to continue using this business."
    ),
    "code": "subscription_required",
}


def require_business_subscription_access(business):
    # Blocks operational access when neither trial nor paid access is current.
    if not business.has_system_access:
        raise PermissionDenied(SUBSCRIPTION_REQUIRED_ERROR)


def get_business_and_role_for_user(
    *,
    user,
    business_id,
    membership_roles=None,
    active_only=True,
):
    # Resolves one authorized business and the requester's business role.
    membership_filter = Q(
        memberships__user=user,
        memberships__is_active=True,
    )

    if membership_roles is not None:
        membership_filter &= Q(
            memberships__role__in=membership_roles,
        )

    queryset = Business.objects.filter(
        Q(owner=user) | membership_filter
    )

    if active_only:
        queryset = queryset.filter(status=Business.Status.ACTIVE)

    business = get_object_or_404(
        queryset.select_related("owner").distinct(),
        pk=business_id,
    )

    if business.owner_id == user.id:
        role = BusinessMembership.Role.OWNER
    else:
        membership_filters = {
            "business": business,
            "user": user,
            "is_active": True,
        }

        if membership_roles is not None:
            membership_filters["role__in"] = membership_roles

        membership = get_object_or_404(
            BusinessMembership,
            **membership_filters,
        )
        role = membership.role

    require_business_subscription_access(business)
    return business, role
