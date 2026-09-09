import base64
import hashlib
import json
import os
import sys

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone

from .models import ProviderCredential


_ENV_NAME = "STOCKFLOW_INTEGRATION_DATA_KEY"


def _fernet_key():
    configured = os.environ.get(_ENV_NAME, "").strip()
    if configured:
        return configured.encode("ascii")

    # Match StockFlow's existing financial-secret development contract:
    # production requires a dedicated external key, while DEBUG/tests derive a
    # deterministic key from Django SECRET_KEY without committing a secret.
    if settings.DEBUG or "test" in sys.argv:
        digest = hashlib.sha256(
            ("stockflow-integration-data:" + str(settings.SECRET_KEY)).encode("utf-8")
        ).digest()
        return base64.urlsafe_b64encode(digest)

    raise ImproperlyConfigured(
        f"Set {_ENV_NAME} before storing or reading live provider credentials."
    )


def _fernet():
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:
        raise ImproperlyConfigured(
            "Install the cryptography package before using live integrations."
        ) from exc

    try:
        return Fernet(_fernet_key())
    except (TypeError, ValueError) as exc:
        raise ImproperlyConfigured(
            f"{_ENV_NAME} must be a valid Fernet key."
        ) from exc


def encrypt_provider_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("Provider credential payload must be an object.")
    raw = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return _fernet().encrypt(raw).decode("ascii")


def decrypt_provider_payload(ciphertext):
    try:
        from cryptography.fernet import InvalidToken
    except ImportError as exc:
        raise ImproperlyConfigured(
            "Install the cryptography package before using live integrations."
        ) from exc

    try:
        raw = _fernet().decrypt(str(ciphertext).encode("ascii")).decode("utf-8")
        payload = json.loads(raw)
    except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ImproperlyConfigured(
            "Provider credentials could not be decrypted with the configured key."
        ) from exc

    if not isinstance(payload, dict):
        raise ImproperlyConfigured(
            "The decrypted provider credential payload is invalid."
        )
    return payload


def credential_connection_key(connection=None):
    return str(connection.id) if connection is not None else "business"


def _credential_filter(*, business, category, provider, connection=None):
    return {
        "business": business,
        "category": str(category),
        "provider": str(provider),
        "connection_key": credential_connection_key(connection),
    }


def get_provider_credential(
    *,
    business,
    category,
    provider,
    connection=None,
    required=False,
):
    row = ProviderCredential.objects.filter(
        **_credential_filter(
            business=business,
            category=category,
            provider=provider,
            connection=connection,
        )
    ).first()
    if row is None:
        if required:
            raise ImproperlyConfigured(
                f"{provider} credentials are not configured for this business."
            )
        return None, None
    return row, decrypt_provider_payload(row.encrypted_payload)


def save_provider_credential(
    *,
    business,
    category,
    provider,
    payload,
    connection=None,
    created_by=None,
    access_expires_at=None,
    refresh_expires_at=None,
):
    lookup = _credential_filter(
        business=business,
        category=category,
        provider=provider,
        connection=connection,
    )
    encrypted = encrypt_provider_payload(payload)

    # Lock an existing credential row so a concurrent writer cannot interleave
    # partial token state. New rows remain protected by the database uniqueness
    # constraint.
    with transaction.atomic():
        row = ProviderCredential.objects.select_for_update().filter(**lookup).first()
        if row is None:
            row = ProviderCredential.objects.create(
                **lookup,
                encrypted_payload=encrypted,
                access_expires_at=access_expires_at,
                refresh_expires_at=refresh_expires_at,
                created_by=created_by,
            )
        else:
            row.encrypted_payload = encrypted
            row.access_expires_at = access_expires_at
            row.refresh_expires_at = refresh_expires_at
            if created_by is not None and row.created_by_id is None:
                row.created_by = created_by
            row.save(
                update_fields=(
                    "encrypted_payload",
                    "access_expires_at",
                    "refresh_expires_at",
                    "created_by",
                    "updated_at",
                )
            )
    return row


def rotate_provider_credential(
    *,
    row,
    expected_refresh_token,
    replacement_payload,
    access_expires_at,
    refresh_expires_at=None,
):
    """Atomically persist one rotating OAuth token pair.

    If another request already rotated the same refresh token, its newer stored
    pair wins and is returned instead of being overwritten by stale data.
    """
    with transaction.atomic():
        locked = ProviderCredential.objects.select_for_update().get(id=row.id)
        current = decrypt_provider_payload(locked.encrypted_payload)
        if current.get("refresh_token") != expected_refresh_token:
            return locked, current, False

        merged = {**current, **replacement_payload}
        locked.encrypted_payload = encrypt_provider_payload(merged)
        locked.access_expires_at = access_expires_at
        if refresh_expires_at is not None:
            locked.refresh_expires_at = refresh_expires_at
        locked.last_used_at = timezone.now()
        locked.save(
            update_fields=(
                "encrypted_payload",
                "access_expires_at",
                "refresh_expires_at",
                "last_used_at",
                "updated_at",
            )
        )
        return locked, merged, True


def touch_provider_credential(row):
    if row is None:
        return
    now = timezone.now()
    ProviderCredential.objects.filter(id=row.id).update(last_used_at=now)
    row.last_used_at = now


def delete_provider_credential(*, business, category, provider, connection=None):
    return ProviderCredential.objects.filter(
        **_credential_filter(
            business=business,
            category=category,
            provider=provider,
            connection=connection,
        )
    ).delete()
