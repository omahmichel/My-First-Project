import math
import uuid

from django.db import transaction
from django.utils import timezone
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
    isTrialActive = serializers.BooleanField(
        source="is_trial_active",
        read_only=True,
    )
    hasActiveSubscription = serializers.BooleanField(
        source="has_active_subscription",
        read_only=True,
    )
    subscriptionReminderDue = serializers.BooleanField(
        source="subscription_reminder_due",
        read_only=True,
    )
    hasSystemAccess = serializers.BooleanField(
        source="has_system_access",
        read_only=True,
    )
    trialDaysRemaining = serializers.SerializerMethodField()
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

    vatRegistered = serializers.BooleanField(
        source="vat_registered",
        required=False,
    )
    vatRegistrationNumber = serializers.CharField(
        source="vat_registration_number",
        max_length=80,
        required=False,
        allow_blank=True,
    )
    dealsIn = serializers.ListField(
        source="deals_in",
        child=serializers.CharField(
            max_length=60,
            trim_whitespace=True,
        ),
        required=False,
        allow_empty=True,
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
            "dealsIn",
            "vatRegistered",
            "vatRegistrationNumber",
            "invoicePrefix",
            "receiptPrefix",
            "status",
            "owner_name",
            "owner_email",
            "current_user_role",
            "active_team_members",
            "trial_started_at",
            "trial_ends_at",
            "trialDaysRemaining",
            "subscription_status",
            "subscription_started_at",
            "subscription_ends_at",
            "isTrialActive",
            "hasActiveSubscription",
            "subscriptionReminderDue",
            "hasSystemAccess",
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
            "trial_started_at",
            "trial_ends_at",
            "trialDaysRemaining",
            "subscription_status",
            "subscription_started_at",
            "subscription_ends_at",
            "isTrialActive",
            "hasActiveSubscription",
            "subscriptionReminderDue",
            "hasSystemAccess",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        # Requires a VAT number only when this business enables VAT.
        attrs = super().validate(attrs)

        current_registered = bool(
            getattr(self.instance, "vat_registered", False)
        )
        current_number = str(
            getattr(self.instance, "vat_registration_number", "")
        ).strip()

        vat_registered = attrs.get(
            "vat_registered",
            current_registered,
        )
        vat_number = str(
            attrs.get(
                "vat_registration_number",
                current_number,
            )
        ).strip()

        if vat_registered and not vat_number:
            raise serializers.ValidationError(
                {
                    "vatRegistrationNumber": (
                        "Enter the VAT registration number "
                        "when VAT is enabled."
                    ),
                }
            )

        return attrs

    def validate_dealsIn(self, value):
        # Keeps dealer categories concise, unique, and safe for documents.
        normalized = []
        seen = set()

        for raw_item in value:
            item = " ".join(str(raw_item).split()).strip()
            if not item:
                continue

            key = item.casefold()
            if key in seen:
                continue

            seen.add(key)
            normalized.append(item)

        if len(normalized) > 10:
            raise serializers.ValidationError(
                "Select up to 10 items your business deals in."
            )

        return normalized

    def validate_vatRegistrationNumber(self, value):
        # Stores the VAT registration number without extra spaces.
        return value.strip()

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

    def get_trialDaysRemaining(self, obj):
        # Returns whole calendar-style days without exposing negative values.
        remaining_seconds = (
            obj.trial_ends_at - timezone.now()
        ).total_seconds()
        return max(0, math.ceil(remaining_seconds / 86400))

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
