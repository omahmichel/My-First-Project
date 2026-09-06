from django.urls import path

from .views import (
    BusinessIntelligenceForecastAPIView,
    BusinessIntelligenceOverviewAPIView,
    BusinessIntelligenceRecommendationAPIView,
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
]
