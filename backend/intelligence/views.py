from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from businesses.access import get_business_and_role_for_user
from businesses.models import BusinessMembership

from .models import ForecastRun
from .serializers import (
    BusinessIntelligenceOverviewSerializer,
    IntelligenceForecastRequestSerializer,
    IntelligenceForecastRunSerializer,
)
from .services.business_analysis import calculate_business_overview
from .services.forecasting import generate_and_store_forecast


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

class BusinessIntelligenceForecastAPIView(APIView):
    """Generates and reads stored deterministic business forecasts."""

    permission_classes = (IsAuthenticated,)

    def _business(self, request, business_id):
        business, _ = get_business_and_role_for_user(
            user=request.user,
            business_id=business_id,
            membership_roles=INTELLIGENCE_ROLES,
        )
        return business

    def get(self, request, business_id):
        business = self._business(request, business_id)
        runs = ForecastRun.objects.filter(
            business=business,
            status=ForecastRun.Status.COMPLETED,
        )

        horizon_days = request.query_params.get("horizonDays")
        if horizon_days is not None:
            request_serializer = IntelligenceForecastRequestSerializer(
                data={"horizonDays": horizon_days}
            )
            request_serializer.is_valid(raise_exception=True)
            runs = runs.filter(
                horizon_days=request_serializer.validated_data[
                    "horizon_days"
                ]
            )

        serializer = IntelligenceForecastRunSerializer(
            instance=runs[:20],
            many=True,
        )
        return Response(serializer.data)

    def post(self, request, business_id):
        business = self._business(request, business_id)

        request_serializer = IntelligenceForecastRequestSerializer(
            data=request.data
        )
        request_serializer.is_valid(raise_exception=True)

        run = generate_and_store_forecast(
            business,
            horizon_days=request_serializer.validated_data[
                "horizon_days"
            ],
        )
        serializer = IntelligenceForecastRunSerializer(instance=run)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )
