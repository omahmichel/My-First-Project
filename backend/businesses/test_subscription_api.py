import hashlib
import hmac
import json
from datetime import timedelta
from unittest.mock import patch

from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from businesses.models import Business, SubscriptionPayment
from businesses.subscription_service import SubscriptionPaymentError


TEST_PAYMENT_SETTINGS = {
    "PAYMENT_GATEWAY": "paystack",
    "PAYMENT_GATEWAY_SECRET_KEY": "sk_test_stockflow_webhook",
    "PAYMENT_CALLBACK_URL": (
        "http://localhost:5173/app/subscription"
    ),
}


@override_settings(**TEST_PAYMENT_SETTINGS)
class SubscriptionPaymentAPITests(APITestCase):
    """Protects owner-only checkout and verification API behaviour."""

    def setUp(self):
        # Creates one owner, unrelated user and expired test business.
        self.owner = User.objects.create_user(
            email="api.owner@stockflow.test",
            password="StrongPass123!",
            full_name="API Owner",
        )
        self.other_user = User.objects.create_user(
            email="api.other@stockflow.test",
            password="StrongPass123!",
            full_name="API Other",
        )
        self.business = Business.objects.create(
            owner=self.owner,
            name="API Payment Shop",
            slug="api-payment-shop",
            business_type=Business.BusinessType.BOUTIQUE,
            trial_started_at=timezone.now() - timedelta(days=61),
            trial_ends_at=timezone.now() - timedelta(days=1),
        )
        self.initialize_url = (
            f"/api/businesses/{self.business.id}/"
            "subscription/payments/initialize/"
        )

    def authenticate(self, user):
        # Uses direct JWT-independent authentication for API isolation.
        self.client.force_authenticate(user=user)

    @patch(
        "businesses.subscription_views."
        "initialize_subscription_payment"
    )
    def test_owner_can_initialize_fixed_subscription_checkout(
        self,
        initialize_mock,
    ):
        # The API returns the checkout URL without exposing an access code.
        payment = SubscriptionPayment.objects.create(
            business=self.business,
            initiated_by=self.owner,
            initiated_by_email=self.owner.email,
            initiated_by_name=self.owner.full_name,
            authorization_url=(
                "https://checkout.paystack.com/api-test"
            ),
            access_code="private-access-code",
        )
        initialize_mock.return_value = payment
        self.authenticate(self.owner)

        response = self.client.post(
            self.initialize_url,
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.data,
        )
        self.assertEqual(response.data["amount"], "99.00")
        self.assertEqual(response.data["currency"], "GHS")
        self.assertEqual(response.data["durationDays"], 40)
        self.assertNotIn("accessCode", response.data)
        initialize_mock.assert_called_once_with(
            user=self.owner,
            business_id=self.business.id,
            callback_url=(
                "http://localhost:5173/app/subscription"
            ),
        )

    def test_non_owner_cannot_initialize_payment(self):
        # Unauthorized users receive no information about the business.
        self.authenticate(self.other_user)

        response = self.client.post(
            self.initialize_url,
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertFalse(
            SubscriptionPayment.objects.exists()
        )

    @patch(
        "businesses.subscription_views."
        "verify_and_fulfill_subscription_payment"
    )
    def test_owner_can_verify_own_business_payment(
        self,
        verify_mock,
    ):
        # Verification returns the renewed business access state.
        payment = SubscriptionPayment.objects.create(
            business=self.business,
            initiated_by=self.owner,
            initiated_by_email=self.owner.email,
            initiated_by_name=self.owner.full_name,
            status=SubscriptionPayment.Status.SUCCESSFUL,
            authorization_url=(
                "https://checkout.paystack.com/verify-test"
            ),
            verified_at=timezone.now(),
            fulfilled_at=timezone.now(),
        )
        self.business.subscription_status = (
            Business.SubscriptionStatus.ACTIVE
        )
        self.business.subscription_started_at = timezone.now()
        self.business.subscription_ends_at = (
            timezone.now() + timedelta(days=40)
        )
        self.business.save(
            update_fields=(
                "subscription_status",
                "subscription_started_at",
                "subscription_ends_at",
            )
        )
        verify_mock.return_value = (
            payment,
            self.business,
            True,
        )
        self.authenticate(self.owner)
        url = (
            f"/api/businesses/{self.business.id}/"
            f"subscription/payments/{payment.reference}/verify/"
        )

        response = self.client.post(url, {}, format="json")

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )
        self.assertTrue(response.data["activated"])
        self.assertTrue(response.data["hasSystemAccess"])
        verify_mock.assert_called_once_with(
            reference=payment.reference,
        )

    def test_owner_cannot_verify_another_business_reference(self):
        # A reference must belong to the business in the request URL.
        second_business = Business.objects.create(
            owner=self.owner,
            name="Second API Shop",
            slug="second-api-shop",
            business_type=Business.BusinessType.BOUTIQUE,
        )
        payment = SubscriptionPayment.objects.create(
            business=second_business,
            initiated_by=self.owner,
            initiated_by_email=self.owner.email,
            initiated_by_name=self.owner.full_name,
        )
        self.authenticate(self.owner)
        url = (
            f"/api/businesses/{self.business.id}/"
            f"subscription/payments/{payment.reference}/verify/"
        )

        response = self.client.post(url, {}, format="json")

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )


@override_settings(**TEST_PAYMENT_SETTINGS)
class PaystackWebhookAPITests(APITestCase):
    """Protects raw-body signature checks and webhook idempotency."""

    webhook_url = "/api/payments/paystack/webhook/"

    def signed_post(self, payload, *, signature=None):
        # Sends deterministic raw JSON so the signature matches exactly.
        raw_body = json.dumps(
            payload,
            separators=(",", ":"),
        ).encode("utf-8")
        valid_signature = hmac.new(
            TEST_PAYMENT_SETTINGS[
                "PAYMENT_GATEWAY_SECRET_KEY"
            ].encode("utf-8"),
            raw_body,
            hashlib.sha512,
        ).hexdigest()

        return self.client.generic(
            "POST",
            self.webhook_url,
            data=raw_body,
            content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE=(
                valid_signature
                if signature is None
                else signature
            ),
        )

    def test_invalid_signature_is_rejected(self):
        # Unsigned or forged requests cannot trigger verification.
        response = self.signed_post(
            {
                "event": "charge.success",
                "data": {"reference": "STF-FORGED"},
            },
            signature="invalid-signature",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    @patch(
        "businesses.subscription_views."
        "verify_and_fulfill_subscription_payment"
    )
    def test_valid_charge_success_triggers_server_verification(
        self,
        verify_mock,
    ):
        # A signed event still causes a fresh server-to-server verification.
        verify_mock.return_value = (object(), object(), True)

        response = self.signed_post(
            {
                "event": "charge.success",
                "data": {"reference": "STF-WEBHOOK-001"},
            }
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )
        self.assertTrue(response.data["processed"])
        self.assertTrue(response.data["activated"])
        verify_mock.assert_called_once_with(
            reference="STF-WEBHOOK-001",
        )

    @patch(
        "businesses.subscription_views."
        "verify_and_fulfill_subscription_payment"
    )
    def test_unrelated_event_is_acknowledged_without_processing(
        self,
        verify_mock,
    ):
        # Account-level Paystack events unrelated to charges are ignored.
        response = self.signed_post(
            {
                "event": "transfer.success",
                "data": {"reference": "OTHER-001"},
            }
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertFalse(response.data["processed"])
        verify_mock.assert_not_called()

    @patch(
        "businesses.subscription_views."
        "verify_and_fulfill_subscription_payment"
    )
    def test_unknown_subscription_reference_is_safely_ignored(
        self,
        verify_mock,
    ):
        # Other Paystack charges on the account do not become subscriptions.
        verify_mock.side_effect = SubscriptionPaymentError(
            "The subscription payment reference was not found.",
            code="subscription_payment_not_found",
        )

        response = self.signed_post(
            {
                "event": "charge.success",
                "data": {"reference": "OTHER-CHARGE-001"},
            }
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertFalse(response.data["processed"])
