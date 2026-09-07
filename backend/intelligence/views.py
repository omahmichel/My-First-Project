from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from businesses.access import get_business_and_role_for_user
from businesses.models import BusinessMembership

from .models import ForecastRun
from .serializers import (
    BusinessIntelligenceOverviewSerializer,
    IntelligenceForecastRequestSerializer,
    IntelligenceForecastRunSerializer,
    IntelligenceRecommendationCollectionSerializer,
    IntelligenceAnalystRequestSerializer,
    IntelligenceAnalystResponseSerializer,
    IntelligenceGeneratedReportSerializer,
    IntelligenceReportRequestSerializer,
)
from .ai.analyst import (
    AIAnalystUnavailable,
    answer_business_question,
)
from .services.business_analysis import calculate_business_overview
from .models import GeneratedReport
from .services.forecasting import generate_and_store_forecast
from .services.reports import generate_and_store_report
from .services.recommendations import (
    RECOMMENDATION_ENGINE,
    RECOMMENDATION_FORECAST_HORIZON_DAYS,
    generate_and_store_recommendations,
    get_active_recommendations,
)


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

class BusinessIntelligenceRecommendationAPIView(APIView):
    """Reads and regenerates deterministic business recommendations."""

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
        payload = {
            "engine": RECOMMENDATION_ENGINE,
            "forecast_horizon_days": (
                RECOMMENDATION_FORECAST_HORIZON_DAYS
            ),
            "generated_at": timezone.now(),
            "recommendations": get_active_recommendations(
                business
            ),
        }
        serializer = IntelligenceRecommendationCollectionSerializer(
            instance=payload
        )
        return Response(serializer.data)

    def post(self, request, business_id):
        business = self._business(request, business_id)
        payload = generate_and_store_recommendations(
            business
        )
        serializer = IntelligenceRecommendationCollectionSerializer(
            instance=payload
        )
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )

class BusinessIntelligenceAnalystAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "intelligence_analyst"

    def post(self, request, business_id):
        business, _ = get_business_and_role_for_user(
            user=request.user,
            business_id=business_id,
            membership_roles=INTELLIGENCE_ROLES,
        )

        request_serializer = IntelligenceAnalystRequestSerializer(
            data=request.data
        )
        request_serializer.is_valid(raise_exception=True)

        try:
            payload = answer_business_question(
                business=business,
                question=request_serializer.validated_data[
                    "question"
                ],
                history=request_serializer.validated_data.get(
                    "history",
                    [],
                ),
            )
        except AIAnalystUnavailable as exc:
            return Response(
                {
                    "detail": exc.message,
                    "code": exc.code,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        serializer = IntelligenceAnalystResponseSerializer(
            instance=payload
        )
        return Response(serializer.data)

class BusinessIntelligenceReportCollectionAPIView(APIView):
    """Lists and generates persisted verified management reports."""

    permission_classes = (IsAuthenticated,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "intelligence_reports"

    def get(self, request, business_id):
        business, _ = get_business_and_role_for_user(
            user=request.user,
            business_id=business_id,
            membership_roles=INTELLIGENCE_ROLES,
        )

        queryset = GeneratedReport.objects.filter(business=business)

        report_type = request.query_params.get("reportType", "").strip()
        if report_type:
            valid_types = {
                choice
                for choice, _ in GeneratedReport.ReportType.choices
            }
            if report_type not in valid_types:
                return Response(
                    {"detail": "Unsupported Intelligence report type."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            queryset = queryset.filter(report_type=report_type)

        serializer = IntelligenceGeneratedReportSerializer(
            instance=queryset[:50],
            many=True,
        )
        return Response(serializer.data)

    def post(self, request, business_id):
        business, _ = get_business_and_role_for_user(
            user=request.user,
            business_id=business_id,
            membership_roles=INTELLIGENCE_ROLES,
        )

        request_serializer = IntelligenceReportRequestSerializer(
            data=request.data
        )
        request_serializer.is_valid(raise_exception=True)

        report = generate_and_store_report(
            business=business,
            generated_by=request.user,
            **request_serializer.validated_data,
        )
        serializer = IntelligenceGeneratedReportSerializer(
            instance=report
        )
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )


class BusinessIntelligenceReportDetailAPIView(APIView):
    """Returns one persisted report inside its owning business only."""

    permission_classes = (IsAuthenticated,)

    def get(self, request, business_id, report_id):
        business, _ = get_business_and_role_for_user(
            user=request.user,
            business_id=business_id,
            membership_roles=INTELLIGENCE_ROLES,
        )

        report = get_object_or_404(
            GeneratedReport,
            id=report_id,
            business=business,
        )
        serializer = IntelligenceGeneratedReportSerializer(
            instance=report
        )
        return Response(serializer.data)
