from django.urls import path

from .restock_views import (
    BusinessRestockListCreateAPIView,
    BusinessRestockPaymentAPIView,
    BusinessSupplierDetailAPIView,
    BusinessSupplierListCreateAPIView,
)
from .views import (
    BusinessProductDetailAPIView,
    BusinessProductListCreateAPIView,
    BusinessStockMovementListAPIView,
    ProductStatusAPIView,
    ProductStockAdjustmentAPIView,
)

app_name = "inventory"

urlpatterns = [
    path(
        "businesses/<uuid:business_id>/products/",
        BusinessProductListCreateAPIView.as_view(),
        name="business-product-list-create",
    ),
    path(
        "businesses/<uuid:business_id>/products/<uuid:product_id>/",
        BusinessProductDetailAPIView.as_view(),
        name="business-product-detail",
    ),
    path(
        "businesses/<uuid:business_id>/products/"
        "<uuid:product_id>/status/",
        ProductStatusAPIView.as_view(),
        name="product-status",
    ),
    path(
        "businesses/<uuid:business_id>/products/"
        "<uuid:product_id>/adjust-stock/",
        ProductStockAdjustmentAPIView.as_view(),
        name="product-stock-adjustment",
    ),
    path(
        "businesses/<uuid:business_id>/stock-movements/",
        BusinessStockMovementListAPIView.as_view(),
        name="business-stock-movement-list",
    ),
    path(
        "businesses/<uuid:business_id>/suppliers/",
        BusinessSupplierListCreateAPIView.as_view(),
        name="business-supplier-list-create",
    ),
    path(
        "businesses/<uuid:business_id>/suppliers/<uuid:supplier_id>/",
        BusinessSupplierDetailAPIView.as_view(),
        name="business-supplier-detail",
    ),
    path(
        "businesses/<uuid:business_id>/restocks/",
        BusinessRestockListCreateAPIView.as_view(),
        name="business-restock-list-create",
    ),
    path(
        "businesses/<uuid:business_id>/restocks/"
        "<uuid:purchase_id>/payments/",
        BusinessRestockPaymentAPIView.as_view(),
        name="business-restock-payment",
    ),
]
