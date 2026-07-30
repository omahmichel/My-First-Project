from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from businesses.models import Business, BusinessMembership
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

        user = self.request.user

        business = get_object_or_404(
            Business.objects.filter(
                Q(owner=user)
                | Q(
                    memberships__user=user,
                    memberships__is_active=True,
                )
            )
            .select_related("owner")
            .distinct(),
            pk=self.kwargs["business_id"],
            status=Business.Status.ACTIVE,
        )

        if business.owner_id == user.id:
            role = BusinessMembership.Role.OWNER
        else:
            membership = get_object_or_404(
                BusinessMembership,
                business=business,
                user=user,
                is_active=True,
            )
            role = membership.role

        self._business_and_role = (business, role)
        return self._business_and_role

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
        }

    def get_sale(self):
        business, _, denied_response = self.require_sales_access()

        if denied_response:
            return None, denied_response

        sale = get_object_or_404(
            Sale.objects.select_related(
                "business",
                "customer",
                "cashier",
            ).prefetch_related("items", "payments", "waybill"),
            pk=self.kwargs["sale_id"],
            business=business,
        )

        return sale, None


class BusinessSaleListCreateAPIView(
    BusinessSaleAccessMixin,
    APIView,
):
    # Lists sales and completes one protected checkout transaction.

    permission_classes = (IsAuthenticated,)

    def get(self, request, business_id):
        business, _, denied_response = self.require_sales_access()

        if denied_response:
            return denied_response

        sales = (
            Sale.objects.filter(business=business)
            .select_related(
                "business",
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
            Sale.objects.filter(
                business=business,
                idempotency_key=idempotency_key,
            )
            .select_related(
                "business",
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

        try:
            sale, replayed = create_completed_sale(
                business=business,
                user=request.user,
                data=serializer.validated_data,
                idempotency_key=idempotency_key,
            )
        except IntegrityError:
            sale = get_object_or_404(
                Sale.objects.select_related(
                    "business",
                    "customer",
                    "cashier",
                ).prefetch_related("items", "payments", "waybill"),
                business=business,
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
                Sale.objects.select_for_update(),
                pk=sale_id,
                business=business,
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

        try:
            payment, replayed = record_customer_debt_payment(
                business=business,
                customer_id=customer_id,
                user=request.user,
                data=serializer.validated_data,
                idempotency_key=idempotency_key,
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
