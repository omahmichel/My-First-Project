import re
from datetime import timedelta

from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import PendingLoginChallenge, User


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="StockFlow <no-reply@stockflow.local>",
    LOGIN_OTP_EXPIRY_SECONDS=600,
    LOGIN_OTP_RESEND_COOLDOWN_SECONDS=60,
    LOGIN_OTP_MAX_ATTEMPTS=5,
)
class LoginOTPAPITests(APITestCase):
    # Verifies that password login cannot issue JWTs before email OTP succeeds.

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email="login.otp@stockflow.local",
            password="StrongPass123!",
            full_name="Login OTP User",
        )
        self.login_url = reverse("accounts:login")
        self.deliver_url = reverse("accounts:login-deliver")
        self.verify_url = reverse("accounts:login-verify")
        self.resend_url = reverse("accounts:login-resend")
        self.payload = {
            "email": self.user.email,
            "password": "StrongPass123!",
        }

    def tearDown(self):
        cache.clear()

    def start_challenge(self):
        response = self.client.post(
            self.login_url,
            self.payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        self.assertIn("challengeId", response.data)
        self.assertTrue(response.data["emailDeliveryRequired"])
        self.assertEqual(len(mail.outbox), 0)
        return response.data["challengeId"]

    def request_code(self):
        challenge_token = self.start_challenge()

        delivery_response = self.client.post(
            self.deliver_url,
            {"challengeId": challenge_token},
            format="json",
        )
        self.assertEqual(delivery_response.status_code, status.HTTP_200_OK)
        self.assertFalse(delivery_response.data["emailDeliveryRequired"])
        self.assertEqual(len(mail.outbox), 1)

        match = re.search(r"\b(\d{6})\b", mail.outbox[-1].body)
        self.assertIsNotNone(match)
        return challenge_token, match.group(1)

    def test_password_login_requires_second_factor_before_tokens(self):
        challenge_token = self.start_challenge()

        challenge = PendingLoginChallenge.objects.get(
            challenge_token=challenge_token,
        )
        self.assertEqual(challenge.user, self.user)
        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(challenge.otp_hash.startswith("pending$"))

    def test_wrong_password_returns_401_without_creating_challenge(self):
        response = self.client.post(
            self.login_url,
            {
                "email": self.user.email,
                "password": "WrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(PendingLoginChallenge.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_valid_code_returns_tokens_and_consumes_challenge(self):
        challenge_token, otp = self.request_code()

        response = self.client.post(
            self.verify_url,
            {"challengeId": challenge_token, "otp": otp},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["email"], self.user.email)
        self.assertFalse(PendingLoginChallenge.objects.exists())

    def test_wrong_code_increments_failed_attempts(self):
        challenge_token, issued_otp = self.request_code()
        wrong_otp = "000000" if issued_otp != "000000" else "000001"

        response = self.client.post(
            self.verify_url,
            {"challengeId": challenge_token, "otp": wrong_otp},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        challenge = PendingLoginChallenge.objects.get(
            challenge_token=challenge_token,
        )
        self.assertEqual(challenge.failed_attempts, 1)

    def test_five_wrong_codes_lock_the_active_code(self):
        challenge_token, issued_otp = self.request_code()
        wrong_otp = "000000" if issued_otp != "000000" else "000001"

        for _ in range(5):
            response = self.client.post(
                self.verify_url,
                {"challengeId": challenge_token, "otp": wrong_otp},
                format="json",
            )
            self.assertEqual(
                response.status_code,
                status.HTTP_400_BAD_REQUEST,
            )

        correct_response = self.client.post(
            self.verify_url,
            {"challengeId": challenge_token, "otp": issued_otp},
            format="json",
        )
        self.assertEqual(
            correct_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertNotIn("access", correct_response.data)

    def test_expired_code_is_rejected_and_challenge_removed(self):
        challenge_token, otp = self.request_code()
        PendingLoginChallenge.objects.filter(
            challenge_token=challenge_token,
        ).update(expires_at=timezone.now() - timedelta(seconds=1))

        response = self.client.post(
            self.verify_url,
            {"challengeId": challenge_token, "otp": otp},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(PendingLoginChallenge.objects.exists())

    def test_repeating_password_login_during_cooldown_reuses_challenge(self):
        challenge_token, _ = self.request_code()

        second_response = self.client.post(
            self.login_url,
            self.payload,
            format="json",
        )

        self.assertEqual(second_response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(second_response.data["challengeId"], challenge_token)
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn("access", second_response.data)

    def test_resend_replaces_code_after_cooldown(self):
        challenge_token, old_otp = self.request_code()
        PendingLoginChallenge.objects.filter(
            challenge_token=challenge_token,
        ).update(
            resend_available_at=timezone.now() - timedelta(seconds=1),
        )

        resend_response = self.client.post(
            self.resend_url,
            {"challengeId": challenge_token},
            format="json",
        )

        self.assertEqual(resend_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 2)

        match = re.search(r"\b(\d{6})\b", mail.outbox[-1].body)
        self.assertIsNotNone(match)
        new_otp = match.group(1)
        self.assertNotEqual(old_otp, new_otp)

        old_response = self.client.post(
            self.verify_url,
            {"challengeId": challenge_token, "otp": old_otp},
            format="json",
        )
        self.assertEqual(old_response.status_code, status.HTTP_400_BAD_REQUEST)

        valid_response = self.client.post(
            self.verify_url,
            {"challengeId": challenge_token, "otp": new_otp},
            format="json",
        )
        self.assertEqual(valid_response.status_code, status.HTTP_200_OK)
        self.assertIn("access", valid_response.data)
