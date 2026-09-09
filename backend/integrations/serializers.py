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
# StockFlow safe data import v1.
from .models import DataImport


class DataImportPreviewRequestSerializer(serializers.Serializer):
    dataset = serializers.ChoiceField(choices=DataImport.Dataset.values)
    branchId = serializers.UUIDField(required=False, allow_null=True)
    file = serializers.FileField()

    def validate(self, attrs):
        if (
            attrs.get("dataset")
            in {DataImport.Dataset.PRODUCTS, DataImport.Dataset.BRANCH_INVENTORY}
            and not attrs.get("branchId")
        ):
            raise serializers.ValidationError(
                {"branchId": "Select the branch this import belongs to."}
            )
        return attrs


class DataImportApplyRequestSerializer(serializers.Serializer):
    previewToken = serializers.CharField(trim_whitespace=False)



# StockFlow outbound intelligence messaging v1.
from intelligence.models import AutomationEvent
from .models import MessageDelivery, MessagingPreference


class MessagingPreferenceSerializer(serializers.ModelSerializer):
    smsEnabled = serializers.BooleanField(source="sms_enabled", required=False)
    whatsappEnabled = serializers.BooleanField(
        source="whatsapp_enabled",
        required=False,
    )
    recipientPhone = serializers.CharField(
        source="recipient_phone",
        required=False,
        allow_blank=True,
        max_length=30,
    )
    minimumSeverity = serializers.ChoiceField(
        source="minimum_severity",
        choices=MessagingPreference.MinimumSeverity.values,
        required=False,
    )
    eventTypes = serializers.ListField(
        source="event_types",
        child=serializers.ChoiceField(choices=AutomationEvent.EventType.values),
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = MessagingPreference
        fields = (
            "smsEnabled",
            "whatsappEnabled",
            "recipientPhone",
            "minimumSeverity",
            "eventTypes",
            "updated_at",
        )
        read_only_fields = ("updated_at",)

    def validate(self, attrs):
        recipient = attrs.get(
            "recipient_phone",
            getattr(self.instance, "recipient_phone", ""),
        )
        sms_enabled = attrs.get(
            "sms_enabled",
            getattr(self.instance, "sms_enabled", False),
        )
        whatsapp_enabled = attrs.get(
            "whatsapp_enabled",
            getattr(self.instance, "whatsapp_enabled", False),
        )
        if whatsapp_enabled:
            from .messaging.whatsapp_live import whatsapp_configured

            business = getattr(self.instance, "business", None)
            if business is None or not whatsapp_configured(business):
                raise serializers.ValidationError(
                    {
                        "whatsappEnabled": (
                            "Configure this business's encrypted WhatsApp provider "
                            "credentials before enabling WhatsApp alerts."
                        )
                    }
                )
        if (sms_enabled or whatsapp_enabled) and not str(recipient or "").strip():
            raise serializers.ValidationError(
                {"recipientPhone": "Set a recipient phone number before enabling messaging."}
            )
        return attrs
