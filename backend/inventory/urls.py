from django.urls import path

from .views import (
    BusinessProductDetailAPIView,
    BusinessProductListCreateAPIView,
    BusinessStockMovementListAPIView,
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
        "<uuid:product_id>/adjust-stock/",
        ProductStockAdjustmentAPIView.as_view(),
        name="product-stock-adjustment",
    ),
    path(
        "businesses/<uuid:business_id>/stock-movements/",
        BusinessStockMovementListAPIView.as_view(),
        name="business-stock-movement-list",
    ),
]
