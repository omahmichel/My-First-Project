import os
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.settings import get_env_positive_int


class PaymentSettingsTests(SimpleTestCase):
    """Protects numeric Mobile Money payment configuration."""

    def test_missing_positive_integer_uses_default(self):
        # Local development remains usable without an optional override.
        with patch.dict(
            os.environ,
            {},
            clear=False,
        ):
            os.environ.pop("TEST_POSITIVE_INTEGER", None)

            value = get_env_positive_int(
                "TEST_POSITIVE_INTEGER",
                default=5,
            )

        self.assertEqual(value, 5)

    def test_positive_integer_override_is_accepted(self):
        # Deployment can safely adjust the reservation window.
        with patch.dict(
            os.environ,
            {"TEST_POSITIVE_INTEGER": "7"},
            clear=False,
        ):
            value = get_env_positive_int(
                "TEST_POSITIVE_INTEGER",
                default=5,
            )

        self.assertEqual(value, 7)

    def test_invalid_integer_override_is_rejected(self):
        # A typo must stop startup instead of silently weakening payments.
        with patch.dict(
            os.environ,
            {"TEST_POSITIVE_INTEGER": "five"},
            clear=False,
        ):
            with self.assertRaises(ImproperlyConfigured):
                get_env_positive_int(
                    "TEST_POSITIVE_INTEGER",
                    default=5,
                )

    def test_non_positive_integer_override_is_rejected(self):
        # Zero or negative reservation windows are unsafe.
        with patch.dict(
            os.environ,
            {"TEST_POSITIVE_INTEGER": "0"},
            clear=False,
        ):
            with self.assertRaises(ImproperlyConfigured):
                get_env_positive_int(
                    "TEST_POSITIVE_INTEGER",
                    default=5,
                )
