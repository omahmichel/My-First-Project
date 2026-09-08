from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied

from .models import Branch, BranchAccess, BusinessMembership


MANAGEMENT_BRANCH_ROLES = (
    BusinessMembership.Role.OWNER,
    BusinessMembership.Role.MANAGER,
)


def ensure_main_branch(*, business, created_by=None):
    """Returns the compatibility branch and safely repairs old direct-created businesses."""
    branch = business.branches.filter(is_main=True).first()
    if branch:
        return branch

    branch = Branch.objects.create(
        business=business,
        name="Main Branch",
        code="MAIN",
        location=business.location,
        phone=business.phone,
        is_main=True,
        is_active=True,
        created_by=created_by,
    )

    for membership in business.memberships.filter(is_active=True):
        BranchAccess.objects.get_or_create(
            branch=branch,
            membership=membership,
            defaults={"is_active": True},
        )

    return branch


def branch_queryset_for_user(*, business, user, role, active_only=True):
    queryset = Branch.objects.filter(business=business)
    if active_only:
        queryset = queryset.filter(is_active=True)

    if role in MANAGEMENT_BRANCH_ROLES:
        return queryset.distinct()

    membership = get_object_or_404(
        BusinessMembership,
        business=business,
        user=user,
        is_active=True,
        role=role,
    )

    # Existing single-location staff keep access to the compatibility branch.
    if not BranchAccess.objects.filter(
        membership=membership,
        is_active=True,
    ).exists():
        main_branch = ensure_main_branch(business=business)
        BranchAccess.objects.get_or_create(
            branch=main_branch,
            membership=membership,
            defaults={"is_active": True},
        )

    return queryset.filter(
        access_assignments__membership=membership,
        access_assignments__is_active=True,
    ).distinct()


def resolve_branch_for_user(
    *, business, user, role, branch_id=None, active_only=True
):
    """Resolves one branch without allowing cross-business or cross-assignment access."""
    ensure_main_branch(business=business, created_by=(user if user.is_authenticated else None))
    queryset = branch_queryset_for_user(
        business=business,
        user=user,
        role=role,
        active_only=active_only,
    )

    if branch_id:
        return get_object_or_404(queryset, pk=branch_id)

    branch = queryset.filter(is_main=True).first() or queryset.order_by(
        "-is_main", "name"
    ).first()
    if not branch:
        raise PermissionDenied(
            "You do not have access to an active branch in this business."
        )
    return branch
