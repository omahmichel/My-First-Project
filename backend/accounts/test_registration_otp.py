import re
from datetime import timedelta

from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import PendingRegistration, User


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="StockFlow <no-reply@stockflow.local>",
    REGISTRATION_OTP_EXPIRY_SECONDS=600,
    REGISTRATION_OTP_RESEND_COOLDOWN_SECONDS=60,
    REGISTRATION_OTP_MAX_ATTEMPTS=5,
)
class RegistrationOTPAPITests(APITestCase):
    # Verifies secure pending registration, OTP checks, and JWT creation.

    def setUp(self):
        # Prevents one test's scoped throttle counters affecting another test.
        cache.clear()

        self.request_url = reverse("accounts:register")
        self.verify_url = reverse("accounts:register-verify")
        self.resend_url = reverse("accounts:register-resend")
        self.payload = {
            "email": "otp.tests@stockflow.local",
            "full_name": "OTP Test User",
            "phone": "0200000000",
            "password": "StrongPass123!",
            "password_confirm": "StrongPass123!",
        }

    def tearDown(self):
        # Leaves no authentication throttle counters behind after each test.
        cache.clear()

    def request_code(self):
        response = self.client.post(
            self.request_url,
            self.payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_202_ACCEPTED,
        )
        self.assertEqual(len(mail.outbox), 1)

        match = re.search(r"\b(\d{6})\b", mail.outbox[-1].body)
        self.assertIsNotNone(match)
        return match.group(1)

    def test_registration_request_sends_code_without_creating_user(self):
        self.request_code()

        self.assertFalse(
            User.objects.filter(email=self.payload["email"]).exists()
        )
        pending = PendingRegistration.objects.get(
            email=self.payload["email"],
        )
        self.assertNotEqual(
            pending.password_hash,
            self.payload["password"],
        )
        self.assertNotEqual(pending.otp_hash, mail.outbox[-1].body)

    def test_valid_code_creates_account_and_returns_tokens(self):
        otp = self.request_code()

        response = self.client.post(
            self.verify_url,
            {
                "email": self.payload["email"],
                "otp": otp,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

        user = User.objects.get(email=self.payload["email"])
        self.assertTrue(
            user.check_password(self.payload["password"])
        )
        self.assertFalse(
            PendingRegistration.objects.filter(
                email=self.payload["email"],
            ).exists()
        )

    def test_wrong_code_increments_failed_attempts(self):
        issued_otp = self.request_code()
        wrong_otp = "000000" if issued_otp != "000000" else "000001"

        response = self.client.post(
            self.verify_url,
            {
                "email": self.payload["email"],
                "otp": wrong_otp,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        pending = PendingRegistration.objects.get(
            email=self.payload["email"],
        )
        self.assertEqual(pending.failed_attempts, 1)
        self.assertFalse(
            User.objects.filter(email=self.payload["email"]).exists()
        )

    def test_five_wrong_codes_lock_the_active_code(self):
        issued_otp = self.request_code()
        wrong_otp = "000000" if issued_otp != "000000" else "000001"

        for attempt_number in range(5):
            response = self.client.post(
                self.verify_url,
                {
                    "email": self.payload["email"],
                    "otp": wrong_otp,
                },
                format="json",
            )

            self.assertEqual(
                response.status_code,
                status.HTTP_400_BAD_REQUEST,
            )

        pending = PendingRegistration.objects.get(
            email=self.payload["email"],
        )
        self.assertEqual(pending.failed_attempts, 5)

        correct_response = self.client.post(
            self.verify_url,
            {
                "email": self.payload["email"],
                "otp": issued_otp,
            },
            format="json",
        )

        self.assertEqual(
            correct_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertFalse(
            User.objects.filter(email=self.payload["email"]).exists()
        )

    def test_expired_code_is_rejected_and_pending_record_removed(self):
        otp = self.request_code()
        PendingRegistration.objects.filter(
            email=self.payload["email"],
        ).update(
            expires_at=timezone.now() - timedelta(seconds=1),
        )

        response = self.client.post(
            self.verify_url,
            {
                "email": self.payload["email"],
                "otp": otp,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertFalse(
            PendingRegistration.objects.filter(
                email=self.payload["email"],
            ).exists()
        )

    def test_resend_requires_cooldown(self):
        self.request_code()

        response = self.client.post(
            self.resend_url,
            {"email": self.payload["email"]},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_replaces_code_after_cooldown(self):
        old_otp = self.request_code()
        PendingRegistration.objects.filter(
            email=self.payload["email"],
        ).update(
            resend_available_at=timezone.now()
            - timedelta(seconds=1),
        )

        resend_response = self.client.post(
            self.resend_url,
            {"email": self.payload["email"]},
            format="json",
        )

        self.assertEqual(
            resend_response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(len(mail.outbox), 2)

        match = re.search(r"\b(\d{6})\b", mail.outbox[-1].body)
        self.assertIsNotNone(match)
        new_otp = match.group(1)
        self.assertNotEqual(old_otp, new_otp)

        old_response = self.client.post(
            self.verify_url,
            {
                "email": self.payload["email"],
                "otp": old_otp,
            },
            format="json",
        )
        self.assertEqual(
            old_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        valid_response = self.client.post(
            self.verify_url,
            {
                "email": self.payload["email"],
                "otp": new_otp,
            },
            format="json",
        )
        self.assertEqual(
            valid_response.status_code,
            status.HTTP_201_CREATED,
        )
