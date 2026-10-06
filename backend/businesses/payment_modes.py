"""Keep test records out of live Paystack operations."""
from django.conf import settings
from .paystack_client import PaystackConfigurationError


def gateway_mode(client=None):
    key = getattr(client, "secret_key", None)
    if not isinstance(key, str):
        key = getattr(settings, "PAYMENT_GATEWAY_SECRET_KEY", "")
    key = key.strip()
    for mode in ("test", "live"):
        if key.startswith("sk_" + mode + "_"):
            return mode
    raise PaystackConfigurationError("A recognised Paystack test or live key is required.", code="paystack_mode_unknown")


def require_mode(record_mode, client=None):
    mode = gateway_mode(client)
    # Unclassified historical records may only run in the test environment.
    if record_mode != mode and not (not record_mode and mode == "test"):
        raise PaystackConfigurationError("This payment belongs to another or an unknown Paystack environment. Start a new payment in the current mode.", code="paystack_mode_mismatch")
    return mode


def require_response_mode(data, mode):
    domain = data.get("domain")
    if domain != mode:
        raise PaystackConfigurationError("Paystack returned an unexpected payment environment.", code="paystack_response_mode_mismatch")
