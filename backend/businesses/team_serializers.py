from rest_framework import serializers

from .models import BusinessMembership


class TeamMemberSerializer(serializers.ModelSerializer):
    # Matches the exact field names currently used by the React Team page.

    name = serializers.CharField(
        source="user.full_name",
        read_only=True,
    )
    email = serializers.EmailField(
        source="user.email",
        read_only=True,
    )
    phone = serializers.CharField(
        source="user.phone",
        read_only=True,
    )
    status = serializers.SerializerMethodField()
    lastActive = serializers.DateTimeField(
        source="last_active_at",
        read_only=True,
        allow_null=True,
    )
    joinedAt = serializers.DateTimeField(
        source="joined_at",
        read_only=True,
    )

    class Meta:
        model = BusinessMembership
        fields = (
            "id",
            "name",
            "email",
            "phone",
            "role",
            "status",
            "lastActive",
            "joinedAt",
        )
        read_only_fields = fields

    def get_status(self, obj):
        # Converts the membership flag into the frontend status label.
        return "active" if obj.is_active else "inactive"


class TeamMemberCreateSerializer(serializers.Serializer):
    # Validates the staff details submitted by the React modal.

    name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    phone = serializers.CharField(
        max_length=30,
        required=False,
        allow_blank=True,
    )
    role = serializers.ChoiceField(
        choices=(
            BusinessMembership.Role.MANAGER,
            BusinessMembership.Role.CASHIER,
            BusinessMembership.Role.INVENTORY_CLERK,
        ),
        default=BusinessMembership.Role.CASHIER,
    )

    def validate_name(self, value):
        # Prevents blank-looking names from being stored.
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "A full name is required."
            )

        return value

    def validate_email(self, value):
        # Normalizes email addresses before account lookup.
        return value.strip().lower()
