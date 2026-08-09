from django.db import transaction
from rest_framework import serializers

from .models import BusinessPaymentAccount
from .payment_account_crypto import normalize_sensitive_number


class BusinessPaymentAccountSerializer(serializers.ModelSerializer):
    # Never returns the encrypted or plaintext receiving number.
    accountType = serializers.ChoiceField(
        source="account_type",
        choices=BusinessPaymentAccount.AccountType.choices,
    )
    displayName = serializers.CharField(
        source="display_name",
        max_length=120,
    )
    bankName = serializers.CharField(
        source="bank_name",
        max_length=120,
        required=False,
        allow_blank=True,
        default="",
    )
    accountName = serializers.CharField(
        source="account_name",
        max_length=150,
    )
    accountNumber = serializers.CharField(
        write_only=True,
        max_length=40,
        required=False,
        allow_blank=False,
    )
    maskedNumber = serializers.CharField(
        source="masked_number",
        read_only=True,
    )
    isActive = serializers.BooleanField(
        source="is_active",
        required=False,
    )
    isDefault = serializers.BooleanField(
        source="is_default",
        required=False,
    )
    createdAt = serializers.DateTimeField(
        source="created_at",
        read_only=True,
    )
    updatedAt = serializers.DateTimeField(
        source="updated_at",
        read_only=True,
    )

    class Meta:
        model = BusinessPaymentAccount
        fields = (
            "id",
            "accountType",
            "displayName",
            "bankName",
            "accountName",
            "network",
            "accountNumber",
            "maskedNumber",
            "isActive",
            "isDefault",
            "createdAt",
            "updatedAt",
        )
        read_only_fields = ("id",)

    def validate_accountNumber(self, value):
        # Normalizes before encryption and rejects malformed identifiers.
        try:
            return normalize_sensitive_number(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def validate(self, attrs):
        # Applies account-type requirements without exposing the number.
        attrs = super().validate(attrs)

        account_type = attrs.get(
            "account_type",
            getattr(self.instance, "account_type", ""),
        )
        bank_name = str(
            attrs.get(
                "bank_name",
                getattr(self.instance, "bank_name", ""),
            )
        ).strip()
        account_name = str(
            attrs.get(
                "account_name",
                getattr(self.instance, "account_name", ""),
            )
        ).strip()
        network = str(
            attrs.get(
                "network",
                getattr(self.instance, "network", ""),
            )
        ).strip()

        if self.instance is None and not attrs.get("accountNumber"):
            raise serializers.ValidationError(
                {
                    "accountNumber": (
                        "Enter the receiving account or wallet number."
                    )
                }
            )

        if not account_name:
            raise serializers.ValidationError(
                {"accountName": "Enter the receiving account name."}
            )

        if account_type == BusinessPaymentAccount.AccountType.BANK:
            if not bank_name:
                raise serializers.ValidationError(
                    {"bankName": "Enter the receiving bank name."}
                )
            attrs["network"] = ""
        elif (
            account_type
            == BusinessPaymentAccount.AccountType.MOBILE_MONEY
        ):
            if not network:
                raise serializers.ValidationError(
                    {"network": "Select the receiving Mobile Money network."}
                )
            attrs["bank_name"] = ""

        attrs["display_name"] = str(
            attrs.get(
                "display_name",
                getattr(self.instance, "display_name", ""),
            )
        ).strip()
        attrs["account_name"] = account_name
        attrs["bank_name"] = bank_name if bank_name else ""
        attrs["network"] = network if network else ""

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        # Creates an encrypted account inside the already-authorized business.
        account_number = validated_data.pop("accountNumber")
        business = validated_data["business"]

        if validated_data.get("is_default"):
            BusinessPaymentAccount.objects.filter(
                business=business,
                is_active=True,
                is_default=True,
            ).update(is_default=False)

        account = BusinessPaymentAccount(**validated_data)
        account.set_account_number(account_number)
        account.save()
        return account

    @transaction.atomic
    def update(self, instance, validated_data):
        # Updates metadata while preserving encrypted account data by default.
        account_number = validated_data.pop("accountNumber", None)

        for field, value in validated_data.items():
            setattr(instance, field, value)

        if not instance.is_active:
            instance.is_default = False

        if instance.is_default:
            BusinessPaymentAccount.objects.filter(
                business=instance.business,
                is_active=True,
                is_default=True,
            ).exclude(pk=instance.pk).update(is_default=False)

        if account_number is not None:
            instance.set_account_number(account_number)

        instance.save()
        return instance
