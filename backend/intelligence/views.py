from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from businesses.access import get_business_and_role_for_user
from businesses.models import BusinessMembership

from .serializers import BusinessIntelligenceOverviewSerializer
from .services.business_analysis import calculate_business_overview


INTELLIGENCE_ROLES = (
    BusinessMembership.Role.OWNER,
    BusinessMembership.Role.MANAGER,
)


class BusinessIntelligenceOverviewAPIView(APIView):
    """Returns verified strategic intelligence for one business."""

    permission_classes = (IsAuthenticated,)

    def get(self, request, business_id):
        business, _ = get_business_and_role_for_user(
            user=request.user,
            business_id=business_id,
            membership_roles=INTELLIGENCE_ROLES,
        )

        overview = calculate_business_overview(business)
        serializer = BusinessIntelligenceOverviewSerializer(instance=overview)
        return Response(serializer.data)
