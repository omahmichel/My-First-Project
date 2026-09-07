from django.urls import path

from .views import (
    BusinessIntelligenceAnalystAPIView,
    BusinessIntelligenceForecastAPIView,
    BusinessIntelligenceOverviewAPIView,
    BusinessIntelligenceRecommendationAPIView,
    BusinessIntelligenceReportCollectionAPIView,
    BusinessIntelligenceReportDetailAPIView,
)


urlpatterns = [
    path(
        "businesses/<uuid:business_id>/intelligence/overview/",
        BusinessIntelligenceOverviewAPIView.as_view(),
        name="business-intelligence-overview",
    ),
    path(
        "businesses/<uuid:business_id>/intelligence/forecasts/",
        BusinessIntelligenceForecastAPIView.as_view(),
        name="business-intelligence-forecast",
    ),
    path(
        "businesses/<uuid:business_id>/intelligence/recommendations/",
        BusinessIntelligenceRecommendationAPIView.as_view(),
        name="business-intelligence-recommendations",
    ),
    path(
        "businesses/<uuid:business_id>/intelligence/analyst/",
        BusinessIntelligenceAnalystAPIView.as_view(),
        name="business-intelligence-analyst",
    ),
    path(
        "businesses/<uuid:business_id>/intelligence/reports/",
        BusinessIntelligenceReportCollectionAPIView.as_view(),
        name="business-intelligence-reports",
    ),
    path(
        "businesses/<uuid:business_id>/intelligence/reports/"
        "<uuid:report_id>/",
        BusinessIntelligenceReportDetailAPIView.as_view(),
        name="business-intelligence-report-detail",
    ),
]
