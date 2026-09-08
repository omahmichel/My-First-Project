from decimal import Decimal

from rest_framework import serializers

from integrations.models import CommerceConnection, ExternalCommerceOrder


FORBIDDEN_SETTING_KEYS = {
    "access_token",
    "refresh_token",
    "client_secret",
    "password",
    "api_key",
    "api_secret",
    "consumer_key",
    "consumer_secret",
    "accessToken",
    "refreshToken",
    "clientSecret",
    "apiKey",
    "apiSecret",
    "consumerKey",
    "consumerSecret",
}


def _contains_forbidden_key(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key) in FORBIDDEN_SETTING_KEYS:
                return True
            if _contains_forbidden_key(item):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden_key(item) for item in value)
    return False


class CommerceConnectionWriteSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(
        choices=CommerceConnection.Provider.values
    )
    name = serializers.CharField(max_length=120)
    shopUrl = serializers.URLField(
        max_length=500,
        required=False,
        allow_blank=True,
    )
    settings = serializers.JSONField(required=False)

    def validate_settings(self, value):
        value = value or {}
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "Commerce connector settings must be an object."
            )
        if _contains_forbidden_key(value):
            raise serializers.ValidationError(
                "Provider secrets and OAuth credentials cannot be stored "
                "in commerce connector settings."
            )
        return value


class CommerceProductMappingSerializer(serializers.Serializer):
    externalProductId = serializers.CharField(max_length=180)
    productId = serializers.UUIDField()


class ExternalCommerceOrderItemSerializer(serializers.Serializer):
    externalItemId = serializers.CharField(max_length=180)
    externalProductId = serializers.CharField(
        max_length=180,
        required=False,
        allow_blank=True,
    )
    name = serializers.CharField(max_length=220)
    sku = serializers.CharField(
        max_length=120,
        required=False,
        allow_blank=True,
    )
    quantity = serializers.IntegerField(min_value=1)
    unitPrice = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.00"),
    )


class ExternalCommerceOrderStageSerializer(serializers.Serializer):
    connectionId = serializers.UUIDField()
    externalOrderId = serializers.CharField(max_length=180)
    externalOrderNumber = serializers.CharField(
        max_length=120,
        required=False,
        allow_blank=True,
    )
    paymentStatus = serializers.ChoiceField(
        choices=ExternalCommerceOrder.PaymentStatus.values,
        required=False,
        default=ExternalCommerceOrder.PaymentStatus.UNKNOWN,
    )
    currency = serializers.CharField(
        max_length=10,
        required=False,
        default="GHS",
    )
    customerName = serializers.CharField(
        max_length=180,
        required=False,
        allow_blank=True,
    )
    customerEmail = serializers.EmailField(
        required=False,
        allow_blank=True,
    )
    customerPhone = serializers.CharField(
        max_length=40,
        required=False,
        allow_blank=True,
    )
    subtotal = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.00"),
    )
    discount = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.00"),
        required=False,
        default=Decimal("0.00"),
    )
    shippingTotal = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.00"),
        required=False,
        default=Decimal("0.00"),
    )
    total = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.00"),
    )
    items = ExternalCommerceOrderItemSerializer(
        many=True,
        allow_empty=False,
    )

    def validate_items(self, items):
        ids = [item["externalItemId"] for item in items]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError(
                "Each external order item ID can appear only once."
            )
        return items

    def validate(self, attrs):
        calculated = (
            attrs["subtotal"]
            - attrs.get("discount", Decimal("0.00"))
            + attrs.get("shippingTotal", Decimal("0.00"))
        )
        if calculated != attrs["total"]:
            raise serializers.ValidationError(
                {
                    "total": (
                        "External order total must equal subtotal minus "
                        "discount plus shipping."
                    )
                }
            )
        return attrs
