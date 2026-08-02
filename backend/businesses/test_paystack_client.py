from unittest.mock import Mock

import requests
from django.test import SimpleTestCase, override_settings

from businesses.paystack_client import (
    PaystackClient,
    PaystackConfigurationError,
    PaystackRequestError,
)


@override_settings(
    PAYMENT_GATEWAY="paystack",
    PAYMENT_GATEWAY_SECRET_KEY="sk_test_stockflow",
)
class PaystackClientTests(SimpleTestCase):
    """Protects backend-only Paystack initialization and verification."""

    def setUp(self):
        # Injects a fake HTTP session so tests never contact Paystack.
        self.session = Mock()
        self.client = PaystackClient(session=self.session)

    def build_response(self, payload, status_code=200):
        # Creates a minimal JSON response matching requests.Response use.
        response = Mock()
        response.status_code = status_code
        response.json.return_value = payload
        return response

    def test_initialize_transaction_sends_server_controlled_values(self):
        # The backend controls the exact amount, currency and reference.
        self.session.request.return_value = self.build_response(
            {
                "status": True,
                "message": "Authorization URL created",
                "data": {
                    "authorization_url": (
                        "https://checkout.paystack.com/test-code"
                    ),
                    "access_code": "test-code",
                    "reference": "STF-TEST-001",
                },
            }
        )

        data = self.client.initialize_transaction(
            email="owner@stockflow.test",
            amount_subunit=9900,
            reference="STF-TEST-001",
            currency="GHS",
            callback_url="https://stockflow.test/payment/callback",
            metadata={"business_id": "business-123"},
        )

        self.assertEqual(data["reference"], "STF-TEST-001")
        self.session.request.assert_called_once_with(
            "POST",
            "https://api.paystack.co/transaction/initialize",
            headers={
                "Authorization": "Bearer sk_test_stockflow",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=(5, 20),
            json={
                "email": "owner@stockflow.test",
                "amount": 9900,
                "reference": "STF-TEST-001",
                "currency": "GHS",
                "callback_url": (
                    "https://stockflow.test/payment/callback"
                ),
                "metadata": {"business_id": "business-123"},
            },
        )

    def test_verify_transaction_encodes_reference(self):
        # Special characters cannot alter the Paystack verification path.
        self.session.request.return_value = self.build_response(
            {
                "status": True,
                "message": "Verification successful",
                "data": {
                    "status": "success",
                    "reference": "STF TEST/001",
                },
            }
        )

        data = self.client.verify_transaction("STF TEST/001")

        self.assertEqual(data["status"], "success")
        self.session.request.assert_called_once_with(
            "GET",
            (
                "https://api.paystack.co/transaction/verify/"
                "STF%20TEST%2F001"
            ),
            headers={
                "Authorization": "Bearer sk_test_stockflow",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=(5, 20),
        )

    def test_timeout_becomes_controlled_gateway_error(self):
        # Network timeouts produce a safe code instead of a server crash.
        self.session.request.side_effect = requests.Timeout()

        with self.assertRaises(PaystackRequestError) as context:
            self.client.verify_transaction("STF-TEST-002")

        self.assertEqual(context.exception.code, "paystack_timeout")

    def test_rejected_request_preserves_safe_message_and_status(self):
        # Paystack API failures remain understandable to calling services.
        self.session.request.return_value = self.build_response(
            {
                "status": False,
                "message": "Invalid key",
            },
            status_code=401,
        )

        with self.assertRaises(PaystackRequestError) as context:
            self.client.verify_transaction("STF-TEST-003")

        self.assertEqual(str(context.exception), "Invalid key")
        self.assertEqual(
            context.exception.code,
            "paystack_request_rejected",
        )
        self.assertEqual(context.exception.status_code, 401)

    def test_incomplete_initialization_response_is_rejected(self):
        # Checkout cannot continue without all required Paystack fields.
        self.session.request.return_value = self.build_response(
            {
                "status": True,
                "message": "Authorization URL created",
                "data": {
                    "reference": "STF-TEST-004",
                },
            }
        )

        with self.assertRaises(PaystackRequestError) as context:
            self.client.initialize_transaction(
                email="owner@stockflow.test",
                amount_subunit=9900,
                reference="STF-TEST-004",
            )

        self.assertEqual(
            context.exception.code,
            "paystack_invalid_response",
        )


@override_settings(
    PAYMENT_GATEWAY="paystack",
    PAYMENT_GATEWAY_SECRET_KEY="",
)
class PaystackConfigurationTests(SimpleTestCase):
    """Rejects Paystack use when its server secret is unavailable."""

    def test_missing_secret_key_is_rejected(self):
        # Payment code must never run without a configured secret key.
        with self.assertRaises(PaystackConfigurationError) as context:
            PaystackClient(session=Mock())

        self.assertEqual(
            context.exception.code,
            "paystack_secret_missing",
        )
