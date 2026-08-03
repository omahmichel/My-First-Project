from django.urls import path

from .views import (
    BusinessCustomerDebtPaymentAPIView,
    BusinessMobileMoneySaleVerifyAPIView,
    BusinessSaleDetailAPIView,
    BusinessSaleListCreateAPIView,
    BusinessSaleWaybillAPIView,
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
        "businesses/<uuid:business_id>/sales/mobile-money/"
        "<str:reference>/verify/",
        BusinessMobileMoneySaleVerifyAPIView.as_view(),
        name="business-mobile-money-sale-verify",
    ),
    path(
        "businesses/<uuid:business_id>/sales/<uuid:sale_id>/",
        BusinessSaleDetailAPIView.as_view(),
        name="business-sale-detail",
    ),
    path(
        "businesses/<uuid:business_id>/sales/"
        "<uuid:sale_id>/waybill/",
        BusinessSaleWaybillAPIView.as_view(),
        name="business-sale-waybill",
    ),
]
