import uuid

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models


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
