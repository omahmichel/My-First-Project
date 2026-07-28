import uuid

from django.db import transaction
from django.utils.text import slugify
from rest_framework import serializers

from .models import Business, BusinessMembership


class BusinessSerializer(serializers.ModelSerializer):
    # Exposes safe business details and the requesting user's role.

    owner_name = serializers.CharField(
        source="owner.full_name",
        read_only=True,
    )
    owner_email = serializers.EmailField(
        source="owner.email",
        read_only=True,
    )
    current_user_role = serializers.SerializerMethodField()
    active_team_members = serializers.SerializerMethodField()
    invoicePrefix = serializers.RegexField(
        source="invoice_prefix",
        regex=r"^[A-Za-z0-9-]+$",
        max_length=12,
        required=False,
        allow_blank=False,
        error_messages={
            "invalid": (
                "Use only letters, numbers and hyphens "
                "for the invoice prefix."
            ),
        },
    )
    receiptPrefix = serializers.RegexField(
        source="receipt_prefix",
        regex=r"^[A-Za-z0-9-]+$",
        max_length=12,
        required=False,
        allow_blank=False,
        error_messages={
            "invalid": (
                "Use only letters, numbers and hyphens "
                "for the receipt prefix."
            ),
        },
    )

    class Meta:
        model = Business
        fields = (
            "id",
            "name",
            "slug",
            "business_type",
            "phone",
            "email",
            "location",
            "invoicePrefix",
            "receiptPrefix",
            "status",
            "owner_name",
            "owner_email",
            "current_user_role",
            "active_team_members",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "slug",
            "owner_name",
            "owner_email",
            "current_user_role",
            "active_team_members",
            "created_at",
            "updated_at",
        )

    def validate_invoicePrefix(self, value):
        # Stores invoice prefixes consistently for document numbering.
        return value.strip().upper()

    def validate_receiptPrefix(self, value):
        # Stores receipt prefixes consistently for document numbering.
        return value.strip().upper()

    def get_current_user_role(self, obj):
        # Returns the owner's role directly or an active membership role.
        request = self.context.get("request")

        if not request or not request.user.is_authenticated:
            return None

        if obj.owner_id == request.user.id:
            return BusinessMembership.Role.OWNER

        membership = obj.memberships.filter(
            user=request.user,
            is_active=True,
        ).only("role").first()

        return membership.role if membership else None

    def get_active_team_members(self, obj):
        # Counts active memberships without exposing private team details.
        return obj.memberships.filter(is_active=True).count()

    def _generate_unique_slug(self, business_name):
        # Builds a readable slug and adds a suffix only when necessary.
        base_slug = slugify(business_name) or "business"

        if not Business.objects.filter(slug=base_slug).exists():
            return base_slug

        return f"{base_slug}-{uuid.uuid4().hex[:8]}"

    @transaction.atomic
    def create(self, validated_data):
        # Creates the workspace and its protected owner membership together.
        request = self.context["request"]

        business = Business.objects.create(
            owner=request.user,
            slug=self._generate_unique_slug(validated_data["name"]),
            **validated_data,
        )

        BusinessMembership.objects.create(
            business=business,
            user=request.user,
            role=BusinessMembership.Role.OWNER,
            is_active=True,
        )

        return business
