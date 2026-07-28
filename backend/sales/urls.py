from django.urls import path

from .views import (
    BusinessCustomerDebtPaymentAPIView,
    BusinessSaleDetailAPIView,
    BusinessSaleListCreateAPIView,
)

app_name = "sales"

urlpatterns = [
    path(
        "businesses/<uuid:business_id>/customers/"
        "<uuid:customer_id>/payments/",
        BusinessCustomerDebtPaymentAPIView.as_view(),
        name="business-customer-debt-payment",
    ),
    path(
        "businesses/<uuid:business_id>/sales/",
        BusinessSaleListCreateAPIView.as_view(),
        name="business-sale-list-create",
    ),
    path(
        "businesses/<uuid:business_id>/sales/<uuid:sale_id>/",
        BusinessSaleDetailAPIView.as_view(),
        name="business-sale-detail",
    ),
]
