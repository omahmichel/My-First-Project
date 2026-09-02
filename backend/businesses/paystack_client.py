from urllib.parse import quote

import requests
from django.conf import settings


class PaystackError(Exception):
    """Base exception for safe Paystack integration failures."""

    def __init__(
        self,
        message,
        *,
        code="paystack_error",
        status_code=None,
    ):
        # Keeps gateway errors structured without exposing secret values.
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class PaystackConfigurationError(PaystackError):
    """Raised when required Paystack settings are unavailable."""


class PaystackRequestError(PaystackError):
    """Raised when Paystack cannot complete or understand a request."""


class PaystackClient:
    """Calls Paystack transaction endpoints from the Django backend."""

    base_url = "https://api.paystack.co"
    timeout = (5, 20)

    # Paystack provider codes supported for Ghana Mobile Money charges.
    ghana_mobile_money_providers = frozenset(
        {
            "mtn",
            "atl",
            "vod",
        }
    )

    def __init__(self, *, session=None, secret_key=None):
        # Refuses to run against an unintended payment provider.
        gateway = settings.PAYMENT_GATEWAY

        if gateway != "paystack":
            raise PaystackConfigurationError(
                "The payment gateway is not configured as Paystack.",
                code="paystack_not_configured",
            )

        # Reads the secret only on the server and never returns it.
        self.secret_key = (
            secret_key or settings.PAYMENT_GATEWAY_SECRET_KEY
        ).strip()

        if not self.secret_key:
            raise PaystackConfigurationError(
                "The Paystack secret key is missing.",
                code="paystack_secret_missing",
            )

        self.session = session or requests.Session()

    @property
    def headers(self):
        # Uses Paystack's required bearer authentication for API calls.
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def initialize_transaction(
        self,
        *,
        email,
        amount_subunit,
        reference,
        currency="GHS",
        callback_url="",
        metadata=None,
    ):
        # Sends server-controlled price and ownership metadata to Paystack.
        if not email:
            raise ValueError("A customer email address is required.")

        if not isinstance(amount_subunit, int) or amount_subunit <= 0:
            raise ValueError(
                "The payment amount must be a positive integer."
            )

        if not reference:
            raise ValueError("A payment reference is required.")

        payload = {
            "email": email,
            "amount": amount_subunit,
            "reference": reference,
            "currency": currency,
        }

        if callback_url:
            payload["callback_url"] = callback_url

        if metadata:
            payload["metadata"] = metadata

        data = self._request(
            "POST",
            "/transaction/initialize",
            json=payload,
        )

        # Rejects incomplete responses before the frontend sees them.
        required_fields = (
            "authorization_url",
            "access_code",
            "reference",
        )
        missing_fields = [
            field for field in required_fields if not data.get(field)
        ]

        if missing_fields:
            raise PaystackRequestError(
                "Paystack returned an incomplete initialization response.",
                code="paystack_invalid_response",
            )

        return data

    def create_mobile_money_charge(
        self,
        *,
        email,
        amount_subunit,
        reference,
        phone,
        provider,
        currency="GHS",
        metadata=None,
    ):
        # Initiates one Ghana Mobile Money prompt using server values.
        if not email:
            raise ValueError("A customer email address is required.")

        if not isinstance(amount_subunit, int) or amount_subunit <= 0:
            raise ValueError(
                "The payment amount must be a positive integer."
            )

        if not reference:
            raise ValueError("A payment reference is required.")

        normalized_phone = str(phone or "").strip()
        normalized_provider = str(provider or "").strip().lower()

        if not normalized_phone:
            raise ValueError(
                "A customer Mobile Money number is required."
            )

        if normalized_provider not in self.ghana_mobile_money_providers:
            raise ValueError(
                "The Mobile Money provider is not supported in Ghana."
            )

        payload = {
            "email": email,
            "amount": amount_subunit,
            "reference": reference,
            "currency": currency,
            "mobile_money": {
                "phone": normalized_phone,
                "provider": normalized_provider,
            },
        }

        if metadata:
            payload["metadata"] = metadata

        data = self._request(
            "POST",
            "/charge",
            json=payload,
        )

        # A prompt cannot continue without its reference and current state.
        required_fields = (
            "reference",
            "status",
            "display_text",
        )
        missing_fields = [
            field for field in required_fields if not data.get(field)
        ]

        if missing_fields or data["reference"] != reference:
            raise PaystackRequestError(
                "Paystack returned an incomplete Mobile Money response.",
                code="paystack_invalid_response",
            )

        return data

    def create_transfer_recipient(
        self,
        *,
        name,
        account_number,
        bank_code,
        currency="GHS",
        metadata=None,
    ):
        # Creates one reusable Ghana Mobile Money beneficiary for payouts.
        normalized_name = str(name or "").strip()
        normalized_number = str(account_number or "").strip()
        normalized_bank_code = str(bank_code or "").strip().upper()

        if not normalized_name:
            raise ValueError("A registered Mobile Money account name is required.")
        if not normalized_number:
            raise ValueError("A registered Mobile Money number is required.")
        if normalized_bank_code not in {"MTN", "ATL", "VOD"}:
            raise ValueError("The Mobile Money payout network is not supported in Ghana.")

        payload = {
            "type": "mobile_money",
            "name": normalized_name,
            "account_number": normalized_number,
            "bank_code": normalized_bank_code,
            "currency": currency,
        }
        if metadata:
            payload["metadata"] = metadata

        data = self._request("POST", "/transferrecipient", json=payload)
        if not str(data.get("recipient_code", "")).strip():
            raise PaystackRequestError(
                "Paystack returned an incomplete transfer-recipient response.",
                code="paystack_invalid_response",
            )
        return data

    def initiate_transfer(
        self,
        *,
        amount_subunit,
        recipient_code,
        reference,
        reason,
    ):
        # Sends one merchant payout from the integration's Paystack balance.
        if not isinstance(amount_subunit, int) or amount_subunit <= 0:
            raise ValueError("The payout amount must be a positive integer.")
        if not str(recipient_code or "").strip():
            raise ValueError("A Paystack recipient code is required.")
        if not str(reference or "").strip():
            raise ValueError("A merchant payout reference is required.")

        data = self._request(
            "POST",
            "/transfer",
            json={
                "source": "balance",
                "amount": amount_subunit,
                "recipient": recipient_code,
                "reference": reference,
                "reason": str(reason or "StockFlow merchant payout")[:100],
            },
        )

        if str(data.get("reference", "")).strip() != reference:
            raise PaystackRequestError(
                "Paystack returned an invalid transfer reference.",
                code="paystack_invalid_response",
            )
        if not str(data.get("status", "")).strip():
            raise PaystackRequestError(
                "Paystack returned an incomplete transfer response.",
                code="paystack_invalid_response",
            )
        return data

    def verify_transfer(self, reference):
        if not reference:
            raise ValueError("A merchant payout reference is required.")
        encoded_reference = quote(reference, safe="")
        return self._request("GET", f"/transfer/verify/{encoded_reference}")

    def verify_transaction(self, reference):
        # Encodes the reference safely before using it in the URL path.
        if not reference:
            raise ValueError("A payment reference is required.")

        encoded_reference = quote(reference, safe="")

        return self._request(
            "GET",
            f"/transaction/verify/{encoded_reference}",
        )

    def _request(self, method, path, **kwargs):
        # Applies explicit timeouts so gateway delays cannot hang Django.
        try:
            response = self.session.request(
                method,
                f"{self.base_url}{path}",
                headers=self.headers,
                timeout=self.timeout,
                **kwargs,
            )
        except requests.Timeout as exc:
            raise PaystackRequestError(
                "Paystack did not respond in time.",
                code="paystack_timeout",
            ) from exc
        except requests.RequestException as exc:
            raise PaystackRequestError(
                "StockFlow could not reach Paystack.",
                code="paystack_connection_failed",
            ) from exc

        # Converts malformed responses into one controlled gateway error.
        try:
            payload = response.json()
        except ValueError as exc:
            raise PaystackRequestError(
                "Paystack returned an unreadable response.",
                code="paystack_invalid_response",
                status_code=response.status_code,
            ) from exc

        message = (
            payload.get("message")
            if isinstance(payload, dict)
            else None
        )

        if not 200 <= response.status_code < 300:
            raise PaystackRequestError(
                message or "Paystack rejected the request.",
                code="paystack_request_rejected",
                status_code=response.status_code,
            )

        if (
            not isinstance(payload, dict)
            or payload.get("status") is not True
            or not isinstance(payload.get("data"), dict)
        ):
            raise PaystackRequestError(
                message or "Paystack returned an invalid response.",
                code="paystack_invalid_response",
                status_code=response.status_code,
            )

        return payload["data"]
