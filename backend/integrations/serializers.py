from rest_framework import serializers


class AccountingExportQuerySerializer(serializers.Serializer):
    dateFrom = serializers.DateField(required=False)
    dateTo = serializers.DateField(required=False)

    def validate(self, attrs):
        date_from = attrs.get("dateFrom")
        date_to = attrs.get("dateTo")
        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError(
                {"dateTo": "The end date cannot be earlier than the start date."}
            )
        return attrs
