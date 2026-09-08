import hashlib
import hmac
import secrets

from django.conf import settings


def hash_api_key(raw_key):
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        str(raw_key).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def generate_api_key_material():
    lookup = secrets.token_hex(6)
    secret = secrets.token_urlsafe(32)
    key_prefix = f"sf_live_{lookup}"
    raw_key = f"{key_prefix}.{secret}"
    return key_prefix, raw_key, hash_api_key(raw_key)


def verify_api_key(raw_key, expected_hash):
    return hmac.compare_digest(
        hash_api_key(raw_key),
        str(expected_hash or ""),
    )
