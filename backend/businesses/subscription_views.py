import hashlib
import hmac
import json

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from sales.mobile_money_service import (
    MobileMoneyPaymentError,
    verify_and_finalize_mobile_money_sale,
)

from .models import SubscriptionPayment
from .paystack_client import (
    PaystackConfigurationError,
    PaystackRequestError,
)
from .subscription_service import (
    SubscriptionPaymentError,
    get_payable_business_for_owner,
    initialize_subscription_payment,
    verify_and_fulfill_subscription_payment,
)


def _payment_response(payment, business=None, *, activated=None):
    # Returns only payment fields required by the StockFlow frontend.
    payload = {
        "reference": payment.reference,
        "status": payment.status,
        "amount": str(payment.amount),
        "currency": payment.currency,
        "durationDays": payment.duration_days,
        "authorizationUrl": payment.authorization_url,
        "paidAt": payment.paid_at,
        "verifiedAt": payment.verified_at,
        "fulfilledAt": payment.fulfilled_at,
    }

    if business is not None:
        payload["subscriptionStatus"] = business.subscription_status
        payload["subscriptionStartedAt"] = (
            business.subscription_started_at
        )
        payload["subscriptionEndsAt"] = business.subscription_ends_at
        payload["hasSystemAccess"] = business.has_system_access

    if activated is not None:
        payload["activated"] = activated

    return payload


def _service_error_response(exc):
    # Maps controlled service errors to stable frontend response codes.
    status_code = status.HTTP_400_BAD_REQUEST

    if exc.code == "subscription_payment_not_found":
        status_code = status.HTTP_404_NOT_FOUND
    elif exc.code == "subscription_payment_not_successful":
        status_code = status.HTTP_409_CONFLICT

    return Response(
        {
            "detail": str(exc),
            "code": exc.code,
        },
        status=status_code,
    )


def _gateway_error_response(exc):
    # Hides credentials while distinguishing setup and network failures.
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


class SubscriptionPaymentInitializeAPIView(APIView):
    """Creates an owner-only Paystack checkout for one business."""

    permission_classes = (IsAuthenticated,)
    throttle_scope = "subscription_payment_initialize"

    def post(self, request, business_id):
        # Uses only the callback URL configured by the StockFlow server.
        callback_url = settings.PAYMENT_CALLBACK_URL

        if not callback_url:
            return Response(
                {
                    "detail": (
                        "The subscription payment callback URL "
                        "is not configured."
                    ),
                    "code": "payment_callback_not_configured",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            payment = initialize_subscription_payment(
                user=request.user,
                business_id=business_id,
                callback_url=callback_url,
            )
        except (
            PaystackConfigurationError,
            PaystackRequestError,
        ) as exc:
            return _gateway_error_response(exc)
        except SubscriptionPaymentError as exc:
            return _service_error_response(exc)

        return Response(
            _payment_response(payment),
            status=status.HTTP_201_CREATED,
        )


class SubscriptionPaymentVerifyAPIView(APIView):
    """Verifies one owner payment and returns the paid access state."""

    permission_classes = (IsAuthenticated,)
    throttle_scope = "subscription_payment_verify"

    def post(self, request, business_id, reference):
        # Confirms ownership and business isolation before verification.
        business = get_payable_business_for_owner(
            user=request.user,
            business_id=business_id,
        )
        get_object_or_404(
            SubscriptionPayment,
            business=business,
            reference=reference,
        )

        try:
            payment, business, activated = (
                verify_and_fulfill_subscription_payment(
                    reference=reference,
                )
            )
        except (
            PaystackConfigurationError,
            PaystackRequestError,
        ) as exc:
            return _gateway_error_response(exc)
        except SubscriptionPaymentError as exc:
            return _service_error_response(exc)

        return Response(
            _payment_response(
                payment,
                business,
                activated=activated,
            ),
            status=status.HTTP_200_OK,
        )


class PaystackWebhookAPIView(APIView):
    """Receives signed Paystack events and verifies successful charges."""

    authentication_classes = ()
    permission_classes = (AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "paystack_webhook"

    def post(self, request):
        # Validates the signature against the exact raw request body.
        secret_key = settings.PAYMENT_GATEWAY_SECRET_KEY

        if (
            settings.PAYMENT_GATEWAY != "paystack"
            or not secret_key
        ):
            return Response(
                {"detail": "Payment webhook is unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        raw_body = request.body
        received_signature = request.headers.get(
            "x-paystack-signature",
            "",
        )
        expected_signature = hmac.new(
            secret_key.encode("utf-8"),
            raw_body,
            hashlib.sha512,
        ).hexdigest()

        if (
            not received_signature
            or not hmac.compare_digest(
                received_signature,
                expected_signature,
            )
        ):
            return Response(
                {"detail": "Invalid webhook signature."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            event = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return Response(
                {"detail": "Invalid webhook payload."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Paystack sends other account events that are not subscriptions.
        if event.get("event") != "charge.success":
            return Response(
                {
                    "received": True,
                    "processed": False,
                },
                status=status.HTTP_200_OK,
            )

        event_data = event.get("data")

        if not isinstance(event_data, dict):
            return Response(
                {"detail": "Invalid webhook event data."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reference = str(event_data.get("reference", "")).strip()

        if not reference:
            return Response(
                {"detail": "Webhook reference is missing."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            _, _, activated = (
                verify_and_fulfill_subscription_payment(
                    reference=reference,
                )
            )
        except SubscriptionPaymentError as exc:
            # A non-subscription reference may belong to a sales payment.
            if exc.code == "subscription_payment_not_found":
                try:
                    _, _, finalized = (
                        verify_and_finalize_mobile_money_sale(
                            reference=reference,
                        )
                    )
                except MobileMoneyPaymentError as sale_exc:
                    # Unknown Paystack charges remain safely ignored.
                    if sale_exc.code == "mobile_money_payment_not_found":
                        return Response(
                            {
                                "received": True,
                                "processed": False,
                            },
                            status=status.HTTP_200_OK,
                        )

                    # Permanent sale failures are already audited locally.
                    if sale_exc.code in {
                        "mobile_money_payment_mismatch",
                        "mobile_money_transaction_reused",
                        "mobile_money_payment_failed",
                        "mobile_money_sale_not_pending",
                        "mobile_money_reservation_invalid",
                        "mobile_money_amount_invalid",
                        "mobile_money_customer_required",
                        "mobile_money_reserved_product_missing",
                    }:
                        return Response(
                            {
                                "received": True,
                                "processed": False,
                            },
                            status=status.HTTP_200_OK,
                        )

                    # Temporary verification states should be retried.
                    return Response(
                        {
                            "detail": str(sale_exc),
                            "code": sale_exc.code,
                        },
                        status=status.HTTP_503_SERVICE_UNAVAILABLE,
                    )
                except (
                    PaystackConfigurationError,
                    PaystackRequestError,
                ):
                    return Response(
                        {
                            "detail": (
                                "Payment verification is unavailable."
                            )
                        },
                        status=status.HTTP_503_SERVICE_UNAVAILABLE,
                    )

                return Response(
                    {
                        "received": True,
                        "processed": True,
                        "saleFinalized": finalized,
                    },
                    status=status.HTTP_200_OK,
                )

            # Permanent subscription mismatches should not be retried.
            if exc.code in {
                "subscription_payment_mismatch",
                "subscription_payment_invalid_response",
                "subscription_transaction_reused",
            }:
                return Response(
                    {
                        "received": True,
                        "processed": False,
                    },
                    status=status.HTTP_200_OK,
                )

            # Temporary states return an error so delivery can be retried.
            return Response(
                {
                    "detail": str(exc),
                    "code": exc.code,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except (
            PaystackConfigurationError,
            PaystackRequestError,
        ):
            return Response(
                {"detail": "Payment verification is unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "received": True,
                "processed": True,
                "activated": activated,
            },
            status=status.HTTP_200_OK,
        )
