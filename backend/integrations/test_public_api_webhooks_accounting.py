import hashlib
import hmac
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from businesses.models import Business, BusinessMembership
from integrations.models import (
    AccountingConnection, ApiCredential, WebhookDelivery, WebhookEndpoint,
)
from integrations.security import generate_api_key_material
from integrations.webhooks.service import (
    emit_webhook_event, endpoint_signing_secret, process_due_webhook_deliveries,
)


class IntegrationBackboneApiTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            email="slice3-owner@example.com", password="StrongPass123!"
        )
        self.manager = User.objects.create_user(
            email="slice3-manager@example.com", password="StrongPass123!"
        )
        self.business = Business.objects.create(
            owner=self.owner, name="Slice Three Business", slug="slice-three-business",
            business_type=Business.BusinessType.BUILDING_MATERIALS,
        )
        BusinessMembership.objects.create(
            business=self.business, user=self.manager,
            role=BusinessMembership.Role.MANAGER,
        )

    def test_owner_creates_api_key_and_secret_is_shown_once(self):
        self.client.force_authenticate(self.owner)
        url = f"/api/businesses/{self.business.id}/integrations/api-keys/"
        created = self.client.post(url, {
            "name": "Reporting", "scopes": ["customers:read"]
        }, format="json")
        self.assertEqual(created.status_code, 201)
        raw = created.data["apiKey"]
        row = ApiCredential.objects.get(id=created.data["id"])
        self.assertNotEqual(row.secret_hash, raw)
        listed = self.client.get(url)
        self.assertEqual(listed.status_code, 200)
        self.assertNotIn("apiKey", listed.data["credentials"][0])

    def test_public_api_scope_and_revocation(self):
        prefix, raw, digest = generate_api_key_material()
        row = ApiCredential.objects.create(
            business=self.business, name="Customers", key_prefix=prefix,
            secret_hash=digest, scopes=["customers:read"], created_by=self.owner,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"StockFlow {raw}")
        ok = self.client.get("/api/public/v1/customers/")
        self.assertEqual(ok.status_code, 200)
        denied = self.client.get("/api/public/v1/sales/")
        self.assertEqual(denied.status_code, 403)
        row.revoked_at = timezone.now()
        row.is_active = False
        row.save(update_fields=("revoked_at", "is_active", "updated_at"))
        revoked = self.client.get("/api/public/v1/customers/")
        self.assertEqual(revoked.status_code, 401)

    def test_private_webhook_url_is_rejected(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            f"/api/businesses/{self.business.id}/integrations/webhooks/endpoints/",
            {
                "name": "Unsafe", "url": "https://127.0.0.1/hook",
                "events": ["customer.created"],
            }, format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_manager_cannot_manage_integrations(self):
        self.client.force_authenticate(self.manager)
        response = self.client.post(
            f"/api/businesses/{self.business.id}/integrations/api-keys/",
            {"name": "Denied", "scopes": ["customers:read"]},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    @override_settings(QUICKBOOKS_CLIENT_ID='', QUICKBOOKS_CLIENT_SECRET='', XERO_CLIENT_ID='', XERO_CLIENT_SECRET='')
    def test_accounting_connectors_are_provider_neutral_and_export_only(self):
        self.client.force_authenticate(self.owner)
        base = f"/api/businesses/{self.business.id}/integrations/accounting/connectors"
        capabilities = self.client.get(base + "/capabilities/")
        self.assertEqual(capabilities.status_code, 200)
        self.assertEqual(capabilities.data["direction"], "stockflow_to_accounting")
        providers = {row["provider"]: row for row in capabilities.data["providers"]}
        self.assertIn("quickbooks", providers)
        self.assertIn("xero", providers)
        self.assertFalse(providers["quickbooks"]["liveConnectionAvailable"])
        created = self.client.post(base + "/connections/", {
            "provider": "quickbooks", "name": "Main Accounts",
            "settings": {"salesMode": "invoice"},
        }, format="json")
        self.assertEqual(created.status_code, 201)
        self.assertEqual(
            AccountingConnection.objects.get(id=created.data["id"]).status,
            AccountingConnection.Status.DISCONNECTED,
        )


class OutboundWebhookServiceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            email="hook-owner@example.com", password="StrongPass123!"
        )
        self.business = Business.objects.create(
            owner=self.owner, name="Webhook Business", slug="webhook-business",
            business_type=Business.BusinessType.BUILDING_MATERIALS,
        )
        self.endpoint = WebhookEndpoint.objects.create(
            business=self.business, name="ERP", url="https://example.com/hook",
            events=["customer.created"], created_by=self.owner,
        )

    @patch("integrations.webhooks.service.assert_public_destination", return_value=None)
    def test_event_dedupes_and_success_is_signed_and_audited(self, _destination):
        first = emit_webhook_event(
            business=self.business, event_type="customer.created",
            source_type="customer", source_id="customer-1",
            payload={"id": "customer-1", "name": "Test"},
        )
        second = emit_webhook_event(
            business=self.business, event_type="customer.created",
            source_type="customer", source_id="customer-1",
            payload={"id": "customer-1", "name": "Test"},
        )
        self.assertEqual(first.id, second.id)
        self.assertEqual(WebhookDelivery.objects.count(), 1)

        response = Mock(status_code=200, text="ok")
        sender = Mock(return_value=response)
        result = process_due_webhook_deliveries(request_func=sender)
        self.assertEqual(result["sent"], 1)
        delivery = WebhookDelivery.objects.get()
        self.assertEqual(delivery.status, WebhookDelivery.Status.SENT)
        kwargs = sender.call_args.kwargs
        timestamp = kwargs["headers"]["X-StockFlow-Timestamp"]
        body = kwargs["data"]
        expected = hmac.new(
            endpoint_signing_secret(self.endpoint).encode("utf-8"),
            timestamp.encode("utf-8") + b"." + body,
            hashlib.sha256,
        ).hexdigest()
        self.assertEqual(
            kwargs["headers"]["X-StockFlow-Signature"], f"sha256={expected}"
        )
        self.assertFalse(kwargs["allow_redirects"])

    @patch("integrations.webhooks.service.assert_public_destination", return_value=None)
    def test_failure_is_audited_and_retried_later(self, _destination):
        emit_webhook_event(
            business=self.business, event_type="customer.created",
            source_type="customer", source_id="customer-2",
            payload={"id": "customer-2"},
        )
        response = Mock(status_code=503, text="temporary")
        result = process_due_webhook_deliveries(request_func=Mock(return_value=response))
        self.assertEqual(result["failed"], 1)
        delivery = WebhookDelivery.objects.get()
        self.assertEqual(delivery.status, WebhookDelivery.Status.FAILED)
        self.assertEqual(delivery.attempt_count, 1)
        self.assertIsNotNone(delivery.next_attempt_at)
