from urllib.parse import parse_qs, urlparse
from unittest.mock import Mock, patch

from django.test import override_settings
from rest_framework.test import APITestCase

from integrations.models import ProviderCredential
from integrations.provider_credentials import get_provider_credential
from storefront import test_listings


META_SETTINGS = {
    "META_APP_ID": "123456789",
    "META_APP_SECRET": "test-secret",
    "META_FACEBOOK_CONFIG_ID": "987654321",
    "META_FACEBOOK_REDIRECT_URI": "https://stockflow.example/api/storefront/social/facebook/callback/",
    "META_SOCIAL_RETURN_URL": "https://stockflow.example/app/online-shop",
    "META_GRAPH_API_VERSION": "v26.0",
}


def response(status, payload):
    item = Mock()
    item.status_code = status
    item.json.return_value = payload
    return item


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"], **META_SETTINGS)
class FacebookSocialConnectionTests(APITestCase):
    def setUp(self):
        test_listings.ShopListingApiTests.setUp(self)
        self.base = f"/api/businesses/{self.business.id}/storefront/social/"
        self.callback = "/api/storefront/social/facebook/callback/"

    def connect_state(self):
        result = self.client.get(self.base + "facebook/connect/")
        self.assertEqual(result.status_code, 200, result.data)
        query = parse_qs(urlparse(result.data["authorizeUrl"]).query)
        return result, query["state"][0]

    def test_connect_url_uses_business_configuration_without_scope(self):
        result, _ = self.connect_state()
        parsed = urlparse(result.data["authorizeUrl"])
        query = parse_qs(parsed.query)
        self.assertEqual(parsed.netloc, "www.facebook.com")
        self.assertEqual(query["client_id"], [META_SETTINGS["META_APP_ID"]])
        self.assertEqual(query["config_id"], [META_SETTINGS["META_FACEBOOK_CONFIG_ID"]])
        self.assertEqual(query["redirect_uri"], [META_SETTINGS["META_FACEBOOK_REDIRECT_URI"]])
        self.assertEqual(query["response_type"], ["code"])
        self.assertNotIn("scope", query)

    @patch("storefront.facebook_social.requests.get")
    def test_single_page_callback_stores_encrypted_connection(self, mocked_get):
        _, state = self.connect_state()
        mocked_get.side_effect = [
            response(200, {"access_token": "system-secret-token", "expires_in": 3600}),
            response(200, {"data": [{
                "id": "111",
                "name": "StockFlow Test Page",
                "tasks": ["CREATE_CONTENT", "MANAGE"],
                "access_token": "page-secret-token",
            }]}),
        ]
        self.client.force_authenticate(user=None)
        result = self.client.get(self.callback, {"code": "one-time-code", "state": state})
        self.assertEqual(result.status_code, 302)
        self.assertIn("social=facebook-connected", result["Location"])

        row = ProviderCredential.objects.get(
            business=self.business,
            category="social",
            provider="facebook",
        )
        self.assertNotIn("system-secret-token", row.encrypted_payload)
        self.assertNotIn("page-secret-token", row.encrypted_payload)

        _, payload = get_provider_credential(
            business=self.business,
            category="social",
            provider="facebook",
        )
        self.assertEqual(payload["page_id"], "111")
        self.assertEqual(payload["page_name"], "StockFlow Test Page")

        self.client.force_authenticate(self.owner)
        channels = self.client.get(self.base + "channels/")
        facebook = next(c for c in channels.data["channels"] if c["platform"] == "facebook")
        self.assertEqual(facebook["connectionStatus"], "connected")
        self.assertEqual(facebook["accountName"], "StockFlow Test Page")
        self.assertNotIn("page_access_token", facebook)


    @patch("storefront.facebook_social.requests.get")
    def test_linked_instagram_account_is_stored_and_exposed_without_token(self, mocked_get):
        _, state = self.connect_state()
        mocked_get.side_effect = [
            response(200, {"access_token": "system-secret-token", "expires_in": 3600}),
            response(200, {"data": [{
                "id": "111",
                "name": "StockFlow Test Shop",
                "tasks": ["CREATE_CONTENT", "MANAGE"],
                "access_token": "page-secret-token",
                "instagram_business_account": {"id": "17841400000000000"},
            }]}),
            response(200, {
                "id": "17841400000000000",
                "username": "stockflowghana",
            }),
        ]

        self.client.force_authenticate(user=None)
        result = self.client.get(self.callback, {"code": "one-time-code", "state": state})
        self.assertEqual(result.status_code, 302)
        self.assertIn("social=facebook-connected", result["Location"])

        _, payload = get_provider_credential(
            business=self.business,
            category="social",
            provider="facebook",
        )
        self.assertEqual(payload["instagram_account_id"], "17841400000000000")
        self.assertEqual(payload["instagram_username"], "stockflowghana")

        row = ProviderCredential.objects.get(
            business=self.business,
            category="social",
            provider="facebook",
        )
        self.assertNotIn("page-secret-token", row.encrypted_payload)

        self.client.force_authenticate(self.owner)
        channels = self.client.get(self.base + "channels/")
        instagram = next(c for c in channels.data["channels"] if c["platform"] == "instagram")
        self.assertEqual(instagram["connectionStatus"], "connected")
        self.assertEqual(instagram["accountName"], "stockflowghana")
        self.assertTrue(instagram["deliveryAvailable"])
        self.assertNotIn("page_access_token", instagram)

        page_lookup = mocked_get.call_args_list[1]
        self.assertIn(
            "instagram_business_account",
            page_lookup.kwargs["params"]["fields"],
        )

    @patch("storefront.facebook_social.requests.get")
    def test_multiple_pages_require_explicit_selection(self, mocked_get):
        _, state = self.connect_state()
        mocked_get.side_effect = [
            response(200, {"access_token": "system-secret-token", "expires_in": 3600}),
            response(200, {"data": [
                {"id": "111", "name": "Page One", "tasks": ["CREATE_CONTENT"], "access_token": "page-token-1"},
                {"id": "222", "name": "Page Two", "tasks": ["CREATE_CONTENT"], "access_token": "page-token-2"},
            ]}),
        ]
        self.client.force_authenticate(user=None)
        result = self.client.get(self.callback, {"code": "one-time-code", "state": state})
        self.assertEqual(result.status_code, 302)
        self.assertIn("social=facebook-select-page", result["Location"])

        self.client.force_authenticate(self.owner)
        channels = self.client.get(self.base + "channels/")
        facebook = next(c for c in channels.data["channels"] if c["platform"] == "facebook")
        self.assertEqual(facebook["connectionStatus"], "selection_required")
        self.assertEqual([p["id"] for p in facebook["availableAccounts"]], ["111", "222"])

        mocked_get.reset_mock()
        # reset_mock() clears call history but does not clear side_effect.
        # The callback already consumed the two-item side_effect iterator above,
        # so disable it before using return_value for the Page-selection lookup.
        mocked_get.side_effect = None
        mocked_get.return_value = response(200, {"data": [
            {"id": "111", "name": "Page One", "tasks": ["CREATE_CONTENT"], "access_token": "page-token-1"},
            {"id": "222", "name": "Page Two", "tasks": ["CREATE_CONTENT"], "access_token": "page-token-2"},
        ]})
        selected = self.client.post(
            self.base + "facebook/select-page/",
            {"pageId": "222"},
            format="json",
        )
        self.assertEqual(selected.status_code, 200, selected.data)
        self.assertEqual(selected.data["connectionStatus"], "connected")
        self.assertEqual(selected.data["accountName"], "Page Two")

    def test_invalid_state_does_not_create_connection(self):
        self.client.force_authenticate(user=None)
        result = self.client.get(self.callback, {"code": "code", "state": "invalid"})
        self.assertEqual(result.status_code, 302)
        self.assertFalse(ProviderCredential.objects.filter(
            business=self.business,
            category="social",
            provider="facebook",
        ).exists())

    @patch("storefront.facebook_social.requests.get")
    def test_disconnect_removes_connection(self, mocked_get):
        _, state = self.connect_state()
        mocked_get.side_effect = [
            response(200, {"access_token": "system-token", "expires_in": 3600}),
            response(200, {"data": [{
                "id": "111",
                "name": "Page One",
                "tasks": ["CREATE_CONTENT"],
                "access_token": "page-token",
            }]}),
        ]
        self.client.force_authenticate(user=None)
        self.client.get(self.callback, {"code": "code", "state": state})
        self.client.force_authenticate(self.owner)
        result = self.client.delete(self.base + "facebook/connection/")
        self.assertEqual(result.status_code, 204)
        self.assertFalse(ProviderCredential.objects.filter(
            business=self.business,
            category="social",
            provider="facebook",
        ).exists())
