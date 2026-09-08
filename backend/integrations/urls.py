from django.urls import path

from .views import AccountingExportCsvAPIView, AccountingExportManifestAPIView


app_name = "integrations"

urlpatterns = [
    path(
        "businesses/<uuid:business_id>/integrations/accounting/exports/",
        AccountingExportManifestAPIView.as_view(),
        name="accounting-export-manifest",
    ),
    path(
        "businesses/<uuid:business_id>/integrations/accounting/exports/"
        "<slug:dataset>/",
        AccountingExportCsvAPIView.as_view(),
        name="accounting-export-csv",
    ),
]
# StockFlow safe data import v1.
from .views import (
    DataImportApplyAPIView,
    DataImportCollectionAPIView,
    DataImportPreviewAPIView,
)

urlpatterns += [
    path(
        "businesses/<uuid:business_id>/integrations/imports/",
        DataImportCollectionAPIView.as_view(),
        name="data-import-list",
    ),
    path(
        "businesses/<uuid:business_id>/integrations/imports/preview/",
        DataImportPreviewAPIView.as_view(),
        name="data-import-preview",
    ),
    path(
        "businesses/<uuid:business_id>/integrations/imports/<uuid:import_id>/apply/",
        DataImportApplyAPIView.as_view(),
        name="data-import-apply",
    ),
]


# StockFlow outbound intelligence messaging v1.
from .views import (
    MessagingCapabilitiesAPIView,
    MessagingDeliveryCollectionAPIView,
    MessagingPreferenceAPIView,
    MessagingTestSmsAPIView,
)

urlpatterns += [
    path(
        "businesses/<uuid:business_id>/integrations/messaging/capabilities/",
        MessagingCapabilitiesAPIView.as_view(),
        name="messaging-capabilities",
    ),
    path(
        "businesses/<uuid:business_id>/integrations/messaging/preferences/",
        MessagingPreferenceAPIView.as_view(),
        name="messaging-preferences",
    ),
    path(
        "businesses/<uuid:business_id>/integrations/messaging/deliveries/",
        MessagingDeliveryCollectionAPIView.as_view(),
        name="messaging-deliveries",
    ),
    path(
        "businesses/<uuid:business_id>/integrations/messaging/test-sms/",
        MessagingTestSmsAPIView.as_view(),
        name="messaging-test-sms",
    ),
]


# Public API, outbound webhooks and accounting connector foundation.
from .admin_views import (
    AccountingCapabilityAPIView,
    AccountingConnectionCollectionAPIView,
    ApiCredentialCollectionAPIView,
    ApiCredentialRevokeAPIView,
    WebhookEndpointCollectionAPIView,
    WebhookEndpointDetailAPIView,
    WebhookEndpointTestAPIView,
)
from .public_api import PublicApiDatasetAPIView, PublicApiManifestAPIView

urlpatterns += [
    path(
        "businesses/<uuid:business_id>/integrations/api-keys/",
        ApiCredentialCollectionAPIView.as_view(),
        name="api-key-list",
    ),
    path(
        "businesses/<uuid:business_id>/integrations/api-keys/"
        "<uuid:credential_id>/revoke/",
        ApiCredentialRevokeAPIView.as_view(),
        name="api-key-revoke",
    ),
    path(
        "businesses/<uuid:business_id>/integrations/webhooks/endpoints/",
        WebhookEndpointCollectionAPIView.as_view(),
        name="webhook-endpoint-list",
    ),
    path(
        "businesses/<uuid:business_id>/integrations/webhooks/endpoints/"
        "<uuid:endpoint_id>/",
        WebhookEndpointDetailAPIView.as_view(),
        name="webhook-endpoint-detail",
    ),
    path(
        "businesses/<uuid:business_id>/integrations/webhooks/endpoints/"
        "<uuid:endpoint_id>/test/",
        WebhookEndpointTestAPIView.as_view(),
        name="webhook-endpoint-test",
    ),
    path(
        "businesses/<uuid:business_id>/integrations/accounting/"
        "connectors/capabilities/",
        AccountingCapabilityAPIView.as_view(),
        name="accounting-connector-capabilities",
    ),
    path(
        "businesses/<uuid:business_id>/integrations/accounting/"
        "connectors/connections/",
        AccountingConnectionCollectionAPIView.as_view(),
        name="accounting-connector-connections",
    ),
    path(
        "public/v1/",
        PublicApiManifestAPIView.as_view(),
        name="public-api-manifest",
    ),
    path(
        "public/v1/<slug:dataset>/",
        PublicApiDatasetAPIView.as_view(),
        name="public-api-dataset",
    ),
]


# E-commerce connector and supplier purchase-order integration foundation.
from .commerce.views import (
    CommerceCapabilitiesAPIView,
    CommerceConnectionCollectionAPIView,
    CommerceOrderCollectionAPIView,
    CommerceOrderStageAPIView,
    CommerceProductMappingAPIView,
)
from .supplier_orders import (
    SupplierPurchaseOrderCollectionAPIView,
    SupplierPurchaseOrderIssueAPIView,
    SupplierPurchaseOrderReceiveAPIView,
)

urlpatterns += [
    path(
        "businesses/<uuid:business_id>/integrations/commerce/capabilities/",
        CommerceCapabilitiesAPIView.as_view(),
        name="commerce-capabilities",
    ),
    path(
        "businesses/<uuid:business_id>/integrations/commerce/connections/",
        CommerceConnectionCollectionAPIView.as_view(),
        name="commerce-connections",
    ),
    path(
        "businesses/<uuid:business_id>/integrations/commerce/connections/"
        "<uuid:connection_id>/product-mappings/",
        CommerceProductMappingAPIView.as_view(),
        name="commerce-product-mappings",
    ),
    path(
        "businesses/<uuid:business_id>/integrations/commerce/orders/",
        CommerceOrderCollectionAPIView.as_view(),
        name="commerce-orders",
    ),
    path(
        "businesses/<uuid:business_id>/integrations/commerce/orders/stage/",
        CommerceOrderStageAPIView.as_view(),
        name="commerce-order-stage",
    ),
    path(
        "businesses/<uuid:business_id>/integrations/supplier-orders/",
        SupplierPurchaseOrderCollectionAPIView.as_view(),
        name="supplier-order-list-create",
    ),
    path(
        "businesses/<uuid:business_id>/integrations/supplier-orders/"
        "<uuid:purchase_order_id>/issue/",
        SupplierPurchaseOrderIssueAPIView.as_view(),
        name="supplier-order-issue",
    ),
    path(
        "businesses/<uuid:business_id>/integrations/supplier-orders/"
        "<uuid:purchase_order_id>/receive/",
        SupplierPurchaseOrderReceiveAPIView.as_view(),
        name="supplier-order-receive",
    ),
]

