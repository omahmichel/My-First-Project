from django.db import transaction
from django.utils import timezone

from .models import BusinessPaymentAccount
from .paystack_client import PaystackClient, PaystackError, PaystackRequestError


NETWORK_ALIASES = {
    "mtn": "MTN",
    "atl": "ATL",
    "airteltigo": "ATL",
    "atmoney": "ATL",
    "vod": "VOD",
    "vodafone": "VOD",
    "telecel": "VOD",
}


def paystack_mobile_money_bank_code(network):
    code = NETWORK_ALIASES.get(str(network or "").strip().lower())
    if not code:
        raise PaystackRequestError(
            "The selected Mobile Money payout network is not supported in Ghana.",
            code="paystack_payout_network_invalid",
        )
    return code


def _save_sync_error(account, message):
    BusinessPaymentAccount.objects.filter(pk=account.pk).update(
        paystack_recipient_code="",
        paystack_recipient_id="",
        paystack_recipient_synced_at=None,
        paystack_recipient_last_error=str(message or "")[:500],
    )
    return BusinessPaymentAccount.objects.get(pk=account.pk)


def sync_mobile_money_payout_recipient(account, client=None):
    if account.account_type != BusinessPaymentAccount.AccountType.MOBILE_MONEY:
        raise PaystackRequestError(
            "Only Mobile Money receiving accounts can be connected for MoMo payouts.",
            code="paystack_payout_account_type_invalid",
        )
    if not account.is_active:
        raise PaystackRequestError(
            "Activate the Mobile Money receiving account before connecting payouts.",
            code="paystack_payout_account_inactive",
        )

    expected_updated_at = account.updated_at
    bank_code = paystack_mobile_money_bank_code(account.network)
    gateway_client = client or PaystackClient()

    try:
        response = gateway_client.create_transfer_recipient(
            name=account.account_name,
            account_number=account.get_account_number(),
            bank_code=bank_code,
            currency="GHS",
            metadata={
                "stockflow_business_id": str(account.business_id),
                "stockflow_payment_account_id": str(account.id),
            },
        )
    except PaystackError as exc:
        _save_sync_error(account, str(exc))
        raise

    recipient_code = str(response.get("recipient_code", "")).strip()
    recipient_id = str(response.get("id", "")).strip()
    if not recipient_code:
        error = PaystackRequestError(
            "Paystack did not return a transfer recipient code.",
            code="paystack_invalid_response",
        )
        _save_sync_error(account, str(error))
        raise error

    with transaction.atomic():
        locked = BusinessPaymentAccount.objects.select_for_update().get(pk=account.pk)
        if locked.updated_at != expected_updated_at:
            raise PaystackRequestError(
                "The receiving account changed while Paystack was connecting it. Try again.",
                code="paystack_payout_account_changed",
            )
        locked.paystack_recipient_code = recipient_code
        locked.paystack_recipient_id = recipient_id
        locked.paystack_recipient_synced_at = timezone.now()
        locked.paystack_recipient_last_error = ""
        locked.save(
            update_fields=(
                "paystack_recipient_code",
                "paystack_recipient_id",
                "paystack_recipient_synced_at",
                "paystack_recipient_last_error",
                "updated_at",
            )
        )
        return locked


def sync_mobile_money_payout_recipient_best_effort(account, client=None):
    try:
        return sync_mobile_money_payout_recipient(account, client=client)
    except PaystackError:
        return BusinessPaymentAccount.objects.get(pk=account.pk)
