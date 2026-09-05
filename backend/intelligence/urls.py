from django.urls import path

from .views import BusinessIntelligenceOverviewAPIView


urlpatterns = [
    path(
        "businesses/<uuid:business_id>/intelligence/overview/",
        BusinessIntelligenceOverviewAPIView.as_view(),
        name="business-intelligence-overview",
    ),
]
