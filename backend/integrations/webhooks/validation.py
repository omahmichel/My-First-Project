import ipaddress
import socket
from urllib.parse import urlparse

from rest_framework.exceptions import ValidationError


def _is_blocked_ip(value):
    ip = ipaddress.ip_address(value)
    return any((
        ip.is_private,
        ip.is_loopback,
        ip.is_link_local,
        ip.is_multicast,
        ip.is_reserved,
        ip.is_unspecified,
    ))


def validate_webhook_url(value):
    parsed = urlparse(str(value))
    if parsed.scheme.lower() != "https":
        raise ValidationError("Webhook endpoints must use HTTPS.")
    if not parsed.hostname:
        raise ValidationError("Webhook endpoint hostname is required.")
    if parsed.username or parsed.password:
        raise ValidationError("Webhook URLs cannot contain embedded credentials.")

    host = parsed.hostname.lower().rstrip(".")
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        raise ValidationError("Webhook endpoints cannot target local hosts.")
    try:
        if _is_blocked_ip(host):
            raise ValidationError(
                "Webhook endpoints cannot target private or reserved IP addresses."
            )
    except ValueError:
        pass
    return str(value)


def assert_public_destination(value):
    validate_webhook_url(value)
    host = urlparse(str(value)).hostname
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("Webhook hostname could not be resolved.") from exc
    for info in addresses:
        address = info[4][0]
        if _is_blocked_ip(address):
            raise ValueError(
                "Webhook endpoint resolved to a private or reserved address."
            )
