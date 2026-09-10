from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from businesses.models import Business, BusinessMembership
from integrations.accounting.live import XERO_SCOPES
from integrations.messaging.service import messaging_capabilities
from integrations.messaging.whatsapp_live import save_whatsapp_credentials
from integrations.models import ProviderCredential
from integrations.provider_credentials import (
    decrypt_provider_payload,
    get_provider_credential,
    rotate_provider_credential,
    save_provider_credential,
)


@override_settings(DEBUG=True)
class LiveProviderCredentialTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            email="live-provider-owner@example.com",
            password="StrongPass123!",
        )
        self.manager = User.objects.create_user(
            email="live-provider-manager@example.com",
            password="StrongPass123!",
        )
        self.business = Business.objects.create(
            owner=self.owner,
            name="Live Provider Business",
            slug="live-provider-business",
            business_type=Business.BusinessType.BUILDING_MATERIALS,
        )
        BusinessMembership.objects.create(
            business=self.business,
            user=self.manager,
            role=BusinessMembership.Role.MANAGER,
        )

    def test_provider_payload_is_encrypted_at_rest(self):
        secret = "refresh-token-that-must-never-be-plaintext"
        row = save_provider_credential(
            business=self.business,
            category="accounting",
            provider="xero",
            payload={"access_token": "access", "refresh_token": secret},
            created_by=self.owner,
        )
        self.assertNotIn(secret, row.encrypted_payload)
        self.assertEqual(
            decrypt_provider_payload(row.encrypted_payload)["refresh_token"],
            secret,
        )

    def test_rotating_token_pair_is_compare_and_swap_safe(self):
        row = save_provider_credential(
            business=self.business,
            category="accounting",
            provider="xero",
            payload={"access_token": "access-1", "refresh_token": "refresh-1"},
        )
        _row, payload, changed = rotate_provider_credential(
            row=row,
            expected_refresh_token="refresh-1",
            replacement_payload={
                "access_token": "access-2",
                "refresh_token": "refresh-2",
            },
            access_expires_at=None,
        )
        self.assertTrue(changed)
        self.assertEqual(payload["refresh_token"], "refresh-2")

        _row, latest, changed = rotate_provider_credential(
            row=row,
            expected_refresh_token="refresh-1",
            replacement_payload={
                "access_token": "stale-access",
                "refresh_token": "stale-refresh",
            },
            access_expires_at=None,
        )
        self.assertFalse(changed)
        self.assertEqual(latest["refresh_token"], "refresh-2")

    def test_xero_uses_2026_granular_scopes(self):
        self.assertNotIn("accounting.transactions", XERO_SCOPES)
        self.assertIn("accounting.invoices", XERO_SCOPES)
        self.assertIn("accounting.payments", XERO_SCOPES)
        self.assertIn("offline_access", XERO_SCOPES)

    def test_whatsapp_can_be_enabled_only_after_encrypted_credentials_exist(self):
        url = (
            f"/api/businesses/{self.business.id}/integrations/messaging/preferences/"
        )
        self.client.force_authenticate(self.owner)
        denied = self.client.patch(
            url,
            {
                "whatsappEnabled": True,
                "recipientPhone": "0244000000",
            },
            format="json",
        )
        self.assertEqual(denied.status_code, 400)
        self.assertIn("whatsappEnabled", denied.data)

        save_whatsapp_credentials(
            business=self.business,
            access_token="test-whatsapp-token",
            phone_number_id="1234567890",
            api_version="v23.0",
            created_by=self.owner,
        )
        allowed = self.client.patch(
            url,
            {
                "whatsappEnabled": True,
                "recipientPhone": "0244000000",
            },
            format="json",
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertTrue(allowed.data["whatsappEnabled"])

    def test_whatsapp_capability_is_business_specific(self):
        self.assertFalse(messaging_capabilities(business=self.business)["whatsapp"]["available"])
        save_whatsapp_credentials(
            business=self.business,
            access_token="test-whatsapp-token",
            phone_number_id="1234567890",
            api_version="v23.0",
            created_by=self.owner,
        )
        capability = messaging_capabilities(business=self.business)["whatsapp"]
        self.assertTrue(capability["available"])
        self.assertEqual(capability["provider"], "whatsapp_cloud_api")

    def test_manager_cannot_store_whatsapp_credentials(self):
        url = (
            f"/api/businesses/{self.business.id}/integrations/messaging/"
            "whatsapp/credentials/"
        )
        self.client.force_authenticate(self.manager)
        response = self.client.put(
            url,
            {
                "accessToken": "secret-token",
                "phoneNumberId": "1234567890",
                "apiVersion": "v23.0",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(ProviderCredential.objects.count(), 0)

    def test_owner_whatsapp_credential_response_never_echoes_secret(self):
        url = (
            f"/api/businesses/{self.business.id}/integrations/messaging/"
            "whatsapp/credentials/"
        )
        self.client.force_authenticate(self.owner)
        response = self.client.put(
            url,
            {
                "accessToken": "secret-token-value",
                "phoneNumberId": "1234567890",
                "apiVersion": "v23.0",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("secret-token-value", str(response.data))
        self.assertFalse(response.data["credentialsReturnedToClient"])
        row, payload = get_provider_credential(
            business=self.business,
            category="messaging",
            provider="whatsapp",
            required=True,
        )
        self.assertIsNotNone(row)
        self.assertEqual(payload["access_token"], "secret-token-value")

from django.http import QueryDict
from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError
from integrations.commerce.live import _verify_shopify_hmac
import hashlib
import hmac


@override_settings(SHOPIFY_CLIENT_SECRET='dummy-shopify-secret')
class ShopifyCallbackSignatureTests(SimpleTestCase):
    def callback_query(self):
        query = QueryDict('timestamp=1234567890&state=payload%3Asignature%2Btest&shop=test-store.myshopify.com&code=test-code', mutable=True)
        message = b'code=test-code&shop=test-store.myshopify.com&state=payload:signature+test&timestamp=1234567890'
        query['hmac'] = hmac.new(b'dummy-shopify-secret', message, hashlib.sha256).hexdigest()
        return query

    def test_accepts_signed_callback_with_encoded_state(self):
        _verify_shopify_hmac(self.callback_query())

    def test_rejects_tampered_callback(self):
        query = self.callback_query()
        query['shop'] = 'different-store.myshopify.com'
        with self.assertRaises(ValidationError):
            _verify_shopify_hmac(query)

    def test_rejects_missing_signature(self):
        query = self.callback_query()
        del query['hmac']
        with self.assertRaises(ValidationError):
            _verify_shopify_hmac(query)

    def test_rejects_wrong_secret(self):
        query = self.callback_query()
        with self.settings(SHOPIFY_CLIENT_SECRET='wrong-secret'):
            with self.assertRaises(ValidationError):
                _verify_shopify_hmac(query)
