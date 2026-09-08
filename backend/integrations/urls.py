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
