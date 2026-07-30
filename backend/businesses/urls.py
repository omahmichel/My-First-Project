from django.urls import path
from rest_framework.routers import DefaultRouter

from .team_views import (
    BusinessTeamDeleteAPIView,
    BusinessTeamListCreateAPIView,
)
from .views import BusinessViewSet

# Registers standard list, create, retrieve and update API routes.
router = DefaultRouter()
router.register("businesses", BusinessViewSet, basename="business")

urlpatterns = [
    path(
        "businesses/<uuid:business_id>/team/",
        BusinessTeamListCreateAPIView.as_view(),
        name="business-team-list-create",
    ),
    path(
        "businesses/<uuid:business_id>/team/<uuid:membership_id>/",
        BusinessTeamDeleteAPIView.as_view(),
        name="business-team-delete",
    ),
] + router.urls
