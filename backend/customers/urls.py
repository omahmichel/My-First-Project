from django.urls import path

from .views import (
    BusinessCustomerDetailAPIView,
    BusinessCustomerListCreateAPIView,
)

app_name = "customers"

urlpatterns = [
    path(
        "businesses/<uuid:business_id>/customers/",
        BusinessCustomerListCreateAPIView.as_view(),
        name="business-customer-list-create",
    ),
    path(
        "businesses/<uuid:business_id>/customers/<uuid:customer_id>/",
        BusinessCustomerDetailAPIView.as_view(),
        name="business-customer-detail",
    ),
]
