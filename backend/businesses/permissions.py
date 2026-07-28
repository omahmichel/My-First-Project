from rest_framework.permissions import BasePermission

from .models import BusinessMembership


class CanManageBusiness(BasePermission):
    # Allows only the owner or an active manager to edit a business.

    message = "You do not have permission to manage this business."

    def has_object_permission(self, request, view, obj):
        if obj.owner_id == request.user.id:
            return True

        return obj.memberships.filter(
            user=request.user,
            is_active=True,
            role__in=(
                BusinessMembership.Role.OWNER,
                BusinessMembership.Role.MANAGER,
            ),
        ).exists()
