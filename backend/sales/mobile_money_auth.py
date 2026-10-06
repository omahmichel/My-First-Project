"""Advance an existing sale charge without creating another payment."""
import re
import logging
from datetime import timedelta
from functools import wraps
from django.db import transaction
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables
from businesses.payment_modes import require_mode, require_response_mode
from businesses.paystack_client import PaystackClient, PaystackRequestError
from .models import Payment, Sale
from .mobile_money_service import (
    MobileMoneyPaymentError, _get_mobile_money_sale_payment,
    verify_and_finalize_mobile_money_sale,
)

logger = logging.getLogger(__name__)
# The platform-event handler on "sales" consumes warnings without printing them.
# Give these allowlisted diagnostic messages their own console destination.
if not any(getattr(h, "name", None) == "stockflow_payment_auth_console" for h in logger.handlers):
    console = logging.StreamHandler()
    console.set_name("stockflow_payment_auth_console")
    console.setLevel(logging.WARNING)
    console.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console)
logger.setLevel(logging.WARNING)
logger.propagate = False
SAFE_STATUSES = {"send_otp", "pay_offline", "pending", "success", "failed", "abandoned", "cancelled", "reversed", "timeout", "open_url"}


def _trace_status(stage, data):
    value = data.get("status") if isinstance(data, dict) else None
    safe = value if isinstance(value, str) and value in SAFE_STATUSES else "other_or_missing"
    logger.warning("StockFlow payment auth: stage=%s provider_status=%s", stage, safe)


def _trace_request(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        logger.warning("StockFlow payment auth: stage=request otp_supplied=%s", kwargs.get("otp") is not None)
        try:
            sale = func(*args, **kwargs)
            logger.warning("StockFlow payment auth: stage=return sale_status=%s", sale.status)
            return sale
        except Exception as exc:
            # Do not log exception text, request body, provider payload, or credentials.
            logger.warning("StockFlow payment auth: stage=error error_type=%s", type(exc).__name__)
            raise
    return wrapped


TERMINAL = {"failed", "abandoned", "cancelled", "reversed"}


@_trace_request
@sensitive_variables("otp", "data")
def advance_sale_charge(*, reference, otp=None, client=None):
    payment = _get_mobile_money_sale_payment(reference)
    if (payment.status != Payment.Status.PENDING or payment.sale.status != Sale.Status.PENDING_PAYMENT) and not payment.checkout_url:
        logger.warning("StockFlow payment auth: stage=already_terminal")
        return Sale.objects.get(pk=payment.sale_id)
    if payment.checkout_url:
        if otp is not None:
            raise MobileMoneyPaymentError("The customer must authenticate privately in Paystack checkout.", code="customer_checkout_required")
        try:
            _, sale, _ = verify_and_finalize_mobile_money_sale(reference=reference, client=client)
            return sale
        except MobileMoneyPaymentError as exc:
            if exc.code not in {"mobile_money_payment_pending", "mobile_money_payment_failed", "mobile_money_sale_not_pending"}:
                raise
            return Sale.objects.get(pk=payment.sale_id)
    gateway = client or PaystackClient()
    mode = require_mode(payment.gateway_mode, gateway)
    if otp is not None and (not isinstance(otp, str) or not re.fullmatch(r"[0-9]{4,10}", otp)):
        raise MobileMoneyPaymentError("Enter the payment code using 4 to 10 digits.", code="payment_code_invalid")
    # Do not poll or submit again while another request is sending the code.
    # The lease also permits recovery after a worker terminates unexpectedly.
    if payment.gateway_charge_status == "otp_submitting" and payment.updated_at > timezone.now() - timedelta(seconds=60):
        logger.warning("StockFlow payment auth: stage=submission_in_progress")
        return Sale.objects.get(pk=payment.sale_id)
    direct_otp = otp is not None and payment.gateway_charge_status == "send_otp"
    if direct_otp:
        if payment.sale.reservation_expires_at and payment.sale.reservation_expires_at <= timezone.now():
            logger.warning("StockFlow payment auth: stage=reservation_expired")
            raise MobileMoneyPaymentError("The stock reservation expired. Check payment status before starting another sale.", code="payment_auth_expired")
        # Claim the stored provider action atomically; no network call holds a DB lock.
        claimed_at = timezone.now()
        claimed = Payment.objects.filter(
            pk=payment.pk, status=Payment.Status.PENDING,
            gateway_charge_status="send_otp", updated_at=payment.updated_at,
            sale__status=Sale.Status.PENDING_PAYMENT,
        ).update(gateway_charge_status="otp_submitting", updated_at=claimed_at)
        if not claimed:
            logger.warning("StockFlow payment auth: stage=submission_already_claimed")
            return Sale.objects.get(pk=payment.sale_id)
        payment.gateway_charge_status = "otp_submitting"
        payment.updated_at = claimed_at
        try:
            logger.warning("StockFlow payment auth: stage=submitting_otp")
            data = gateway.submit_charge_otp(reference=reference, otp=otp)
            _trace_status("after_otp", data)
            _validate_response(data, reference, mode)
        except Exception:
            # An uncertain response must be checked before another code submission.
            Payment.objects.filter(
                pk=payment.pk, status=Payment.Status.PENDING,
                gateway_charge_status="otp_submitting", updated_at=claimed_at,
            ).update(gateway_charge_status="otp_unknown", updated_at=timezone.now())
            raise
    else:
        # Status checks and recovery never replay a supplied code automatically.
        data = gateway.check_pending_charge(reference)
        _trace_status("status_check", data)
        _validate_response(data, reference, mode)
    charge_status = str(data.get("status", "")).lower()
    if charge_status == "success" or charge_status in TERMINAL:
        try:
            _, sale, _ = verify_and_finalize_mobile_money_sale(reference=reference, client=gateway)
            return sale
        except MobileMoneyPaymentError as exc:
            if exc.code not in {"mobile_money_payment_failed", "mobile_money_sale_not_pending", "mobile_money_payment_pending"}:
                raise
            return Sale.objects.get(pk=payment.sale_id)
    # Charge responses are actions, never proof of payment.
    instructions = {
        "send_otp": 'Paystack requested an OTP instead of a direct phone approval. Do not ask the customer for their code or PIN. This payment needs additional customer authentication that the merchant screen cannot complete. Check its final status before attempting another payment.',
        "pay_offline": "Complete the payment approval on the paying phone, then check payment status.",
        "pending": "Paystack is processing this payment. Wait at least 10 seconds before checking again.",
    }
    message = instructions.get(charge_status, "Paystack requires an authentication step this checkout cannot complete. Do not create another charge until this payment status is confirmed.")
    # Keep trusted provider guidance (plain text) for offline/OTP instructions.
    if charge_status in {"pay_offline", "pending"}:
        message = str(data.get("display_text") or message)[:500]
    with transaction.atomic():
        locked = Payment.objects.select_for_update().get(pk=payment.pk)
        if (locked.status == Payment.Status.PENDING
                and locked.gateway_charge_status == payment.gateway_charge_status
                and locked.updated_at == payment.updated_at):
            locked.gateway_charge_status = charge_status[:32]
            locked.note = message
            locked.save(update_fields=("gateway_charge_status", "note", "updated_at"))
    return Sale.objects.get(pk=payment.sale_id)


def _validate_response(data, reference, mode):
    if not isinstance(data, dict) or not data.get("status"):
        raise PaystackRequestError("Paystack returned an incomplete charge response.", code="paystack_invalid_response")
    if data.get("reference") and data["reference"] != reference:
        raise PaystackRequestError("Paystack returned a different payment reference.", code="paystack_reference_mismatch")
    # Intermediate Charge responses may omit domain; the API client/key is mode-checked.
    if data.get("domain"):
        require_response_mode(data, mode)
