from datetime import timedelta

from django.db import transaction
from django.http import Http404
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import Business, SubscriptionPayment
from .paystack_client import PaystackClient, PaystackError


class SubscriptionPaymentError(Exception):
    """Represents a safe subscription payment processing failure."""

    def __init__(self, message, *, code="subscription_payment_error"):
        # Keeps service failures structured for future API responses.
        super().__init__(message)
        self.code = code


def get_payable_business_for_owner(*, user, business_id):
    # Allows only the active business owner to start a subscription payment.
    try:
        return Business.objects.select_related("owner").get(
            pk=business_id,
            owner=user,
            status=Business.Status.ACTIVE,
        )
    except Business.DoesNotExist as exc:
        # Returns the same not-found result for missing and unauthorized IDs.
        raise Http404("Business not found.") from exc


def initialize_subscription_payment(
    *,
    user,
    business_id,
    callback_url="",
    client=None,
):
    # Creates the local audit record before opening Paystack checkout.
    business = get_payable_business_for_owner(
        user=user,
        business_id=business_id,
    )
    gateway_client = client or PaystackClient()

    payment = SubscriptionPayment.objects.create(
        business=business,
        initiated_by=user,
        initiated_by_email=user.email,
        initiated_by_name=user.full_name,
    )

    metadata = {
        "business_id": str(business.id),
        "subscription_payment_id": str(payment.id),
        "subscription_days": payment.duration_days,
    }

    try:
        response = gateway_client.initialize_transaction(
            email=payment.initiated_by_email,
            amount_subunit=payment.amount_subunit,
            reference=payment.reference,
            currency=payment.currency,
            callback_url=callback_url,
            metadata=metadata,
        )
    except PaystackError as exc:
        # Keeps a failed audit row without exposing server credentials.
        payment.status = SubscriptionPayment.Status.FAILED
        payment.failure_reason = str(exc)
        payment.save(
            update_fields=(
                "status",
                "failure_reason",
                "updated_at",
            )
        )
        raise

    if response["reference"] != payment.reference:
        payment.status = SubscriptionPayment.Status.FAILED
        payment.failure_reason = (
            "Paystack returned a different payment reference."
        )
        payment.provider_response = {
            "initialization": _safe_initialization_snapshot(response)
        }
        payment.save(
            update_fields=(
                "status",
                "failure_reason",
                "provider_response",
                "updated_at",
            )
        )
        raise SubscriptionPaymentError(
            "Paystack returned an invalid payment reference.",
            code="payment_reference_mismatch",
        )

    payment.authorization_url = response["authorization_url"]
    payment.access_code = response["access_code"]
    payment.provider_response = {
        "initialization": _safe_initialization_snapshot(response)
    }
    payment.save(
        update_fields=(
            "authorization_url",
            "access_code",
            "provider_response",
            "updated_at",
        )
    )

    return payment


def verify_and_fulfill_subscription_payment(
    *,
    reference,
    client=None,
):
    # Returns immediately when a prior request already delivered the value.
    try:
        existing_payment = SubscriptionPayment.objects.select_related(
            "business"
        ).get(reference=reference)
    except SubscriptionPayment.DoesNotExist as exc:
        raise SubscriptionPaymentError(
            "The subscription payment reference was not found.",
            code="subscription_payment_not_found",
        ) from exc

    if existing_payment.is_fulfilled:
        return existing_payment, existing_payment.business, False

    gateway_client = client or PaystackClient()
    verification = gateway_client.verify_transaction(reference)
    deferred_error = None

    with transaction.atomic():
        # Locks both records so callback and webhook cannot extend twice.
        payment = (
            SubscriptionPayment.objects.select_for_update()
            .select_related("business")
            .get(pk=existing_payment.pk)
        )
        business = Business.objects.select_for_update().get(
            pk=payment.business_id
        )

        if payment.is_fulfilled:
            return payment, business, False

        _store_verification_snapshot(payment, verification)
        deferred_error = _get_verification_error(
            payment,
            verification,
        )

        if deferred_error is not None:
            # Commits safe failure evidence before raising outside atomic.
            payment.save(
                update_fields=(
                    "status",
                    "provider_transaction_id",
                    "provider_status",
                    "channel",
                    "paid_at",
                    "failure_reason",
                    "provider_response",
                    "updated_at",
                )
            )
        else:
            _activate_paid_subscription(
                business=business,
                payment=payment,
            )

    if deferred_error is not None:
        raise deferred_error

    return payment, business, True


def _activate_paid_subscription(*, business, payment):
    # Adds one paid period only after the locked verification succeeds.
    now = timezone.now()
    current_end = business.subscription_ends_at

    if (
        business.subscription_status
        == Business.SubscriptionStatus.ACTIVE
        and current_end
        and current_end > now
    ):
        # Renews from the existing paid expiry without losing days.
        subscription_base = current_end
        subscription_start = business.subscription_started_at or now
    else:
        # A first payment or expired renewal starts when verified.
        subscription_base = now
        subscription_start = now

    business.subscription_status = Business.SubscriptionStatus.ACTIVE
    business.subscription_started_at = subscription_start
    business.subscription_ends_at = (
        subscription_base + timedelta(days=payment.duration_days)
    )
    business.save(
        update_fields=(
            "subscription_status",
            "subscription_started_at",
            "subscription_ends_at",
            "updated_at",
        )
    )

    payment.status = SubscriptionPayment.Status.SUCCESSFUL
    payment.verified_at = now
    payment.fulfilled_at = now
    payment.failure_reason = ""
    payment.save(
        update_fields=(
            "status",
            "provider_transaction_id",
            "provider_status",
            "channel",
            "paid_at",
            "verified_at",
            "fulfilled_at",
            "failure_reason",
            "provider_response",
            "updated_at",
        )
    )


def _safe_initialization_snapshot(response):
    # Stores only checkout fields needed for support and reconciliation.
    allowed_fields = (
        "authorization_url",
        "access_code",
        "reference",
    )
    return {
        field: response.get(field)
        for field in allowed_fields
        if response.get(field) not in (None, "")
    }


def _safe_verification_snapshot(verification):
    # Excludes authorization codes, customer data and other excess fields.
    allowed_fields = (
        "id",
        "status",
        "reference",
        "amount",
        "currency",
        "channel",
        "paid_at",
        "transaction_date",
        "gateway_response",
        "fees",
    )
    return {
        field: verification.get(field)
        for field in allowed_fields
        if verification.get(field) not in (None, "")
    }


def _store_verification_snapshot(payment, verification):
    # Saves only the gateway evidence needed for payment reconciliation.
    payment.provider_status = str(
        verification.get("status", "")
    ).strip()
    payment.provider_transaction_id = str(
        verification.get("id", "")
    ).strip()
    payment.channel = str(
        verification.get("channel", "")
    ).strip()
    payment.provider_response = {
        **payment.provider_response,
        "verification": _safe_verification_snapshot(verification),
    }

    paid_at_value = verification.get("paid_at")

    if isinstance(paid_at_value, str):
        payment.paid_at = parse_datetime(paid_at_value)


def _get_verification_error(payment, verification):
    # Returns a structured error while allowing the audit save to commit.
    if verification.get("status") != "success":
        payment.status = SubscriptionPayment.Status.PENDING
        payment.failure_reason = ""
        return SubscriptionPaymentError(
            "The payment has not been completed successfully.",
            code="subscription_payment_not_successful",
        )

    expected_values = {
        "reference": payment.reference,
        "amount": payment.amount_subunit,
        "currency": payment.currency,
    }
    received_values = {
        "reference": verification.get("reference"),
        "amount": verification.get("amount"),
        "currency": str(
            verification.get("currency", "")
        ).upper(),
    }
    mismatched_fields = [
        field
        for field, expected in expected_values.items()
        if received_values[field] != expected
    ]

    if mismatched_fields:
        payment.status = SubscriptionPayment.Status.FAILED
        payment.failure_reason = (
            "Paystack verification did not match the expected "
            + ", ".join(mismatched_fields)
            + "."
        )
        return SubscriptionPaymentError(
            "The verified payment details did not match StockFlow.",
            code="subscription_payment_mismatch",
        )

    if not payment.provider_transaction_id:
        payment.status = SubscriptionPayment.Status.FAILED
        payment.failure_reason = (
            "Paystack verification did not include a transaction ID."
        )
        return SubscriptionPaymentError(
            "The verified payment was incomplete.",
            code="subscription_payment_invalid_response",
        )

    duplicate_transaction = (
        SubscriptionPayment.objects.exclude(pk=payment.pk)
        .filter(
            gateway=payment.gateway,
            provider_transaction_id=payment.provider_transaction_id,
        )
        .exists()
    )

    if duplicate_transaction:
        # Clears the constrained field while retaining it in the snapshot.
        payment.provider_transaction_id = ""
        payment.status = SubscriptionPayment.Status.FAILED
        payment.failure_reason = (
            "The Paystack transaction was already used by another "
            "subscription payment."
        )
        return SubscriptionPaymentError(
            "This payment transaction has already been processed.",
            code="subscription_transaction_reused",
        )

    return None
