from datetime import timedelta
from decimal import Decimal
import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from businesses.paystack_client import (
    PaystackClient,
    PaystackConfigurationError,
    PaystackError,
    PaystackRequestError,
)
from customers.models import Customer
from inventory.models import Product, StockMovement

from .models import Payment, Sale, SaleItem
from .services import (
    _apply_debt_payment_allocation_locked,
    _load_customer,
    _load_products,
    _next_document_numbers,
    _next_receipt_number,
    _prepare_lines,
    debt_payment_split,
)


class MobileMoneyPaymentError(Exception):
    """Represents a safe sales Mobile Money processing failure."""

    def __init__(self, message, *, code="mobile_money_payment_error"):
        # Keeps service failures structured for future API responses.
        super().__init__(message)
        self.code = code


def generate_sales_payment_reference():
    # Creates a unique Paystack-safe reference for a sales payment.
    timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
    suffix = uuid.uuid4().hex[:12].upper()
    return f"STF-SALE-{timestamp}-{suffix}"


def _payment_email(*, business, customer, user):
    # Uses the most relevant available email without accepting client input.
    if customer and customer.email:
        return customer.email

    if business.email:
        return business.email

    return user.email


def _mobile_money_amount(*, data, total):
    # Resolves the exact amount Paystack must collect for this checkout.
    if data["paymentMethod"] == Sale.PaymentMethod.MOBILE_MONEY:
        return total

    if (
        data["paymentMethod"] == Sale.PaymentMethod.CREDIT
        and data.get("amountPaidMethod")
        == Payment.Method.MOBILE_MONEY
    ):
        return data.get("amountPaid", Decimal("0.00"))

    raise MobileMoneyPaymentError(
        "This checkout does not require a Mobile Money prompt.",
        code="mobile_money_not_requested",
    )


def _reload_sale_and_payment(*, sale_id, payment_id):
    # Returns complete records after transactional changes commit.
    sale = (
        Sale.objects.select_related(
            "business",
            "customer",
            "cashier",
        )
        .prefetch_related("items", "payments")
        .get(pk=sale_id)
    )
    payment = Payment.objects.select_related(
        "business",
        "sale",
        "customer",
        "initiated_by",
    ).get(pk=payment_id)
    return sale, payment


def _existing_mobile_money_attempt(*, business, idempotency_key):
    # Replays one prior checkout without sending another phone prompt.
    sale = (
        Sale.objects.filter(
            business=business,
            idempotency_key=idempotency_key,
        )
        .select_related(
            "business",
            "customer",
            "cashier",
        )
        .prefetch_related("items", "payments")
        .first()
    )

    if not sale:
        return None

    payment = sale.payments.filter(
        method=Payment.Method.MOBILE_MONEY,
    ).first()

    if not payment:
        raise MobileMoneyPaymentError(
            "The existing sale has no Mobile Money payment attempt.",
            code="mobile_money_payment_missing",
        )

    return sale, payment


@transaction.atomic
def _create_pending_mobile_money_records(
    *,
    business,
    user,
    data,
    idempotency_key,
):
    # Creates the audit records and reserves stock before calling Paystack.
    customer = _load_customer(
        business,
        data.get("customerId"),
    )
    products = _load_products(business, data["items"])
    lines, subtotal = _prepare_lines(products, data["items"])

    discount = data.get("discount", Decimal("0.00"))

    if discount > subtotal:
        raise MobileMoneyPaymentError(
            "Discount cannot be greater than the subtotal.",
            code="mobile_money_discount_invalid",
        )

    total = subtotal - discount

    if total <= Decimal("0.00"):
        raise MobileMoneyPaymentError(
            "A Mobile Money sale must have an amount above zero.",
            code="mobile_money_amount_invalid",
        )

    payment_amount = _mobile_money_amount(
        data=data,
        total=total,
    )

    if (
        payment_amount <= Decimal("0.00")
        or payment_amount > total
    ):
        raise MobileMoneyPaymentError(
            "The Mobile Money amount must be above zero "
            "and cannot exceed the sale total.",
            code="mobile_money_amount_invalid",
        )

    if (
        data["paymentMethod"] == Sale.PaymentMethod.CREDIT
        and not customer
    ):
        raise MobileMoneyPaymentError(
            "Select a customer before starting a part-payment sale.",
            code="mobile_money_customer_required",
        )

    # Uses trusted totals to decide whether verified debt will remain.
    expected_outstanding_balance = total - payment_amount
    debt_due_date = data.get("debtDueDate")

    if (
        expected_outstanding_balance > Decimal("0.00")
        and not debt_due_date
    ):
        raise MobileMoneyPaymentError(
            "Select the date when this debt is due.",
            code="mobile_money_debt_due_date_required",
        )

    if expected_outstanding_balance == Decimal("0.00"):
        debt_due_date = None

    sale_number, invoice_number, _ = _next_document_numbers(
        business,
        issue_receipt=False,
    )
    reservation_expires_at = timezone.now() + timedelta(
        minutes=settings.MOBILE_MONEY_RESERVATION_MINUTES
    )

    sale = Sale.objects.create(
        business=business,
        customer=customer,
        sale_number=sale_number,
        invoice_number=invoice_number,
        idempotency_key=idempotency_key,
        payment_method=data["paymentMethod"],
        status=Sale.Status.PENDING_PAYMENT,
        subtotal=subtotal,
        discount=discount,
        total=total,
        amount_paid=Decimal("0.00"),
        outstanding_balance=total,
        # Keeps the trusted due date but waits for debt verification.
        debt_due_date=debt_due_date,
        debt_principal_at_due=Decimal("0.00"),
        cashier=user,
        reservation_expires_at=reservation_expires_at,
    )

    for line in lines:
        product = line["product"]
        product.reserved_stock += line["quantity"]
        product.save(
            update_fields=("reserved_stock", "updated_at")
        )

        SaleItem.objects.create(
            sale=sale,
            product=product,
            quantity=line["quantity"],
            unit_price=line["unit_price"],
            cost_price=product.cost_price,
            line_total=line["line_total"],
        )

    payment = Payment.objects.create(
        business=business,
        sale=sale,
        customer=customer,
        payment_type=Payment.PaymentType.SALE_PAYMENT,
        method=Payment.Method.MOBILE_MONEY,
        status=Payment.Status.PENDING,
        amount=payment_amount,
        mobile_money_network=data["mobileMoneyNetwork"],
        mobile_money_number=data["mobileMoneyNumber"],
        gateway="paystack",
        gateway_reference=generate_sales_payment_reference(),
        idempotency_key=idempotency_key,
        note="Waiting for the Mobile Money prompt.",
        initiated_by=user,
    )

    return sale, payment


@transaction.atomic
def _release_failed_mobile_money_sale(
    *,
    payment_id,
    message,
):
    # Releases stock only while the sale is still genuinely pending.
    payment = (
        Payment.objects.select_for_update()
        .select_related("sale")
        .get(pk=payment_id)
    )
    sale = Sale.objects.select_for_update().get(pk=payment.sale_id)

    if sale.status != Sale.Status.PENDING_PAYMENT:
        return payment, sale

    items = list(
        SaleItem.objects.filter(sale=sale).values(
            "product_id",
            "quantity",
        )
    )
    product_ids = [item["product_id"] for item in items]
    products = {
        product.id: product
        for product in Product.objects.select_for_update().filter(
            id__in=product_ids
        )
    }

    for item in items:
        product = products[item["product_id"]]
        product.reserved_stock = max(
            0,
            product.reserved_stock - item["quantity"],
        )
        product.save(
            update_fields=("reserved_stock", "updated_at")
        )

    sale.status = Sale.Status.FAILED
    sale.reservation_expires_at = None
    sale.save(
        update_fields=(
            "status",
            "reservation_expires_at",
            "updated_at",
        )
    )

    payment.status = Payment.Status.FAILED
    payment.failure_reason = message
    payment.note = "The Mobile Money prompt was not started."
    payment.save(
        update_fields=(
            "status",
            "failure_reason",
            "note",
            "updated_at",
        )
    )

    return payment, sale


@transaction.atomic
def _record_uncertain_gateway_error(*, payment_id, message):
    # Keeps stock reserved when Paystack may have received the request.
    payment = Payment.objects.select_for_update().get(pk=payment_id)

    if payment.status == Payment.Status.PENDING:
        payment.failure_reason = message
        payment.note = (
            "Paystack could not confirm whether the prompt started. "
            "Verify this payment before retrying."
        )
        payment.save(
            update_fields=(
                "failure_reason",
                "note",
                "updated_at",
            )
        )

    return payment


def _gateway_error_is_definitive(exc):
    # Releases stock only when the request was certainly never accepted.
    if isinstance(exc, PaystackConfigurationError):
        return True

    return (
        isinstance(exc, PaystackRequestError)
        and exc.status_code is not None
        and 400 <= exc.status_code < 500
    )


def initialize_mobile_money_sale(
    *,
    business,
    user,
    data,
    idempotency_key,
    client=None,
):
    # Creates one pending sale and sends exactly one Paystack phone prompt.
    existing_attempt = _existing_mobile_money_attempt(
        business=business,
        idempotency_key=idempotency_key,
    )

    if existing_attempt:
        sale, payment = existing_attempt
        return sale, payment, True

    sale, payment = _create_pending_mobile_money_records(
        business=business,
        user=user,
        data=data,
        idempotency_key=idempotency_key,
    )
    gateway_client = client or PaystackClient()
    email = _payment_email(
        business=business,
        customer=sale.customer,
        user=user,
    )
    metadata = {
        "business_id": str(business.id),
        "sale_id": str(sale.id),
        "payment_id": str(payment.id),
        "payment_type": Payment.PaymentType.SALE_PAYMENT,
    }
    amount_subunit = int(payment.amount * 100)

    try:
        response = gateway_client.create_mobile_money_charge(
            email=email,
            amount_subunit=amount_subunit,
            reference=payment.gateway_reference,
            phone=payment.mobile_money_number,
            provider=payment.mobile_money_network,
            currency="GHS",
            metadata=metadata,
        )
    except PaystackError as exc:
        if _gateway_error_is_definitive(exc):
            _release_failed_mobile_money_sale(
                payment_id=payment.id,
                message=str(exc),
            )
        else:
            _record_uncertain_gateway_error(
                payment_id=payment.id,
                message=str(exc),
            )
        raise
    except ValueError as exc:
        _release_failed_mobile_money_sale(
            payment_id=payment.id,
            message=str(exc),
        )
        raise MobileMoneyPaymentError(
            str(exc),
            code="mobile_money_request_invalid",
        ) from exc

    provider_status = str(response.get("status", "")).strip().lower()

    if provider_status in {
        "failed",
        "abandoned",
        "cancelled",
        "reversed",
    }:
        message = (
            str(response.get("display_text", "")).strip()
            or "Paystack could not start the Mobile Money prompt."
        )
        _release_failed_mobile_money_sale(
            payment_id=payment.id,
            message=message,
        )
        raise MobileMoneyPaymentError(
            message,
            code="mobile_money_prompt_failed",
        )

    with transaction.atomic():
        locked_payment = Payment.objects.select_for_update().get(
            pk=payment.id
        )
        locked_payment.note = str(
            response.get("display_text", "")
        ).strip()
        locked_payment.failure_reason = ""
        locked_payment.save(
            update_fields=(
                "note",
                "failure_reason",
                "updated_at",
            )
        )

    sale, payment = _reload_sale_and_payment(
        sale_id=sale.id,
        payment_id=payment.id,
    )
    return sale, payment, False

def _get_mobile_money_sale_payment(reference):
    # Finds only Paystack Mobile Money payments attached to pending sales.
    try:
        return (
            Payment.objects.select_related(
                "business",
                "sale",
                "customer",
                "initiated_by",
            )
            .get(
                gateway="paystack",
                gateway_reference=reference,
                method=Payment.Method.MOBILE_MONEY,
                payment_type=Payment.PaymentType.SALE_PAYMENT,
                sale__isnull=False,
            )
        )
    except Payment.DoesNotExist as exc:
        raise MobileMoneyPaymentError(
            "The Mobile Money payment reference was not found.",
            code="mobile_money_payment_not_found",
        ) from exc


def _locked_sale_inventory(sale):
    # Locks the reserved sale lines and their products before changing stock.
    items = list(
        SaleItem.objects.select_for_update()
        .filter(sale=sale)
        .order_by("id")
    )
    product_ids = [item.product_id for item in items]
    products = {
        product.id: product
        for product in Product.objects.select_for_update().filter(
            id__in=product_ids
        )
    }

    if len(products) != len(set(product_ids)):
        raise MobileMoneyPaymentError(
            "One or more reserved products could not be found.",
            code="mobile_money_reserved_product_missing",
        )

    return items, products


def _release_verified_failure_locked(
    *,
    sale,
    payment,
    payment_status,
    reason,
):
    # Releases reserved stock after a definite failure or mismatch.
    items, products = _locked_sale_inventory(sale)

    for item in items:
        product = products[item.product_id]
        product.reserved_stock = max(
            0,
            product.reserved_stock - item.quantity,
        )
        product.save(
            update_fields=("reserved_stock", "updated_at")
        )

    sale.status = (
        Sale.Status.CANCELLED
        if payment_status == Payment.Status.CANCELLED
        else Sale.Status.FAILED
    )
    sale.reservation_expires_at = None
    sale.save(
        update_fields=(
            "status",
            "reservation_expires_at",
            "updated_at",
        )
    )

    payment.status = payment_status
    payment.failure_reason = reason
    payment.note = "The reserved stock was released."
    payment.save(
        update_fields=(
            "status",
            "failure_reason",
            "note",
            "updated_at",
        )
    )


def _payment_status_for_terminal_provider_status(provider_status):
    # Maps final Paystack states onto StockFlow payment states.
    if provider_status == "reversed":
        return Payment.Status.REVERSED

    if provider_status in {"abandoned", "cancelled"}:
        return Payment.Status.CANCELLED

    return Payment.Status.FAILED


def _successful_verification_error(payment, verification):
    # Validates every value needed before StockFlow delivers the sale.
    expected_values = {
        "reference": payment.gateway_reference,
        "amount": int(payment.amount * Decimal("100")),
        "currency": "GHS",
        "channel": "mobile_money",
    }
    received_values = {
        "reference": verification.get("reference"),
        "amount": verification.get("amount"),
        "currency": str(
            verification.get("currency", "")
        ).upper(),
        "channel": str(
            verification.get("channel", "")
        ).lower(),
    }
    mismatched_fields = [
        field
        for field, expected in expected_values.items()
        if received_values[field] != expected
    ]

    if mismatched_fields:
        return (
            MobileMoneyPaymentError(
                "The verified Mobile Money payment did not match "
                "the expected StockFlow sale.",
                code="mobile_money_payment_mismatch",
            ),
            True,
            (
                "Paystack verification did not match the expected "
                + ", ".join(mismatched_fields)
                + "."
            ),
        )

    provider_reference = str(
        verification.get("id", "")
    ).strip()

    if not provider_reference:
        return (
            MobileMoneyPaymentError(
                "The verified Mobile Money payment was incomplete.",
                code="mobile_money_verification_incomplete",
            ),
            False,
            "Paystack verification did not include a transaction ID.",
        )

    duplicate_transaction = (
        Payment.objects.exclude(pk=payment.pk)
        .filter(
            gateway=payment.gateway,
            provider_reference=provider_reference,
        )
        .exists()
    )

    if duplicate_transaction:
        return (
            MobileMoneyPaymentError(
                "This Mobile Money transaction has already been processed.",
                code="mobile_money_transaction_reused",
            ),
            True,
            (
                "The Paystack transaction was already used by another "
                "StockFlow payment."
            ),
        )

    return None, False, ""


def _finalize_mobile_money_sale_locked(
    *,
    sale,
    payment,
    verification,
):
    # Converts one verified reservation into stock, receipt and sale records.
    if payment.amount > sale.total:
        raise MobileMoneyPaymentError(
            "The Mobile Money payment exceeds the sale total.",
            code="mobile_money_amount_invalid",
        )

    if (
        sale.payment_method == Sale.PaymentMethod.MOBILE_MONEY
        and payment.amount != sale.total
    ):
        raise MobileMoneyPaymentError(
            "The full Mobile Money payment does not match the sale total.",
            code="mobile_money_amount_invalid",
        )

    outstanding_balance = sale.total - payment.amount

    if outstanding_balance > Decimal("0.00") and not sale.customer_id:
        raise MobileMoneyPaymentError(
            "A customer is required for a part-payment sale.",
            code="mobile_money_customer_required",
        )

    items, products = _locked_sale_inventory(sale)

    for item in items:
        product = products[item.product_id]

        if (
            product.stock < item.quantity
            or product.reserved_stock < item.quantity
        ):
            raise MobileMoneyPaymentError(
                "The reserved stock is no longer available for this sale.",
                code="mobile_money_reservation_invalid",
            )

    receipt_number = _next_receipt_number(sale.business)
    now = timezone.now()

    for item in items:
        product = products[item.product_id]
        previous_stock = product.stock
        new_stock = previous_stock - item.quantity

        product.stock = new_stock
        product.reserved_stock -= item.quantity
        product.save(
            update_fields=(
                "stock",
                "reserved_stock",
                "updated_at",
            )
        )

        StockMovement.objects.create(
            business=sale.business,
            product=product,
            movement_type=StockMovement.MovementType.SALE,
            quantity=-item.quantity,
            previous_stock=previous_stock,
            new_stock=new_stock,
            reason=f"Sale {sale.sale_number}",
            created_by=sale.cashier,
        )

    if sale.customer_id:
        customer = (
            Customer.objects.select_for_update()
            .get(pk=sale.customer_id)
        )
        customer.total_purchases += sale.total
        customer.outstanding_balance += outstanding_balance
        customer.save(
            update_fields=(
                "total_purchases",
                "outstanding_balance",
                "updated_at",
            )
        )

    sale.amount_paid = payment.amount
    sale.outstanding_balance = outstanding_balance

    # Activates the frozen debt principal only after verified success.
    sale.debt_principal_at_due = (
        outstanding_balance
        if outstanding_balance > Decimal("0.00")
        else Decimal("0.00")
    )

    if outstanding_balance == Decimal("0.00"):
        sale.debt_due_date = None

    sale.status = (
        Sale.Status.COMPLETED
        if outstanding_balance == Decimal("0.00")
        else Sale.Status.PARTIALLY_PAID
    )
    sale.reservation_expires_at = None
    sale.completed_at = now
    sale.save(
        update_fields=(
            "amount_paid",
            "outstanding_balance",
            "debt_due_date",
            "debt_principal_at_due",
            "status",
            "reservation_expires_at",
            "completed_at",
            "updated_at",
        )
    )

    payment.status = Payment.Status.SUCCESSFUL
    payment.provider_reference = str(verification["id"])
    payment.receipt_number = receipt_number
    payment.failure_reason = ""
    payment.note = "Mobile Money payment verified by Paystack."
    payment.verified_at = now
    payment.save(
        update_fields=(
            "status",
            "provider_reference",
            "receipt_number",
            "failure_reason",
            "note",
            "verified_at",
            "updated_at",
        )
    )

    # Queue the merchant payout in the same database transaction.
    # The actual Paystack transfer happens asynchronously via the payout worker.
    from .merchant_payout_service import queue_merchant_payout_for_payment_locked

    queue_merchant_payout_for_payment_locked(payment)


def verify_and_finalize_mobile_money_sale(
    *,
    reference,
    client=None,
):
    # Verifies Paystack server-to-server and delivers the sale exactly once.
    existing_payment = _get_mobile_money_sale_payment(reference)
    existing_sale = existing_payment.sale

    if (
        existing_payment.status == Payment.Status.SUCCESSFUL
        and existing_sale.status
        in {
            Sale.Status.COMPLETED,
            Sale.Status.PARTIALLY_PAID,
        }
    ):
        return existing_payment, existing_sale, False

    gateway_client = client or PaystackClient()
    verification = gateway_client.verify_transaction(reference)
    deferred_error = None

    with transaction.atomic():
        payment = (
            Payment.objects.select_for_update()
            .select_related(
                "business",
                "sale",
                "customer",
                "initiated_by",
            )
            .get(pk=existing_payment.pk)
        )
        sale = (
            Sale.objects.select_for_update()
            .select_related(
                "business",
                "customer",
                "cashier",
            )
            .get(pk=payment.sale_id)
        )

        if (
            payment.status == Payment.Status.SUCCESSFUL
            and sale.status
            in {
                Sale.Status.COMPLETED,
                Sale.Status.PARTIALLY_PAID,
            }
        ):
            return payment, sale, False

        if sale.status != Sale.Status.PENDING_PAYMENT:
            raise MobileMoneyPaymentError(
                "This Mobile Money sale is no longer pending.",
                code="mobile_money_sale_not_pending",
            )

        provider_status = str(
            verification.get("status", "")
        ).strip().lower()

        if provider_status != "success":
            if provider_status in {
                "failed",
                "abandoned",
                "cancelled",
                "reversed",
            }:
                reason = (
                    "Paystack verification returned the final status "
                    f"{provider_status}."
                )
                _release_verified_failure_locked(
                    sale=sale,
                    payment=payment,
                    payment_status=(
                        _payment_status_for_terminal_provider_status(
                            provider_status
                        )
                    ),
                    reason=reason,
                )
                deferred_error = MobileMoneyPaymentError(
                    "The Mobile Money payment was not successful.",
                    code="mobile_money_payment_failed",
                )
            else:
                payment.failure_reason = ""
                payment.note = (
                    "Waiting for Paystack confirmation. "
                    f"Current status: {provider_status or 'unknown'}."
                )
                payment.save(
                    update_fields=(
                        "failure_reason",
                        "note",
                        "updated_at",
                    )
                )
                deferred_error = MobileMoneyPaymentError(
                    "The Mobile Money payment is still pending.",
                    code="mobile_money_payment_pending",
                )
        else:
            (
                verification_error,
                should_release,
                failure_reason,
            ) = _successful_verification_error(
                payment,
                verification,
            )

            if verification_error is not None:
                if should_release:
                    _release_verified_failure_locked(
                        sale=sale,
                        payment=payment,
                        payment_status=Payment.Status.FAILED,
                        reason=failure_reason,
                    )
                else:
                    payment.failure_reason = failure_reason
                    payment.note = (
                        "The payment needs another server verification."
                    )
                    payment.save(
                        update_fields=(
                            "failure_reason",
                            "note",
                            "updated_at",
                        )
                    )

                deferred_error = verification_error
            else:
                _finalize_mobile_money_sale_locked(
                    sale=sale,
                    payment=payment,
                    verification=verification,
                )

    if deferred_error is not None:
        raise deferred_error

    sale, payment = _reload_sale_and_payment(
        sale_id=existing_sale.id,
        payment_id=existing_payment.id,
    )
    return payment, sale, True


def generate_debt_payment_reference():
    # Creates a unique Paystack-safe reference for a debt payment.
    timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
    suffix = uuid.uuid4().hex[:12].upper()
    return f"STF-DEBT-{timestamp}-{suffix}"


def _reload_debt_payment(payment_id):
    # Reloads the complete payment after a transaction commits.
    return Payment.objects.select_related(
        "business", "sale", "customer", "initiated_by"
    ).get(pk=payment_id)


def _existing_mobile_money_debt_attempt(*, business, idempotency_key):
    # Replays one prior debt attempt without sending another phone prompt.
    return Payment.objects.select_related(
        "business", "sale", "customer", "initiated_by"
    ).filter(
        business=business,
        idempotency_key=idempotency_key,
        payment_type=Payment.PaymentType.DEBT_PAYMENT,
        method=Payment.Method.MOBILE_MONEY,
    ).first()


@transaction.atomic
def _create_pending_mobile_money_debt_payment(
    *, business, customer_id, user, data, idempotency_key
):
    # Validates the unpaid invoice before creating a pending payment.
    customer = Customer.objects.select_for_update().filter(
        pk=customer_id,
        business=business,
        is_active=True,
    ).first()
    if not customer:
        raise MobileMoneyPaymentError(
            "The customer was not found.",
            code="mobile_money_customer_not_found",
        )

    amount = data["amount"]

    unpaid_sales = Sale.objects.select_for_update().filter(
        business=business,
        customer=customer,
        outstanding_balance__gt=Decimal("0.00"),
    ).order_by("created_at")
    if data.get("saleId"):
        unpaid_sales = unpaid_sales.filter(pk=data["saleId"])
    sale = unpaid_sales.first()
    if not sale:
        raise MobileMoneyPaymentError(
            "No unpaid invoice was found for this customer.",
            code="mobile_money_invoice_not_found",
        )
    split = debt_payment_split(
        sale=sale,
        amount=amount,
    )

    if amount > split["total_due"]:
        raise MobileMoneyPaymentError(
            "Payment cannot exceed the selected invoice total due.",
            code="mobile_money_debt_amount_invalid",
        )

    return Payment.objects.create(
        business=business,
        sale=sale,
        customer=customer,
        payment_type=Payment.PaymentType.DEBT_PAYMENT,
        method=Payment.Method.MOBILE_MONEY,
        status=Payment.Status.PENDING,
        amount=amount,
        mobile_money_network=data["mobileMoneyNetwork"],
        mobile_money_number=data["mobileMoneyNumber"],
        gateway="paystack",
        gateway_reference=generate_debt_payment_reference(),
        idempotency_key=idempotency_key,
        reference=data.get("reference", ""),
        note=data.get("note", "") or "Waiting for the Mobile Money prompt.",
        initiated_by=user,
    )


@transaction.atomic
def _mark_mobile_money_debt_failure(
    *, payment_id, message, payment_status=Payment.Status.FAILED,
    note="The Mobile Money prompt was not started."
):
    # Records a definite failure without changing invoice balances.
    payment = Payment.objects.select_for_update().get(pk=payment_id)
    if payment.status == Payment.Status.PENDING:
        payment.status = payment_status
        payment.failure_reason = message
        payment.note = note
        payment.save(update_fields=(
            "status", "failure_reason", "note", "updated_at"
        ))
    return payment


@transaction.atomic
def _record_uncertain_debt_gateway_error(*, payment_id, message):
    # Keeps a possibly accepted charge pending for later verification.
    payment = Payment.objects.select_for_update().get(pk=payment_id)
    if payment.status == Payment.Status.PENDING:
        payment.failure_reason = message
        payment.note = (
            "Paystack could not confirm whether the prompt started. "
            "Verify this payment before retrying."
        )
        payment.save(update_fields=("failure_reason", "note", "updated_at"))
    return payment


def initialize_mobile_money_debt_payment(
    *, business, customer_id, user, data, idempotency_key, client=None
):
    # Creates one pending debt payment and sends exactly one phone prompt.
    existing = _existing_mobile_money_debt_attempt(
        business=business,
        idempotency_key=idempotency_key,
    )
    if existing:
        return existing, True

    payment = _create_pending_mobile_money_debt_payment(
        business=business,
        customer_id=customer_id,
        user=user,
        data=data,
        idempotency_key=idempotency_key,
    )
    gateway_client = client or PaystackClient()
    metadata = {
        "business_id": str(business.id),
        "sale_id": str(payment.sale_id),
        "customer_id": str(payment.customer_id),
        "payment_id": str(payment.id),
        "payment_type": Payment.PaymentType.DEBT_PAYMENT,
    }
    try:
        response = gateway_client.create_mobile_money_charge(
            email=_payment_email(
                business=business,
                customer=payment.customer,
                user=user,
            ),
            amount_subunit=int(payment.amount * Decimal("100")),
            reference=payment.gateway_reference,
            phone=payment.mobile_money_number,
            provider=payment.mobile_money_network,
            currency="GHS",
            metadata=metadata,
        )
    except PaystackError as exc:
        if _gateway_error_is_definitive(exc):
            _mark_mobile_money_debt_failure(
                payment_id=payment.id,
                message=str(exc),
            )
        else:
            _record_uncertain_debt_gateway_error(
                payment_id=payment.id,
                message=str(exc),
            )
        raise
    except ValueError as exc:
        _mark_mobile_money_debt_failure(
            payment_id=payment.id,
            message=str(exc),
        )
        raise MobileMoneyPaymentError(
            str(exc),
            code="mobile_money_request_invalid",
        ) from exc

    provider_status = str(response.get("status", "")).strip().lower()
    if provider_status in {"failed", "abandoned", "cancelled", "reversed"}:
        message = (
            str(response.get("display_text", "")).strip()
            or "Paystack could not start the Mobile Money prompt."
        )
        _mark_mobile_money_debt_failure(
            payment_id=payment.id,
            message=message,
            payment_status=_payment_status_for_terminal_provider_status(
                provider_status
            ),
        )
        raise MobileMoneyPaymentError(
            message,
            code="mobile_money_prompt_failed",
        )

    with transaction.atomic():
        locked = Payment.objects.select_for_update().get(pk=payment.id)
        locked.note = str(response.get("display_text", "")).strip()
        locked.failure_reason = ""
        locked.save(update_fields=("note", "failure_reason", "updated_at"))

    return _reload_debt_payment(payment.id), False


def _get_mobile_money_debt_payment(reference):
    # Finds only Paystack Mobile Money customer debt payments.
    try:
        return Payment.objects.select_related(
            "business", "sale", "customer", "initiated_by"
        ).get(
            gateway="paystack",
            gateway_reference=reference,
            method=Payment.Method.MOBILE_MONEY,
            payment_type=Payment.PaymentType.DEBT_PAYMENT,
            sale__isnull=False,
            customer__isnull=False,
        )
    except Payment.DoesNotExist as exc:
        raise MobileMoneyPaymentError(
            "The Mobile Money debt-payment reference was not found.",
            code="mobile_money_debt_payment_not_found",
        ) from exc


def _mark_verified_debt_failure_locked(*, payment, payment_status, reason):
    # Finalizes a verified failure without changing debt balances.
    payment.status = payment_status
    payment.failure_reason = reason
    payment.note = "No customer or invoice balance was changed."
    payment.save(update_fields=(
        "status", "failure_reason", "note", "updated_at"
    ))


def _debt_balance_verification_error(*, payment, sale, customer):
    # Rejects a charge when the linked invoice changed after initialization.
    if (
        sale.business_id != payment.business_id
        or customer.business_id != payment.business_id
        or sale.customer_id != customer.id
        or payment.customer_id != customer.id
    ):
        return MobileMoneyPaymentError(
            "The Mobile Money debt payment no longer matches its invoice.",
            code="mobile_money_payment_mismatch",
        )
    split = debt_payment_split(
        sale=sale,
        amount=payment.amount,
    )

    if (
        sale.outstanding_balance <= Decimal("0.00")
        or customer.outstanding_balance <= Decimal("0.00")
        or payment.amount > split["total_due"]
        or split["principal_paid"] > customer.outstanding_balance
    ):
        return MobileMoneyPaymentError(
            "The invoice balance changed before this payment was verified.",
            code="mobile_money_debt_balance_changed",
        )
    return None


def _finalize_mobile_money_debt_locked(*, payment, sale, customer, verification):
    # Applies one verified debt payment and creates one receipt.
    receipt_number = _next_receipt_number(payment.business)
    now = timezone.now()

    payment.status = Payment.Status.SUCCESSFUL
    payment.provider_reference = str(verification["id"])
    payment.receipt_number = receipt_number
    payment.failure_reason = ""
    payment.note = "Mobile Money debt payment verified by Paystack."
    payment.verified_at = now
    payment.save(update_fields=(
        "status", "provider_reference", "receipt_number", "failure_reason",
        "note", "verified_at", "updated_at"
    ))

    # Queue a matching merchant payout for this verified debt payment.
    from .merchant_payout_service import queue_merchant_payout_for_payment_locked

    queue_merchant_payout_for_payment_locked(payment)

    _apply_debt_payment_allocation_locked(
        payment=payment,
        sale=sale,
        customer=customer,
    )


def verify_and_finalize_mobile_money_debt_payment(*, reference, client=None):
    # Verifies Paystack and applies one debt payment exactly once.
    existing = _get_mobile_money_debt_payment(reference)
    if existing.status == Payment.Status.SUCCESSFUL:
        return existing, existing.sale, existing.customer, False

    verification = (client or PaystackClient()).verify_transaction(reference)
    deferred_error = None
    with transaction.atomic():
        payment = Payment.objects.select_for_update().select_related(
            "business", "sale", "customer", "initiated_by"
        ).get(pk=existing.pk)
        sale = Sale.objects.select_for_update().get(pk=payment.sale_id)
        customer = Customer.objects.select_for_update().get(pk=payment.customer_id)

        if payment.status == Payment.Status.SUCCESSFUL:
            return payment, sale, customer, False
        if payment.status != Payment.Status.PENDING:
            raise MobileMoneyPaymentError(
                "This Mobile Money debt payment is no longer pending.",
                code="mobile_money_debt_not_pending",
            )

        provider_status = str(verification.get("status", "")).strip().lower()
        if provider_status != "success":
            if provider_status in {"failed", "abandoned", "cancelled", "reversed"}:
                _mark_verified_debt_failure_locked(
                    payment=payment,
                    payment_status=_payment_status_for_terminal_provider_status(
                        provider_status
                    ),
                    reason=(
                        "Paystack verification returned the final status "
                        f"{provider_status}."
                    ),
                )
                deferred_error = MobileMoneyPaymentError(
                    "The Mobile Money payment was not successful.",
                    code="mobile_money_payment_failed",
                )
            else:
                payment.failure_reason = ""
                payment.note = (
                    "Waiting for Paystack confirmation. "
                    f"Current status: {provider_status or 'unknown'}."
                )
                payment.save(update_fields=(
                    "failure_reason", "note", "updated_at"
                ))
                deferred_error = MobileMoneyPaymentError(
                    "The Mobile Money payment is still pending.",
                    code="mobile_money_payment_pending",
                )
        else:
            verification_error, should_fail, reason = (
                _successful_verification_error(payment, verification)
            )
            if verification_error is not None:
                if should_fail:
                    _mark_verified_debt_failure_locked(
                        payment=payment,
                        payment_status=Payment.Status.FAILED,
                        reason=reason,
                    )
                else:
                    payment.failure_reason = reason
                    payment.note = "The payment needs another server verification."
                    payment.save(update_fields=(
                        "failure_reason", "note", "updated_at"
                    ))
                deferred_error = verification_error
            else:
                balance_error = _debt_balance_verification_error(
                    payment=payment,
                    sale=sale,
                    customer=customer,
                )
                if balance_error:
                    _mark_verified_debt_failure_locked(
                        payment=payment,
                        payment_status=Payment.Status.FAILED,
                        reason=str(balance_error),
                    )
                    deferred_error = balance_error
                else:
                    _finalize_mobile_money_debt_locked(
                        payment=payment,
                        sale=sale,
                        customer=customer,
                        verification=verification,
                    )

    if deferred_error:
        raise deferred_error
    payment = _reload_debt_payment(existing.id)
    return payment, payment.sale, payment.customer, True


@transaction.atomic
def _expire_stale_mobile_money_sale(
    *,
    payment_id,
    checked_at,
):
    # Releases one expired reservation only while it is still pending.
    payment = (
        Payment.objects.select_for_update()
        .select_related("sale")
        .get(pk=payment_id)
    )
    sale = Sale.objects.select_for_update().get(pk=payment.sale_id)

    if (
        payment.status != Payment.Status.PENDING
        or sale.status != Sale.Status.PENDING_PAYMENT
        or sale.reservation_expires_at is None
        or sale.reservation_expires_at > checked_at
    ):
        return payment, sale, False

    items = list(
        SaleItem.objects.select_for_update()
        .filter(sale=sale)
        .values("product_id", "quantity")
    )
    product_ids = [item["product_id"] for item in items]
    products = {
        product.id: product
        for product in Product.objects.select_for_update().filter(
            id__in=product_ids
        )
    }

    if len(products) != len(set(product_ids)):
        raise MobileMoneyPaymentError(
            "One or more reserved products could not be found.",
            code="mobile_money_reserved_product_missing",
        )

    for item in items:
        product = products[item["product_id"]]
        product.reserved_stock = max(
            0,
            product.reserved_stock - item["quantity"],
        )
        product.save(
            update_fields=("reserved_stock", "updated_at")
        )

    sale.status = Sale.Status.FAILED
    sale.reservation_expires_at = None
    sale.save(
        update_fields=(
            "status",
            "reservation_expires_at",
            "updated_at",
        )
    )

    payment.status = Payment.Status.FAILED
    payment.failure_reason = (
        "The Mobile Money reservation expired before Paystack "
        "confirmed a successful payment."
    )
    payment.note = (
        "The expired stock reservation was released after "
        "server-side Paystack verification."
    )
    payment.save(
        update_fields=(
            "status",
            "failure_reason",
            "note",
            "updated_at",
        )
    )

    return payment, sale, True


def _expired_mobile_money_payment_ids(*, checked_at, batch_size):
    # Selects only expired pending sale payments in deterministic order.
    return list(
        Payment.objects.filter(
            gateway="paystack",
            method=Payment.Method.MOBILE_MONEY,
            payment_type=Payment.PaymentType.SALE_PAYMENT,
            status=Payment.Status.PENDING,
            sale__status=Sale.Status.PENDING_PAYMENT,
            sale__reservation_expires_at__isnull=False,
            sale__reservation_expires_at__lte=checked_at,
        )
        .order_by("sale__reservation_expires_at", "created_at", "id")
        .values_list("id", flat=True)[:batch_size]
    )


def cleanup_expired_mobile_money_reservations(
    *,
    checked_at=None,
    batch_size=100,
    client=None,
):
    # Reconciles expired reservations with Paystack before releasing stock.
    if batch_size < 1:
        raise ValueError("batch_size must be greater than zero.")

    checked_at = checked_at or timezone.now()
    payment_ids = _expired_mobile_money_payment_ids(
        checked_at=checked_at,
        batch_size=batch_size,
    )
    summary = {
        "scanned": len(payment_ids),
        "finalized": 0,
        "released": 0,
        "deferred": 0,
        "skipped": 0,
    }

    for payment_id in payment_ids:
        payment = (
            Payment.objects.select_related("sale")
            .filter(pk=payment_id)
            .first()
        )

        if not payment:
            summary["skipped"] += 1
            continue

        try:
            _, _, finalized = verify_and_finalize_mobile_money_sale(
                reference=payment.gateway_reference,
                client=client,
            )
        except (
            PaystackConfigurationError,
            PaystackRequestError,
        ):
            # A gateway outage must never release stock without verification.
            summary["deferred"] += 1
            continue
        except MobileMoneyPaymentError as exc:
            payment.refresh_from_db()
            payment.sale.refresh_from_db()

            # Terminal verification failures already release the reservation.
            if (
                payment.status != Payment.Status.PENDING
                and payment.sale.reservation_expires_at is None
            ):
                summary["released"] += 1
                continue

            if exc.code != "mobile_money_payment_pending":
                # Incomplete or inconsistent verification requires review.
                summary["deferred"] += 1
                continue

            try:
                _, _, released = _expire_stale_mobile_money_sale(
                    payment_id=payment.id,
                    checked_at=checked_at,
                )
            except MobileMoneyPaymentError:
                summary["deferred"] += 1
                continue

            if released:
                summary["released"] += 1
            else:
                summary["skipped"] += 1
            continue

        if finalized:
            summary["finalized"] += 1
        else:
            summary["skipped"] += 1

    return summary
