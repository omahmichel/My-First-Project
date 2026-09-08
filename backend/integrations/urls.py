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
