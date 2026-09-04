from urllib.parse import parse_qs, urlparse

from django.core import mail
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .password_reset_views import PASSWORD_RESET_RESPONSE


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="StockFlow <no-reply@stockflow.local>",
    FRONTEND_BASE_URL="http://127.0.0.1:5173",
)
class PasswordResetAPITests(APITestCase):
    # Verifies enumeration safety, signed links, and session invalidation.

    def setUp(self):
        self.user = User.objects.create_user(
            email="reset.tests@stockflow.local",
            password="OriginalPass123!",
            full_name="Reset Test User",
        )
        self.request_url = reverse("accounts:password-reset-request")
        self.confirm_url = reverse("accounts:password-reset-confirm")
        self.login_url = reverse("accounts:login")
        self.refresh_url = reverse("accounts:refresh")
        self.current_user_url = reverse("accounts:current-user")

    def request_reset_payload(self):
        response = self.client.post(
            self.request_url,
            {"email": self.user.email},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"message": PASSWORD_RESET_RESPONSE})
        self.assertEqual(len(mail.outbox), 1)

        reset_link = next(
            line
            for line in mail.outbox[0].body.splitlines()
            if line.startswith("http://127.0.0.1:5173/reset-password")
        )
        query = parse_qs(urlparse(reset_link).query)
        return {"uid": query["uid"][0], "token": query["token"][0]}

    def test_request_sends_reset_link_for_active_account(self):
        payload = self.request_reset_payload()
        self.assertTrue(payload["uid"])
        self.assertTrue(payload["token"])
        self.assertEqual(mail.outbox[0].to, [self.user.email])

    def test_request_does_not_reveal_unknown_email(self):
        response = self.client.post(
            self.request_url,
            {"email": "unknown@stockflow.local"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"message": PASSWORD_RESET_RESPONSE})
        self.assertEqual(len(mail.outbox), 0)

    def test_valid_link_changes_password_and_invalidates_sessions(self):
        old_refresh = RefreshToken.for_user(self.user)
        old_access = str(old_refresh.access_token)
        payload = self.request_reset_payload()

        response = self.client.post(
            self.confirm_url,
            {
                **payload,
                "password": "ReplacementPass456!",
                "password_confirm": "ReplacementPass456!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertFalse(self.user.check_password("OriginalPass123!"))
        self.assertTrue(self.user.check_password("ReplacementPass456!"))

        login_response = self.client.post(
            self.login_url,
            {
                "email": self.user.email,
                "password": "ReplacementPass456!",
            },
            format="json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn("challengeId", login_response.data)
        self.assertNotIn("access", login_response.data)
        self.assertNotIn("refresh", login_response.data)

        refresh_response = self.client.post(
            self.refresh_url,
            {"refresh": str(old_refresh)},
            format="json",
        )
        self.assertEqual(
            refresh_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        current_user_response = self.client.get(
            self.current_user_url,
            HTTP_AUTHORIZATION=f"Bearer {old_access}",
        )
        self.assertEqual(
            current_user_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_invalid_link_does_not_change_password(self):
        response = self.client.post(
            self.confirm_url,
            {
                "uid": "invalid",
                "token": "invalid",
                "password": "ReplacementPass456!",
                "password_confirm": "ReplacementPass456!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("OriginalPass123!"))

    def test_confirmation_requires_matching_passwords(self):
        payload = self.request_reset_payload()
        response = self.client.post(
            self.confirm_url,
            {
                **payload,
                "password": "ReplacementPass456!",
                "password_confirm": "DifferentPass456!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("OriginalPass123!"))
