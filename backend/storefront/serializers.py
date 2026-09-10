from collections.abc import Mapping

from rest_framework import serializers


class StrictInputSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError({
                    'detail': 'The request contains unsupported fields.',
                })
        return super().to_internal_value(data)


class PublicOrderItemSerializer(StrictInputSerializer):
    productId = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, max_value=10000)


class PublicOrderCreateSerializer(StrictInputSerializer):
    idempotencyKey = serializers.UUIDField()
    customerName = serializers.CharField(max_length=180, trim_whitespace=True)
    customerPhone = serializers.RegexField(
        regex=r'^\+?[0-9][0-9 -]{7,23}$', max_length=30,
        error_messages={'invalid': 'Enter a valid contact phone number.'},
    )
    customerNote = serializers.CharField(
        max_length=1000, required=False, allow_blank=True,
        default='', trim_whitespace=True,
    )
    items = PublicOrderItemSerializer(many=True, allow_empty=False, max_length=50)

    def validate_customerName(self, value):
        return ' '.join(value.split())

    def validate_customerPhone(self, value):
        return value.replace(' ', '').replace('-', '')

    def validate_items(self, value):
        product_ids = [item['productId'] for item in value]
        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError(
                'Each product can appear only once in an order.'
            )
        return value
