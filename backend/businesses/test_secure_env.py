"""Tests the StockFlow encrypted environment loader without real secrets."""

import os
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from config.secure_env import (
    load_backend_environment,
    parse_environment_text,
)


class SecureEnvironmentLoaderTests(SimpleTestCase):
    """Validates safe parsing and environment precedence."""

    def test_parse_environment_text_reads_quoted_and_empty_values(self):
        values = parse_environment_text(
            'DJANGO_SECRET_KEY="local secret"\n'
            "PAYMENT_GATEWAY=paystack\n"
            "PAYMENT_GATEWAY_SECRET_KEY=\n"
        )

        self.assertEqual(values["DJANGO_SECRET_KEY"], "local secret")
        self.assertEqual(values["PAYMENT_GATEWAY"], "paystack")
        self.assertEqual(values["PAYMENT_GATEWAY_SECRET_KEY"], "")

    def test_encrypted_values_load_without_overriding_host_variables(self):
        with tempfile.TemporaryDirectory() as directory:
            base_dir = Path(directory)
            (base_dir / ".env.enc").write_bytes(b"encrypted-placeholder")

            with (
                mock.patch.dict(
                    os.environ,
                    {
                        "PAYMENT_GATEWAY": "host-gateway",
                    },
                    clear=False,
                ),
                mock.patch(
                    "config.secure_env.decrypt_environment_file",
                    return_value=(
                        "PAYMENT_GATEWAY=paystack\n"
                        "PAYMENT_CALLBACK_URL=http://localhost:5173/app/subscription\n"
                    ),
                ),
            ):
                source = load_backend_environment(base_dir)

                self.assertEqual(source, "encrypted")
                self.assertEqual(
                    os.environ["PAYMENT_GATEWAY"],
                    "host-gateway",
                )
                self.assertEqual(
                    os.environ["PAYMENT_CALLBACK_URL"],
                    "http://localhost:5173/app/subscription",
                )

                os.environ.pop("PAYMENT_CALLBACK_URL", None)

    def test_missing_local_files_use_host_environment_only(self):
        with tempfile.TemporaryDirectory() as directory:
            source = load_backend_environment(Path(directory))

        self.assertEqual(source, "environment")
