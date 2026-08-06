from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User


TEST_REST_FRAMEWORK = {
    **settings.REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {
        **settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
        "auth_login": "2/min",
        "auth_register": "2/min",
        "auth_register_verify": "2/min",
        "auth_register_resend": "2/min",
        "auth_refresh": "2/min",
        "auth_logout": "2/min",
    },
}


@override_settings(
    REST_FRAMEWORK=TEST_REST_FRAMEWORK,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class AuthenticationThrottleTests(APITestCase):
    # Uses very small limits so security throttles can be tested quickly.

    def setUp(self):
        cache.clear()

        # DRF caches throttle rates on the throttle class at import time.
        # This patch makes each test use the smaller rates defined above.
        throttle_rates_patcher = patch.object(
            ScopedRateThrottle,
            "THROTTLE_RATES",
            TEST_REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
        )
        throttle_rates_patcher.start()
        self.addCleanup(throttle_rates_patcher.stop)

        self.user = User.objects.create_user(
            email="security.tests@stockflow.local",
            password="StrongPass123!",
            full_name="Security Test User",
        )

        self.login_url = reverse("accounts:login")
        self.register_url = reverse("accounts:register")
        self.refresh_url = reverse("accounts:refresh")
        self.logout_url = reverse("accounts:logout")

    def tearDown(self):
        cache.clear()

    def test_login_is_throttled_after_repeated_attempts(self):
        # Repeated login attempts from one client must eventually return 429.
        payload = {
            "email": self.user.email,
            "password": "WrongPassword123!",
        }

        first_response = self.client.post(
            self.login_url,
            payload,
            format="json",
        )
        second_response = self.client.post(
            self.login_url,
            payload,
            format="json",
        )
        throttled_response = self.client.post(
            self.login_url,
            payload,
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(second_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            throttled_response.status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )

    def test_registration_is_throttled_after_repeated_attempts(self):
        # Automated account creation must be limited per anonymous client.
        def payload(number):
            return {
                "email": f"registration{number}@stockflow.local",
                "full_name": f"Registration User {number}",
                "phone": "",
                "password": "StrongPass123!",
                "password_confirm": "StrongPass123!",
            }

        first_response = self.client.post(
            self.register_url,
            payload(1),
            format="json",
        )
        second_response = self.client.post(
            self.register_url,
            payload(2),
            format="json",
        )
        throttled_response = self.client.post(
            self.register_url,
            payload(3),
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(second_response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(
            throttled_response.status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )

    def test_refresh_is_throttled_after_repeated_attempts(self):
        # Repeated refresh requests must be limited even with invalid tokens.
        invalid_payload = {"refresh": "invalid-refresh-token"}

        first_response = self.client.post(
            self.refresh_url,
            invalid_payload,
            format="json",
        )
        second_response = self.client.post(
            self.refresh_url,
            invalid_payload,
            format="json",
        )
        throttled_response = self.client.post(
            self.refresh_url,
            invalid_payload,
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(second_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            throttled_response.status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )

    def test_logout_is_throttled_for_authenticated_user(self):
        # One authenticated account must not submit unlimited logout requests.
        self.client.force_authenticate(user=self.user)

        first_response = self.client.post(
            self.logout_url,
            {"refresh": str(RefreshToken.for_user(self.user))},
            format="json",
        )
        second_response = self.client.post(
            self.logout_url,
            {"refresh": str(RefreshToken.for_user(self.user))},
            format="json",
        )
        throttled_response = self.client.post(
            self.logout_url,
            {"refresh": str(RefreshToken.for_user(self.user))},
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            throttled_response.status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )
