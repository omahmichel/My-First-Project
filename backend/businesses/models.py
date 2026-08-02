from datetime import timedelta
from decimal import Decimal
import uuid

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


def default_trial_ends_at():
    # Sets a new business trial expiry exactly 60 days after creation.
    return timezone.now() + timedelta(days=60)


def generate_subscription_payment_reference():
    # Creates a unique Paystack-safe reference without business details.
    timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
    return f"STF-{timestamp}-{uuid.uuid4().hex[:12].upper()}"


document_prefix_validator = RegexValidator(
    regex=r"^[A-Za-z0-9-]+$",
    message=(
        "Use only letters, numbers and hyphens "
        "for document prefixes."
    ),
)


class Business(models.Model):
    """Represents one inventory workspace owned by a registered user."""

    class BusinessType(models.TextChoices):
        BUILDING_MATERIALS = (
            "building_materials",
            "Building materials",
        )
        BOUTIQUE = "boutique", "Boutique"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    class SubscriptionStatus(models.TextChoices):
        TRIAL = "trial", "Free trial"
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_businesses",
    )
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=200, unique=True)
    business_type = models.CharField(
        max_length=30,
        choices=BusinessType.choices,
    )
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    location = models.CharField(max_length=255, blank=True)

    # Starts every new business on a 60-day free trial.
    trial_started_at = models.DateTimeField(default=timezone.now)
    trial_ends_at = models.DateTimeField(default=default_trial_ends_at)
    subscription_status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.TRIAL,
    )
    subscription_started_at = models.DateTimeField(blank=True, null=True)
    subscription_ends_at = models.DateTimeField(blank=True, null=True)

    # Controls the business-specific numbers shown on invoices and receipts.
    invoice_prefix = models.CharField(
        max_length=12,
        default="INV",
        validators=(document_prefix_validator,),
    )
    receipt_prefix = models.CharField(
        max_length=12,
        default="RCT",
        validators=(document_prefix_validator,),
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        indexes = [
            models.Index(fields=("owner", "status")),
            models.Index(fields=("business_type", "status")),
        ]

    @property
    def has_active_subscription(self):
        # Grants paid access only while the verified subscription is current.
        return bool(
            self.subscription_status == self.SubscriptionStatus.ACTIVE
            and self.subscription_ends_at
            and self.subscription_ends_at > timezone.now()
        )

    @property
    def is_trial_active(self):
        # Keeps free access available until the full 60-day trial ends.
        return bool(
            self.subscription_status == self.SubscriptionStatus.TRIAL
            and self.trial_ends_at > timezone.now()
        )

    @property
    def subscription_reminder_due(self):
        # Starts reminders 15 days before the 60-day trial expires.
        reminder_starts_at = self.trial_ends_at - timedelta(days=15)
        now = timezone.now()
        return bool(
            self.is_trial_active
            and reminder_starts_at <= now < self.trial_ends_at
        )

    @property
    def has_system_access(self):
        # Allows access during the trial or an active paid subscription.
        return self.is_trial_active or self.has_active_subscription

    def __str__(self):
        return self.name


class BusinessMembership(models.Model):
    """Connects a user to a business with a business-specific role."""

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MANAGER = "manager", "Manager"
        CASHIER = "cashier", "Cashier"
        INVENTORY_CLERK = (
            "inventory_clerk",
            "Inventory clerk",
        )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="business_memberships",
    )
    role = models.CharField(
        max_length=30,
        choices=Role.choices,
        default=Role.CASHIER,
    )
    is_active = models.BooleanField(default=True)
    last_active_at = models.DateTimeField(blank=True, null=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("business__name", "user__email")
        constraints = [
            models.UniqueConstraint(
                fields=("business", "user"),
                name="unique_user_membership_per_business",
            ),
        ]
        indexes = [
            models.Index(fields=("business", "is_active")),
            models.Index(fields=("user", "is_active")),
            models.Index(fields=("business", "role")),
        ]

    def __str__(self):
        return (
            f"{self.user.email} - "
            f"{self.business.name} ({self.get_role_display()})"
        )


class SubscriptionPayment(models.Model):
    """Audits one owner-initiated StockFlow subscription payment."""

    class Gateway(models.TextChoices):
        PAYSTACK = "paystack", "Paystack"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESSFUL = "successful", "Successful"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="subscription_payments",
    )
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="initiated_subscription_payments",
        blank=True,
        null=True,
    )
    initiated_by_email = models.EmailField()
    initiated_by_name = models.CharField(max_length=150)

    # Stores the exact commercial terms used for this payment attempt.
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("99.00"),
    )
    amount_subunit = models.PositiveIntegerField(default=9900)
    currency = models.CharField(max_length=3, default="GHS")
    duration_days = models.PositiveSmallIntegerField(default=40)

    gateway = models.CharField(
        max_length=30,
        choices=Gateway.choices,
        default=Gateway.PAYSTACK,
    )
    reference = models.CharField(
        max_length=80,
        unique=True,
        default=generate_subscription_payment_reference,
        editable=False,
    )
    provider_transaction_id = models.CharField(
        max_length=80,
        blank=True,
    )
    provider_status = models.CharField(max_length=40, blank=True)
    channel = models.CharField(max_length=40, blank=True)
    authorization_url = models.URLField(max_length=500, blank=True)
    access_code = models.CharField(max_length=160, blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    failure_reason = models.TextField(blank=True)
    provider_response = models.JSONField(default=dict, blank=True)

    paid_at = models.DateTimeField(blank=True, null=True)
    verified_at = models.DateTimeField(blank=True, null=True)
    fulfilled_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="subscription_payment_amount_above_zero",
            ),
            models.CheckConstraint(
                condition=models.Q(amount_subunit__gt=0),
                name="subscription_payment_subunit_above_zero",
            ),
            models.CheckConstraint(
                condition=models.Q(duration_days__gt=0),
                name="subscription_payment_duration_above_zero",
            ),
            models.UniqueConstraint(
                fields=("gateway", "provider_transaction_id"),
                condition=~models.Q(provider_transaction_id=""),
                name="unique_subscription_provider_transaction",
            ),
        ]
        indexes = [
            models.Index(fields=("business", "status")),
            models.Index(fields=("business", "created_at")),
            models.Index(fields=("status", "created_at")),
        ]

    @property
    def is_fulfilled(self):
        # Treats fulfillment time as the source of truth for value delivery.
        return self.fulfilled_at is not None

    def __str__(self):
        return (
            f"{self.business.name} - "
            f"{self.currency} {self.amount} - {self.status}"
        )
