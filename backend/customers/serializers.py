from rest_framework import serializers

from .models import Customer


class CustomerSerializer(serializers.ModelSerializer):
    # Uses the camelCase field names already expected by the React frontend.

    businessId = serializers.UUIDField(
        source="business_id",
        read_only=True,
    )
    businessType = serializers.CharField(
        source="business.business_type",
        read_only=True,
    )
    outstandingBalance = serializers.DecimalField(
        source="outstanding_balance",
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )
    totalPurchases = serializers.DecimalField(
        source="total_purchases",
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )
    isActive = serializers.BooleanField(
        source="is_active",
        read_only=True,
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
        model = Customer
        fields = (
            "id",
            "businessId",
            "businessType",
            "name",
            "phone",
            "email",
            "address",
            "outstandingBalance",
            "totalPurchases",
            "isActive",
            "createdAt",
            "updatedAt",
        )
        read_only_fields = (
            "id",
            "businessId",
            "businessType",
            "outstandingBalance",
            "totalPurchases",
            "isActive",
            "createdAt",
            "updatedAt",
        )
        extra_kwargs = {
            "name": {
                "max_length": 180,
                "required": True,
                "allow_blank": False,
            },
            "phone": {
                "max_length": 30,
                "required": True,
                "allow_blank": False,
            },
            "email": {
                "required": False,
                "allow_blank": True,
            },
            "address": {
                "required": False,
                "allow_blank": True,
            },
        }

    def validate_name(self, value):
        # Removes accidental spaces while preserving the customer's real name.
        cleaned_value = value.strip()

        if not cleaned_value:
            raise serializers.ValidationError(
                "Customer name is required."
            )

        return cleaned_value

    def validate_phone(self, value):
        # Removes accidental spaces while keeping local and international formats.
        cleaned_value = value.strip()

        if not cleaned_value:
            raise serializers.ValidationError(
                "Phone number is required."
            )

        return cleaned_value

    def validate_email(self, value):
        # Normalizes optional email addresses for consistent searching.
        return value.strip().lower()

    def validate_address(self, value):
        # Removes leading and trailing spaces from the optional address.
        return value.strip()

    def create(self, validated_data):
        # The business and creator always come from the authenticated request.
        return Customer.objects.create(
            business=self.context["business"],
            created_by=self.context["request"].user,
            **validated_data,
        )
