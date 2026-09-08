from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .authentication import StockFlowApiKeyAuthentication
from .models import ApiCredential
from .services.accounting_exports import (
    DATASETS,
    accounting_export_manifest,
    build_accounting_export,
)


DATASET_SCOPES = {
    "sales": "sales:read",
    "inventory": "inventory:read",
    "purchases": "purchases:read",
    "customers": "customers:read",
    "suppliers": "suppliers:read",
}


def _credential(request):
    if not isinstance(request.auth, ApiCredential):
        raise PermissionDenied("A StockFlow API key is required.")
    return request.auth


def _require_scope(request, scope):
    credential = _credential(request)
    if scope not in (credential.scopes or []):
        raise PermissionDenied(
            f"This API key does not have the required scope: {scope}."
        )
    return credential


def _rows_as_objects(headers, rows):
    return [dict(zip(headers, row)) for row in rows]


class PublicApiManifestAPIView(APIView):
    authentication_classes = (StockFlowApiKeyAuthentication,)
    permission_classes = (IsAuthenticated,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "public_api"

    def get(self, request):
        credential = _credential(request)
        manifest = accounting_export_manifest()
        return Response({
            "version": "v1",
            "readOnly": True,
            "business": {
                "id": str(credential.business_id),
                "name": credential.business.name,
                "businessType": credential.business.business_type,
            },
            "scopes": credential.scopes,
            "datasets": [
                {
                    "key": item["key"],
                    "label": item["label"],
                    "description": item["description"],
                    "requiredScope": DATASET_SCOPES[item["key"]],
                    "available": DATASET_SCOPES[item["key"]] in credential.scopes,
                }
                for item in manifest["datasets"]
            ],
        })


class PublicApiDatasetAPIView(APIView):
    authentication_classes = (StockFlowApiKeyAuthentication,)
    permission_classes = (IsAuthenticated,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "public_api"

    def get(self, request, dataset):
        if dataset not in DATASETS:
            return Response({"detail": "Unknown public API dataset."}, status=404)
        credential = _require_scope(request, DATASET_SCOPES[dataset])
        export = build_accounting_export(
            business=credential.business,
            dataset=dataset,
            date_from=request.query_params.get("dateFrom") or None,
            date_to=request.query_params.get("dateTo") or None,
        )
        return Response({
            "dataset": dataset,
            "count": len(export["rows"]),
            "results": _rows_as_objects(export["headers"], export["rows"]),
        })
