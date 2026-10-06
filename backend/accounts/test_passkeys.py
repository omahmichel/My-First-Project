from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


@override_settings(
    WEBAUTHN_RP_ID="localhost",
    WEBAUTHN_ORIGINS=["http://localhost:5173"],
)
class PasskeyAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com",
            password="StrongPass123!",
            full_name="Owner",
        )

    def authenticate(self):
        token = RefreshToken.for_user(self.user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_registration_options_require_authenticated_user(self):
        response = self.client.post("/api/auth/passkeys/register/options/", {}, format="json")
        self.assertEqual(response.status_code, 401)

    @patch("accounts.passkey_views.begin_passkey_registration")
    def test_authenticated_user_can_start_registration(self, begin):
        begin.return_value = ("challenge-token", {"challenge": "abc"})
        self.authenticate()
        response = self.client.post("/api/auth/passkeys/register/options/", {}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["challengeId"], "challenge-token")

    def test_login_options_reject_account_without_registered_passkey(self):
        response = self.client.post(
            "/api/auth/passkeys/login/options/",
            {"email": self.user.email},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)

    @patch("accounts.passkey_views.begin_passkey_authentication")
    def test_login_options_endpoint_returns_browser_options(self, begin):
        begin.return_value = ("login-challenge", {"challenge": "abc"})
        response = self.client.post(
            "/api/auth/passkeys/login/options/",
            {"email": self.user.email},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["challengeId"], "login-challenge")

    @patch("accounts.passkey_views.finish_passkey_authentication")
    def test_verified_passkey_login_returns_existing_token_shape(self, finish):
        finish.return_value = {
            "message": "Biometric sign-in verified successfully.",
            "user": {"id": self.user.id, "email": self.user.email},
            "access": "access-token",
            "refresh": "refresh-token",
        }
        response = self.client.post(
            "/api/auth/passkeys/login/verify/",
            {
                "challengeId": "login-challenge",
                "credential": {"id": "credential", "rawId": "credential"},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["access"], "access-token")
        self.assertEqual(response.data["refresh"], "refresh-token")
