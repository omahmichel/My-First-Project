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
# StockFlow safe data import v1.
from rest_framework import status as import_status
from rest_framework.exceptions import ValidationError as ImportValidationError

from .imports.service import (
    apply_import_preview,
    create_import_preview,
    list_import_audits,
)
from .serializers import (
    DataImportApplyRequestSerializer,
    DataImportPreviewRequestSerializer,
)


def _import_owner_business(*, request, business_id):
    business, role = get_business_and_role_for_user(
        user=request.user,
        business_id=business_id,
    )
    if role != BusinessMembership.Role.OWNER:
        raise PermissionDenied(
            "Only the business owner can preview or apply bulk data imports."
        )
    return business


def _selected_import_branch(*, business, branch_id):
    if not branch_id:
        return None
    branch = business.branches.filter(id=branch_id, is_active=True).first()
    if not branch:
        raise ImportValidationError(
            {"branchId": "Select an active branch from this business."}
        )
    return branch


class DataImportCollectionAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, business_id):
        business = _import_owner_business(
            request=request,
            business_id=business_id,
        )
        return Response(list_import_audits(business=business))


class DataImportPreviewAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, business_id):
        business = _import_owner_business(
            request=request,
            business_id=business_id,
        )
        serializer = DataImportPreviewRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        branch = _selected_import_branch(
            business=business,
            branch_id=serializer.validated_data.get("branchId"),
        )
        result = create_import_preview(
            business=business,
            branch=branch,
            dataset=serializer.validated_data["dataset"],
            upload=serializer.validated_data["file"],
            user=request.user,
            request=request,
        )
        return Response(result, status=import_status.HTTP_201_CREATED)


class DataImportApplyAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, business_id, import_id):
        business = _import_owner_business(
            request=request,
            business_id=business_id,
        )
        serializer = DataImportApplyRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = apply_import_preview(
            business=business,
            import_id=import_id,
            preview_token=serializer.validated_data["previewToken"],
            user=request.user,
            request=request,
        )
        return Response(result)



# StockFlow outbound intelligence messaging v1.
from .messaging.service import (
    delivery_payload,
    list_deliveries,
    messaging_capabilities,
    send_test_sms,
)
from .models import MessagingPreference
from .serializers import MessagingPreferenceSerializer


class MessagingCapabilitiesAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, business_id):
        _import_owner_business(request=request, business_id=business_id)
        return Response(messaging_capabilities())


class MessagingPreferenceAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def _preference(self, *, request, business_id):
        business = _import_owner_business(
            request=request,
            business_id=business_id,
        )
        preference, _ = MessagingPreference.objects.get_or_create(
            business=business,
        )
        return business, preference

    def get(self, request, business_id):
        _business, preference = self._preference(
            request=request,
            business_id=business_id,
        )
        return Response(MessagingPreferenceSerializer(preference).data)

    def patch(self, request, business_id):
        _business, preference = self._preference(
            request=request,
            business_id=business_id,
        )
        serializer = MessagingPreferenceSerializer(
            preference,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class MessagingDeliveryCollectionAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, business_id):
        business = _import_owner_business(
            request=request,
            business_id=business_id,
        )
        return Response(list_deliveries(business=business))


class MessagingTestSmsAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, business_id):
        business = _import_owner_business(
            request=request,
            business_id=business_id,
        )
        preference, _ = MessagingPreference.objects.get_or_create(
            business=business,
        )
        if not preference.sms_enabled:
            raise ImportValidationError(
                {"smsEnabled": "Enable SMS alerts before sending a test message."}
            )
        try:
            delivery = send_test_sms(
                business=business,
                preference=preference,
            )
        except ValueError as exc:
            raise ImportValidationError(
                {"recipientPhone": str(exc)}
            ) from exc
        payload = delivery_payload(delivery)
        response_status = (
            import_status.HTTP_201_CREATED
            if delivery.status == delivery.Status.SENT
            else import_status.HTTP_502_BAD_GATEWAY
        )
        return Response(payload, status=response_status)
