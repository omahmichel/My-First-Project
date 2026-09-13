from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from integrations.messaging.provider import MessagingProviderError
from integrations.messaging.whatsapp_live import (
    send_whatsapp_document,
    whatsapp_configured,
)

from businesses.access import get_business_and_role_for_user
from businesses.branch_access import (
    branch_queryset_for_user,
    resolve_branch_for_user,
)
from businesses.models import BusinessMembership
from businesses.paystack_client import (
    PaystackConfigurationError,
    PaystackRequestError,
)
from .mobile_money_service import (
    MobileMoneyPaymentError,
    initialize_mobile_money_debt_payment,
    initialize_mobile_money_sale,
    verify_and_finalize_mobile_money_debt_payment,
    verify_and_finalize_mobile_money_sale,
)
from .models import DocumentSequence, Payment, Sale, Waybill
from .serializers import (
    CreateSaleSerializer,
    DebtPaymentSerializer,
    PaymentSerializer,
    SaleSerializer,
    WaybillSerializer,
    WaybillUpsertSerializer,
)
from .services import (
    create_completed_sale,
    record_customer_debt_payment,
)


def _request_uses_mobile_money(request):
    # Applies the gateway throttle only to checkouts needing a phone prompt.
    if request.method != "POST":
        return False

    data = request.data
    return (
        data.get("paymentMethod") == Sale.PaymentMethod.MOBILE_MONEY
        or data.get("amountPaidMethod") == Payment.Method.MOBILE_MONEY
    )


def _mobile_money_service_error_response(exc):
    # Maps controlled payment states to stable frontend response codes.
    status_code = status.HTTP_400_BAD_REQUEST

    if exc.code in {
        "mobile_money_payment_not_found",
        "mobile_money_debt_payment_not_found",
        "mobile_money_customer_not_found",
    }:
        status_code = status.HTTP_404_NOT_FOUND
    elif exc.code in {
        "mobile_money_payment_pending",
        "mobile_money_payment_failed",
        "mobile_money_sale_not_pending",
        "mobile_money_debt_not_pending",
        "mobile_money_debt_balance_changed",
        "mobile_money_transaction_reused",
        "mobile_money_reservation_invalid",
    }:
        status_code = status.HTTP_409_CONFLICT

    return Response(
        {
            "detail": str(exc),
            "code": exc.code,
        },
        status=status_code,
    )


def _mobile_money_gateway_error_response(exc):
    # Hides credentials while distinguishing setup and gateway failures.
    status_code = status.HTTP_502_BAD_GATEWAY

    if isinstance(exc, PaystackConfigurationError):
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return Response(
        {
            "detail": str(exc),
            "code": exc.code,
        },
        status=status_code,
    )


class BusinessSaleAccessMixin:
    # Resolves one active business and the authenticated user's role.

    allowed_roles = (
        BusinessMembership.Role.OWNER,
        BusinessMembership.Role.MANAGER,
        BusinessMembership.Role.CASHIER,
    )

    def get_business_and_role(self):
        if hasattr(self, "_business_and_role"):
            return self._business_and_role

        self._business_and_role = get_business_and_role_for_user(
            user=self.request.user,
            business_id=self.kwargs["business_id"],
        )
        return self._business_and_role

    def get_branch(self, branch_id=None):
        business, role = self.get_business_and_role()
        requested_id = (
            branch_id
            or self.request.query_params.get("branchId")
            or self.request.data.get("branchId")
        )
        return resolve_branch_for_user(
            business=business,
            user=self.request.user,
            role=role,
            branch_id=requested_id,
        )

    def branch_scoped_sales(self, queryset):
        business, role = self.get_business_and_role()
        branches = branch_queryset_for_user(
            business=business,
            user=self.request.user,
            role=role,
        )
        scope = Q(branch__in=branches)
        if branches.filter(is_main=True).exists():
            scope |= Q(branch__isnull=True)
        return queryset.filter(business=business).filter(scope)

    def require_sales_access(self):
        business, role = self.get_business_and_role()

        if role not in self.allowed_roles:
            return None, None, Response(
                {
                    "detail": (
                        "Your role does not allow access to sales."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        return business, role, None

    def get_serializer_context(self):
        business, role = self.get_business_and_role()

        return {
            "request": self.request,
            "business": business,
            "current_role": role,
            "branch": self.get_branch(),
        }

    def get_sale(self):
        business, _, denied_response = self.require_sales_access()

        if denied_response:
            return None, denied_response

        sale = get_object_or_404(
            self.branch_scoped_sales(
                Sale.objects.select_related(
                    "business",
                    "branch",
                    "customer",
                    "cashier",
                ).prefetch_related("items", "payments", "waybill")
            ),
            pk=self.kwargs["sale_id"],
        )

        return sale, None


class BusinessSaleListCreateAPIView(
    BusinessSaleAccessMixin,
    APIView,
):
    # Lists sales and completes one protected checkout transaction.

    permission_classes = (IsAuthenticated,)

    def get_throttles(self):
        # Adds the stricter scope only to Mobile Money sale requests.
        self.throttle_scope = (
            "mobile_money_sale_initialize"
            if _request_uses_mobile_money(self.request)
            else None
        )
        return super().get_throttles()

    def get(self, request, business_id):
        business, _, denied_response = self.require_sales_access()

        if denied_response:
            return denied_response

        branch = self.get_branch()
        branch_filter = {"branch": branch}
        sales_queryset = Sale.objects.filter(business=business)
        if branch.is_main:
            sales_queryset = sales_queryset.filter(
                Q(branch=branch) | Q(branch__isnull=True)
            )
        else:
            sales_queryset = sales_queryset.filter(**branch_filter)

        sales = (
            sales_queryset
            .select_related(
                "business",
                "branch",
                "customer",
                "cashier",
            )
            .prefetch_related("items", "payments", "waybill")
            .order_by("-created_at")
        )

        return Response(
            SaleSerializer(
                sales,
                many=True,
                context=self.get_serializer_context(),
            ).data
        )

    def post(self, request, business_id):
        business, _, denied_response = self.require_sales_access()

        if denied_response:
            return denied_response

        idempotency_key = request.headers.get(
            "Idempotency-Key",
            "",
        ).strip()

        if not idempotency_key:
            return Response(
                {
                    "detail": (
                        "Idempotency-Key header is required."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(idempotency_key) > 128:
            return Response(
                {
                    "detail": (
                        "Idempotency-Key cannot exceed 128 characters."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing_sale = (
            self.branch_scoped_sales(
                Sale.objects.filter(idempotency_key=idempotency_key)
            )
            .select_related(
                "business",
                "branch",
                "customer",
                "cashier",
            )
            .prefetch_related("items", "payments", "waybill")
            .first()
        )

        if existing_sale:
            response = Response(
                SaleSerializer(
                    existing_sale,
                    context=self.get_serializer_context(),
                ).data,
                status=status.HTTP_200_OK,
            )
            response["Idempotent-Replay"] = "true"
            return response

        serializer = CreateSaleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        branch = self.get_branch(serializer.validated_data.get("branchId"))

        uses_mobile_money = (
            serializer.validated_data["paymentMethod"]
            == Sale.PaymentMethod.MOBILE_MONEY
            or (
                serializer.validated_data["paymentMethod"]
                == Sale.PaymentMethod.CREDIT
                and serializer.validated_data.get("amountPaid")
                and serializer.validated_data.get("amountPaidMethod")
                == Payment.Method.MOBILE_MONEY
            )
        )

        try:
            if uses_mobile_money:
                sale, _, replayed = initialize_mobile_money_sale(
                    business=business,
                    user=request.user,
                    data=serializer.validated_data,
                    idempotency_key=idempotency_key,
                    branch=branch,
                )
            else:
                sale, replayed = create_completed_sale(
                    business=business,
                    user=request.user,
                    data=serializer.validated_data,
                    idempotency_key=idempotency_key,
                    branch=branch,
                )
        except (
            PaystackConfigurationError,
            PaystackRequestError,
        ) as exc:
            return _mobile_money_gateway_error_response(exc)
        except MobileMoneyPaymentError as exc:
            return _mobile_money_service_error_response(exc)
        except IntegrityError:
            sale = get_object_or_404(
                self.branch_scoped_sales(
                    Sale.objects.select_related(
                        "business",
                        "branch",
                        "customer",
                        "cashier",
                    ).prefetch_related("items", "payments", "waybill")
                ),
                idempotency_key=idempotency_key,
            )
            replayed = True

        response = Response(
            SaleSerializer(
                sale,
                context=self.get_serializer_context(),
            ).data,
            status=(
                status.HTTP_200_OK
                if replayed
                else status.HTTP_201_CREATED
            ),
        )

        if replayed:
            response["Idempotent-Replay"] = "true"

        return response


class BusinessMobileMoneySaleVerifyAPIView(
    BusinessSaleAccessMixin,
    APIView,
):
    # Verifies one business-isolated Paystack Mobile Money sale.

    permission_classes = (IsAuthenticated,)
    throttle_scope = "mobile_money_sale_verify"

    def post(self, request, business_id, reference):
        business, _, denied_response = self.require_sales_access()

        if denied_response:
            return denied_response

        # Hides references that belong to a different business.
        get_object_or_404(
            Payment.objects.select_related("sale"),
            business=business,
            gateway="paystack",
            gateway_reference=reference,
            method=Payment.Method.MOBILE_MONEY,
            payment_type=Payment.PaymentType.SALE_PAYMENT,
            sale__in=self.branch_scoped_sales(Sale.objects.all()),
        )

        try:
            _, sale, finalized = (
                verify_and_finalize_mobile_money_sale(
                    reference=reference,
                )
            )
        except (
            PaystackConfigurationError,
            PaystackRequestError,
        ) as exc:
            return _mobile_money_gateway_error_response(exc)
        except MobileMoneyPaymentError as exc:
            return _mobile_money_service_error_response(exc)

        response = Response(
            SaleSerializer(
                sale,
                context=self.get_serializer_context(),
            ).data,
            status=status.HTTP_200_OK,
        )

        if not finalized:
            response["Idempotent-Replay"] = "true"

        return response




class BusinessMobileMoneyDebtPaymentVerifyAPIView(
    BusinessSaleAccessMixin,
    APIView,
):
    # Verifies one business-isolated Mobile Money debt payment.

    permission_classes = (IsAuthenticated,)
    throttle_scope = "mobile_money_debt_verify"

    def post(self, request, business_id, customer_id, reference):
        business, _, denied_response = self.require_sales_access()
        if denied_response:
            return denied_response

        get_object_or_404(
            Payment.objects.select_related("sale", "customer"),
            business=business,
            customer_id=customer_id,
            gateway="paystack",
            gateway_reference=reference,
            method=Payment.Method.MOBILE_MONEY,
            payment_type=Payment.PaymentType.DEBT_PAYMENT,
            sale__in=self.branch_scoped_sales(Sale.objects.all()),
        )
        try:
            payment, _, _, finalized = (
                verify_and_finalize_mobile_money_debt_payment(
                    reference=reference,
                )
            )
        except (PaystackConfigurationError, PaystackRequestError) as exc:
            return _mobile_money_gateway_error_response(exc)
        except MobileMoneyPaymentError as exc:
            return _mobile_money_service_error_response(exc)

        response = Response(
            PaymentSerializer(payment).data,
            status=status.HTTP_200_OK,
        )
        if not finalized:
            response["Idempotent-Replay"] = "true"
        return response


class BusinessSaleDetailAPIView(
    BusinessSaleAccessMixin,
    APIView,
):
    # Retrieves one business-isolated sale and its payment history.

    permission_classes = (IsAuthenticated,)

    def get(self, request, business_id, sale_id):
        sale, denied_response = self.get_sale()

        if denied_response:
            return denied_response

        return Response(
            SaleSerializer(
                sale,
                context=self.get_serializer_context(),
            ).data
        )



class BusinessSaleWaybillAPIView(
    BusinessSaleAccessMixin,
    APIView,
):
    # Creates or updates one business-isolated waybill for a sale.

    permission_classes = (IsAuthenticated,)

    def _save_waybill(
        self,
        request,
        business_id,
        sale_id,
        *,
        partial=False,
    ):
        business, _, denied_response = self.require_sales_access()

        if denied_response:
            return denied_response

        serializer = WaybillUpsertSerializer(
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            sale = get_object_or_404(
                self.branch_scoped_sales(
                    Sale.objects.select_for_update()
                ),
                pk=sale_id,
            )
            waybill = (
                Waybill.objects.select_for_update()
                .filter(
                    business=business,
                    sale=sale,
                )
                .first()
            )
            created = waybill is None

            if created:
                sequence, _ = (
                    DocumentSequence.objects.select_for_update()
                    .get_or_create(business=business)
                )
                prefix = (
                    getattr(business, "waybill_prefix", "")
                    or "WB"
                )
                waybill_number = (
                    f"{prefix}-"
                    f"{sequence.next_waybill_number:05d}"
                )
                sequence.next_waybill_number += 1
                sequence.save(
                    update_fields=(
                        "next_waybill_number",
                        "updated_at",
                    )
                )
                waybill = Waybill(
                    business=business,
                    sale=sale,
                    waybill_number=waybill_number,
                    created_by=request.user,
                )

            for field, value in serializer.validated_data.items():
                setattr(waybill, field, value)

            waybill.save()

        return Response(
            WaybillSerializer(waybill).data,
            status=(
                status.HTTP_201_CREATED
                if created
                else status.HTTP_200_OK
            ),
        )

    def post(self, request, business_id, sale_id):
        return self._save_waybill(request, business_id, sale_id)

    def put(self, request, business_id, sale_id):
        return self._save_waybill(request, business_id, sale_id)

    def patch(self, request, business_id, sale_id):
        return self._save_waybill(
            request,
            business_id,
            sale_id,
            partial=True,
        )


class BusinessCustomerDebtPaymentAPIView(
    BusinessSaleAccessMixin,
    APIView,
):
    # Records one later payment against a customer's unpaid invoice.

    permission_classes = (IsAuthenticated,)

    def get_throttles(self):
        # Applies the stricter scope only to Mobile Money debt requests.
        self.throttle_scope = (
            "mobile_money_debt_initialize"
            if _request_uses_mobile_money(self.request)
            else None
        )
        return super().get_throttles()

    def post(self, request, business_id, customer_id):
        business, _, denied_response = self.require_sales_access()

        if denied_response:
            return denied_response

        idempotency_key = request.headers.get(
            "Idempotency-Key",
            "",
        ).strip()

        if not idempotency_key:
            return Response(
                {
                    "detail": (
                        "Idempotency-Key header is required."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(idempotency_key) > 128:
            return Response(
                {
                    "detail": (
                        "Idempotency-Key cannot exceed 128 characters."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing_payment = (
            Payment.objects.filter(
                business=business,
                idempotency_key=idempotency_key,
                sale__in=self.branch_scoped_sales(Sale.objects.all()),
            )
            .select_related(
                "business",
                "sale",
                "customer",
                "initiated_by",
            )
            .first()
        )

        if existing_payment:
            response = Response(
                PaymentSerializer(existing_payment).data,
                status=status.HTTP_200_OK,
            )
            response["Idempotent-Replay"] = "true"
            return response

        serializer = DebtPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        branch = self.get_branch(serializer.validated_data.get("branchId"))

        if (
            serializer.validated_data["paymentMethod"]
            == Payment.Method.MOBILE_MONEY
        ):
            try:
                payment, replayed = initialize_mobile_money_debt_payment(
                    business=business,
                    customer_id=customer_id,
                    user=request.user,
                    data=serializer.validated_data,
                    idempotency_key=idempotency_key,
                    branch=branch,
                )
            except (PaystackConfigurationError, PaystackRequestError) as exc:
                return _mobile_money_gateway_error_response(exc)
            except MobileMoneyPaymentError as exc:
                return _mobile_money_service_error_response(exc)
            except IntegrityError:
                payment = get_object_or_404(
                    Payment.objects.select_related(
                        "business", "sale", "customer", "initiated_by"
                    ),
                    business=business,
                    idempotency_key=idempotency_key,
                )
                replayed = True

            response = Response(
                PaymentSerializer(payment).data,
                status=(
                    status.HTTP_200_OK
                    if replayed
                    else status.HTTP_201_CREATED
                ),
            )
            if replayed:
                response["Idempotent-Replay"] = "true"
            return response

        try:
            payment, replayed = record_customer_debt_payment(
                business=business,
                customer_id=customer_id,
                user=request.user,
                data=serializer.validated_data,
                idempotency_key=idempotency_key,
                branch=branch,
            )
        except IntegrityError:
            payment = get_object_or_404(
                Payment.objects.select_related(
                    "business",
                    "sale",
                    "customer",
                    "initiated_by",
                ),
                business=business,
                idempotency_key=idempotency_key,
            )
            replayed = True

        response = Response(
            PaymentSerializer(payment).data,
            status=(
                status.HTTP_200_OK
                if replayed
                else status.HTTP_201_CREATED
            ),
        )

        if replayed:
            response["Idempotent-Replay"] = "true"

        return response

class WhatsAppSaleDocumentSerializer(serializers.Serializer):
    document = serializers.FileField()
    documentType = serializers.ChoiceField(
        choices=("invoice", "receipt"),
    )
    paymentId = serializers.UUIDField(
        required=False,
        allow_null=True,
    )

    def validate_document(self, value):
        if value.size <= 0:
            raise serializers.ValidationError(
                "The PDF document is empty."
            )

        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError(
                "The PDF document cannot be larger than 10 MB."
            )

        if value.content_type != "application/pdf":
            raise serializers.ValidationError(
                "Only PDF documents can be sent to customers."
            )

        try:
            signature = value.read(5)
            value.seek(0)
        except (AttributeError, OSError) as exc:
            raise serializers.ValidationError(
                "The PDF document could not be read."
            ) from exc

        if signature != b"%PDF-":
            raise serializers.ValidationError(
                "The uploaded file is not a valid PDF document."
            )

        return value

    def validate(self, attrs):
        if (
            attrs.get("documentType") == "receipt"
            and not attrs.get("paymentId")
        ):
            raise serializers.ValidationError(
                {
                    "paymentId": (
                        "Select the receipt payment before sending it."
                    )
                }
            )
        return attrs


class BusinessSaleWhatsAppDocumentAPIView(
    BusinessSaleAccessMixin,
    APIView,
):
    permission_classes = (IsAuthenticated,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "integration_admin"

    def post(self, request, business_id, sale_id):
        business, _, denied_response = self.require_sales_access()

        if denied_response:
            return denied_response

        sale, denied_response = self.get_sale()

        if denied_response:
            return denied_response

        if not str(sale.customer_phone or "").strip():
            return Response(
                {
                    "detail": (
                        "This sale has no customer phone number. "
                        "Add a customer phone before sending documents."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not whatsapp_configured(business):
            return Response(
                {
                    "detail": (
                        "Connect this business to WhatsApp before "
                        "sending invoice or receipt PDFs."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = WhatsAppSaleDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        document_type = serializer.validated_data["documentType"]
        document = serializer.validated_data["document"]

        if document_type == "invoice":
            filename = f"{sale.invoice_number}.pdf"
            caption = (
                f"{business.name} invoice {sale.invoice_number} "
                f"for {sale.customer_name}."
            )
            document_number = sale.invoice_number
        else:
            payment = get_object_or_404(
                Payment.objects.filter(
                    business=business,
                    sale=sale,
                    status=Payment.Status.SUCCESSFUL,
                ),
                pk=serializer.validated_data["paymentId"],
            )

            if not payment.receipt_number:
                return Response(
                    {
                        "detail": (
                            "The selected payment does not have "
                            "a receipt number."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            filename = f"{payment.receipt_number}.pdf"
            caption = (
                f"{business.name} payment receipt "
                f"{payment.receipt_number} for {sale.customer_name}."
            )
            document_number = payment.receipt_number

        try:
            delivery = send_whatsapp_document(
                business=business,
                recipient=sale.customer_phone,
                document=document,
                filename=filename,
                caption=caption,
            )
        except MessagingProviderError as exc:
            return Response(
                {
                    "detail": str(exc),
                    "code": "whatsapp_document_send_failed",
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "status": "sent",
                "provider": delivery["provider"],
                "providerReference": delivery["provider_reference"],
                "documentType": document_type,
                "documentNumber": document_number,
                "filename": filename,
                "recipient": sale.customer_phone,
            },
            status=status.HTTP_201_CREATED,
        )
