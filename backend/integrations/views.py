import csv

from django.http import HttpResponse
from django.utils.text import slugify
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from businesses.access import get_business_and_role_for_user
from businesses.models import BusinessMembership

from .serializers import AccountingExportQuerySerializer
from .services.accounting_exports import (
    DATASETS,
    accounting_export_manifest,
    build_accounting_export,
)


def _owner_business(*, request, business_id):
    business, role = get_business_and_role_for_user(
        user=request.user,
        business_id=business_id,
    )
    if role != BusinessMembership.Role.OWNER:
        raise PermissionDenied(
            "Only the business owner can export accounting integration data."
        )
    return business


def _safe_csv_cell(value):
    if value is None:
        return ""
    if not isinstance(value, str):
        return value
    text = value
    if text and text[0] in ("=", "+", "-", "@"):
        return "'" + text
    return text


def _csv_response(*, business, dataset, export):
    business_slug = slugify(business.name) or "business"
    filename = f"{business_slug}-stockflow-{dataset}.csv"
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(export["headers"])
    for row in export["rows"]:
        writer.writerow([_safe_csv_cell(value) for value in row])
    return response


class AccountingExportManifestAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, business_id):
        business = _owner_business(
            request=request, business_id=business_id
        )
        payload = accounting_export_manifest()
        payload["business"] = {
            "id": str(business.id),
            "name": business.name,
            "businessType": business.business_type,
        }
        payload["exportPathTemplate"] = (
            f"/api/businesses/{business.id}/integrations/"
            "accounting/exports/{dataset}/"
        )
        return Response(payload)


class AccountingExportCsvAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, business_id, dataset):
        business = _owner_business(
            request=request, business_id=business_id
        )
        if dataset not in DATASETS:
            raise NotFound("Unknown accounting export dataset.")

        query = AccountingExportQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        export = build_accounting_export(
            business=business,
            dataset=dataset,
            date_from=query.validated_data.get("dateFrom"),
            date_to=query.validated_data.get("dateTo"),
        )
        return _csv_response(
            business=business, dataset=dataset, export=export
        )
