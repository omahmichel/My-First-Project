from django.db.models import Q
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Business
from .permissions import CanManageBusiness
from .serializers import BusinessSerializer


class BusinessViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    # Provides business-isolated workspace access without a delete endpoint.

    serializer_class = BusinessSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        # Limits every request to owned businesses or active memberships.
        user = self.request.user

        return (
            Business.objects.filter(
                Q(owner=user)
                | Q(
                    memberships__user=user,
                    memberships__is_active=True,
                )
            )
            .select_related("owner")
            .distinct()
        )

    def get_permissions(self):
        # Restricts business edits to owners and active managers.
        if self.action in ("update", "partial_update"):
            return (IsAuthenticated(), CanManageBusiness())

        return (IsAuthenticated(),)
