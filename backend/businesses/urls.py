from django.urls import path
from rest_framework.routers import DefaultRouter

from .subscription_views import (
    PaystackWebhookAPIView,
    SubscriptionPaymentInitializeAPIView,
    SubscriptionPaymentVerifyAPIView,
)
from .team_views import (
    BusinessTeamDeleteAPIView,
    BusinessTeamListCreateAPIView,
)
from .payment_account_views import (
    BusinessPaymentAccountDetailAPIView,
    BusinessPaymentAccountListCreateAPIView,
    BusinessPaymentAccountPayoutSyncAPIView,
)

from .views import BusinessViewSet

# Registers standard list, create, retrieve and update API routes.
router = DefaultRouter()
router.register("businesses", BusinessViewSet, basename="business")

urlpatterns = [
    path(
        "payments/paystack/webhook/",
        PaystackWebhookAPIView.as_view(),
        name="paystack-webhook",
    ),
    path(
        (
            "businesses/<uuid:business_id>/"
            "subscription/payments/initialize/"
        ),
        SubscriptionPaymentInitializeAPIView.as_view(),
        name="subscription-payment-initialize",
    ),
    path(
        (
            "businesses/<uuid:business_id>/"
            "subscription/payments/<str:reference>/verify/"
        ),
        SubscriptionPaymentVerifyAPIView.as_view(),
        name="subscription-payment-verify",
    ),
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
    path(
        "businesses/<uuid:business_id>/payment-accounts/",
        BusinessPaymentAccountListCreateAPIView.as_view(),
        name="business-payment-account-list-create",
    ),
    path(
        (
            "businesses/<uuid:business_id>/payment-accounts/"
            "<uuid:account_id>/"
        ),
        BusinessPaymentAccountDetailAPIView.as_view(),
        name="business-payment-account-detail",
    ),
    path(
        (
            "businesses/<uuid:business_id>/payment-accounts/"
            "<uuid:account_id>/payout-recipient/sync/"
        ),
        BusinessPaymentAccountPayoutSyncAPIView.as_view(),
        name="business-payment-account-payout-sync",
    ),
] + router.urls
