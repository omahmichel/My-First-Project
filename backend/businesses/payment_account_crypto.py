import base64
import hashlib
import os
import re
import sys

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


_ENV_NAME = "STOCKFLOW_FINANCIAL_DATA_KEY"


def normalize_sensitive_number(value):
    # Removes presentation separators before encrypted storage.
    normalized = str(value or "").strip().replace(" ", "").replace("-", "")

    if not re.fullmatch(r"\+?[0-9]{8,34}", normalized):
        raise ValueError(
            "Enter a valid account or wallet number using digits only."
        )

    return normalized


def _fernet_key():
    # Production uses a dedicated encryption key kept outside the database.
    configured = os.environ.get(_ENV_NAME, "").strip()

    if configured:
        return configured.encode("ascii")

    # Local development and automated tests remain usable without storing
    # a production financial key in source control.
    if settings.DEBUG or "test" in sys.argv:
        digest = hashlib.sha256(
            (
                "stockflow-financial-data:"
                + str(settings.SECRET_KEY)
            ).encode("utf-8")
        ).digest()
        return base64.urlsafe_b64encode(digest)

    raise ImproperlyConfigured(
        f"Set {_ENV_NAME} before storing or reading financial account data."
    )


def _fernet():
    # Loads cryptography lazily so configuration failures are explicit.
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:
        raise ImproperlyConfigured(
            "Install the cryptography package before using payment accounts."
        ) from exc

    try:
        return Fernet(_fernet_key())
    except (TypeError, ValueError) as exc:
        raise ImproperlyConfigured(
            f"{_ENV_NAME} must be a valid Fernet key."
        ) from exc


def encrypt_sensitive_value(value):
    # Returns authenticated ciphertext; plaintext is never stored.
    normalized = normalize_sensitive_number(value)
    return _fernet().encrypt(normalized.encode("utf-8")).decode("ascii")


def decrypt_sensitive_value(value):
    # Decrypts only when internal business logic genuinely needs the value.
    try:
        from cryptography.fernet import InvalidToken
    except ImportError as exc:
        raise ImproperlyConfigured(
            "Install the cryptography package before using payment accounts."
        ) from exc

    try:
        return _fernet().decrypt(
            str(value).encode("ascii")
        ).decode("utf-8")
    except InvalidToken as exc:
        raise ImproperlyConfigured(
            "Financial account data could not be decrypted with the "
            "configured key."
        ) from exc
