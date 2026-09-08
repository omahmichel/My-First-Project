from rest_framework import serializers

from .models import AccountingConnection
from .webhooks.validation import validate_webhook_url

API_SCOPES = (
    "sales:read",
    "inventory:read",
    "purchases:read",
    "customers:read",
    "suppliers:read",
)

WEBHOOK_EVENTS = (
    "integration.test",
    "sale.completed",
    "sale.partially_paid",
    "payment.received",
    "customer.created",
    "customer.updated",
    "supplier.created",
    "supplier.updated",
    "product.created",
    "product.updated",
    "inventory.updated",
)


class ApiCredentialCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    scopes = serializers.ListField(
        child=serializers.ChoiceField(choices=API_SCOPES),
        allow_empty=False,
    )
    expiresAt = serializers.DateTimeField(required=False, allow_null=True)

    def validate_scopes(self, value):
        return list(dict.fromkeys(value))


class WebhookEndpointWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    url = serializers.URLField(max_length=500)
    events = serializers.ListField(
        child=serializers.ChoiceField(choices=WEBHOOK_EVENTS),
        allow_empty=False,
    )
    isActive = serializers.BooleanField(required=False, default=True)

    def validate_url(self, value):
        return validate_webhook_url(value)

    def validate_events(self, value):
        return list(dict.fromkeys(value))


class AccountingConnectionWriteSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=AccountingConnection.Provider.values)
    name = serializers.CharField(max_length=120)
    settings = serializers.JSONField(required=False)

    def validate_settings(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("Connector settings must be an object.")
        forbidden = {
            "access_token", "refresh_token", "client_secret", "password",
            "accessToken", "refreshToken", "clientSecret",
        }
        if forbidden.intersection(value):
            raise serializers.ValidationError(
                "Secrets and OAuth tokens cannot be stored in connector settings."
            )
        return value
