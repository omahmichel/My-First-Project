from rest_framework import serializers

from .models import Branch


class BranchSerializer(serializers.ModelSerializer):
    businessId = serializers.UUIDField(source="business_id", read_only=True)
    isMain = serializers.BooleanField(source="is_main", read_only=True)
    isActive = serializers.BooleanField(source="is_active", read_only=True)
    assignedMemberIds = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = Branch
        fields = (
            "id", "businessId", "name", "code", "location", "phone",
            "isMain", "isActive", "assignedMemberIds", "createdAt", "updatedAt",
        )
        read_only_fields = ("id", "businessId", "isMain", "isActive")

    def get_assignedMemberIds(self, obj):
        return [
            str(value)
            for value in obj.access_assignments.filter(is_active=True).values_list(
                "membership_id", flat=True
            )
        ]


class BranchWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, trim_whitespace=True)
    code = serializers.RegexField(
        regex=r"^[A-Za-z0-9-]+$",
        max_length=40,
        trim_whitespace=True,
    )
    location = serializers.CharField(
        max_length=255, required=False, allow_blank=True, trim_whitespace=True
    )
    phone = serializers.CharField(
        max_length=30, required=False, allow_blank=True, trim_whitespace=True
    )

    def validate_name(self, value):
        value = " ".join(value.split()).strip()
        if not value:
            raise serializers.ValidationError("A branch name is required.")
        return value

    def validate_code(self, value):
        return value.strip().upper()


class BranchAccessUpdateSerializer(serializers.Serializer):
    membershipIds = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=True,
    )

    def validate_membershipIds(self, values):
        if len(values) != len(set(values)):
            raise serializers.ValidationError(
                "Each team membership can appear only once."
            )
        return values
