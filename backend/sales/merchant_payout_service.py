from decimal import Decimal
import uuid

from django.db import transaction
from django.utils import timezone

from businesses.models import BusinessPaymentAccount
from businesses.paystack_client import PaystackClient, PaystackError, PaystackRequestError
from businesses.payout_recipient_service import sync_mobile_money_payout_recipient

from .models import MerchantPayout, Payment


def generate_merchant_payout_reference():
    # Paystack recommends caller-generated unique references for safe retries.
    return f"stf_payout_{uuid.uuid4().hex}"


def _eligible_account_for_business(business):
    return (
        business.payment_accounts.filter(
            account_type=BusinessPaymentAccount.AccountType.MOBILE_MONEY,
            is_active=True,
        )
        .order_by("-is_default", "created_at")
        .first()
    )


def _set_account_snapshot(payout, account):
    payout.receiving_account = account
    payout.recipient_code_snapshot = account.paystack_recipient_code
    payout.receiving_account_name_snapshot = account.account_name
    payout.receiving_account_network_snapshot = account.network
    payout.receiving_account_masked_number_snapshot = account.masked_number


def queue_merchant_payout_for_payment_locked(payment):
    # Only verified Paystack Mobile Money payments produce merchant payouts.
    if (
        payment.gateway != "paystack"
        or payment.method != Payment.Method.MOBILE_MONEY
        or payment.status != Payment.Status.SUCCESSFUL
    ):
        return None

    existing = MerchantPayout.objects.filter(payment=payment).first()
    if existing:
        return existing

    account = _eligible_account_for_business(payment.business)
    payout = MerchantPayout(
        business=payment.business,
        payment=payment,
        amount=payment.amount,
        currency="GHS",
        reference=generate_merchant_payout_reference(),
        status=(
            MerchantPayout.Status.PENDING
            if account
            else MerchantPayout.Status.BLOCKED
        ),
        failure_reason=(
            ""
            if account
            else "No active Mobile Money receiving account is configured for this business."
        ),
    )
    if account:
        _set_account_snapshot(payout, account)
    payout.save()
    return payout


def _amount_subunit(amount):
    return int((Decimal(amount) * Decimal("100")).quantize(Decimal("1")))


def _apply_provider_state(payout_id, data, *, fallback_status="processing"):
    provider_status = str(data.get("status", fallback_status)).strip().lower()
    transfer_code = str(data.get("transfer_code", "")).strip()
    now = timezone.now()

    with transaction.atomic():
        payout = MerchantPayout.objects.select_for_update().get(pk=payout_id)
        payout.provider_status = provider_status
        if transfer_code:
            payout.transfer_code = transfer_code
        payout.failure_reason = ""

        if provider_status == "success":
            payout.status = MerchantPayout.Status.SUCCESSFUL
            payout.completed_at = now
        elif provider_status == "failed":
            payout.status = MerchantPayout.Status.FAILED
        elif provider_status == "reversed":
            payout.status = MerchantPayout.Status.REVERSED
            payout.completed_at = now
        else:
            payout.status = MerchantPayout.Status.PROCESSING

        payout.save(
            update_fields=(
                "provider_status",
                "transfer_code",
                "failure_reason",
                "status",
                "completed_at",
                "updated_at",
            )
        )
        return payout


def _mark_retry(payout_id, message):
    with transaction.atomic():
        payout = MerchantPayout.objects.select_for_update().get(pk=payout_id)
        payout.status = MerchantPayout.Status.RETRY
        payout.failure_reason = str(message or "")[:1000]
        payout.last_attempted_at = timezone.now()
        payout.attempt_count += 1
        payout.save(
            update_fields=(
                "status",
                "failure_reason",
                "last_attempted_at",
                "attempt_count",
                "updated_at",
            )
        )
        return payout


def _mark_blocked(payout_id, message):
    with transaction.atomic():
        payout = MerchantPayout.objects.select_for_update().get(pk=payout_id)
        payout.status = MerchantPayout.Status.BLOCKED
        payout.failure_reason = str(message or "")[:1000]
        payout.last_attempted_at = timezone.now()
        payout.save(
            update_fields=(
                "status",
                "failure_reason",
                "last_attempted_at",
                "updated_at",
            )
        )
        return payout


def process_merchant_payout(payout_id, client=None):
    payout = MerchantPayout.objects.select_related(
        "business", "payment", "receiving_account"
    ).get(pk=payout_id)

    if payout.status in {
        MerchantPayout.Status.SUCCESSFUL,
        MerchantPayout.Status.REVERSED,
    }:
        return payout

    account = payout.receiving_account
    if (
        account is None
        or not account.is_active
        or account.account_type != BusinessPaymentAccount.AccountType.MOBILE_MONEY
    ):
        account = _eligible_account_for_business(payout.business)

    if account is None:
        return _mark_blocked(
            payout.id,
            "No active Mobile Money receiving account is configured for this business.",
        )

    if not account.payout_ready:
        try:
            account = sync_mobile_money_payout_recipient(account, client=client)
        except PaystackError as exc:
            return _mark_retry(payout.id, str(exc))

    with transaction.atomic():
        locked = MerchantPayout.objects.select_for_update().get(pk=payout.id)
        _set_account_snapshot(locked, account)
        locked.status = MerchantPayout.Status.PROCESSING
        locked.failure_reason = ""
        locked.last_attempted_at = timezone.now()
        locked.attempt_count += 1
        locked.save(
            update_fields=(
                "receiving_account",
                "recipient_code_snapshot",
                "receiving_account_name_snapshot",
                "receiving_account_network_snapshot",
                "receiving_account_masked_number_snapshot",
                "status",
                "failure_reason",
                "last_attempted_at",
                "attempt_count",
                "updated_at",
            )
        )

    gateway_client = client or PaystackClient()

    # A previous request may have timed out after Paystack accepted it.
    # Verify the same reference before ever trying to initiate it again.
    try:
        existing = gateway_client.verify_transfer(payout.reference)
    except PaystackRequestError as exc:
        if exc.status_code != 404:
            return _mark_retry(payout.id, str(exc))
    else:
        return _apply_provider_state(payout.id, existing)

    try:
        response = gateway_client.initiate_transfer(
            amount_subunit=_amount_subunit(payout.amount),
            recipient_code=account.paystack_recipient_code,
            reference=payout.reference,
            reason=f"StockFlow payout for {payout.payment.receipt_number or payout.payment.id}",
        )
    except PaystackError as exc:
        return _mark_retry(payout.id, str(exc))

    return _apply_provider_state(payout.id, response)


def handle_paystack_transfer_webhook(*, event_name, event_data):
    reference = str(event_data.get("reference", "")).strip()
    if not reference:
        return False

    payout = MerchantPayout.objects.filter(reference=reference).first()
    if payout is None:
        return False

    amount = event_data.get("amount")
    if amount is not None and int(amount) != _amount_subunit(payout.amount):
        _mark_retry(
            payout.id,
            "Paystack transfer webhook amount did not match the merchant payout.",
        )
        return False

    mapped = {
        "transfer.success": "success",
        "transfer.failed": "failed",
        "transfer.reversed": "reversed",
    }.get(event_name)
    if not mapped:
        return False

    data = dict(event_data)
    data["status"] = mapped
    _apply_provider_state(payout.id, data, fallback_status=mapped)
    return True
