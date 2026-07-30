import uuid

from django.core.exceptions import ValidationError
from django.db import models

from businesses.models import Business


class Product(models.Model):
    # Stores one business-isolated inventory product.

    class ProductType(models.TextChoices):
        STANDARD = "standard", "Standard product"
        TILE = "tile", "Tile product"
        FASHION = "fashion", "Boutique product"

    class Unit(models.TextChoices):
        PIECE = "piece", "Piece"
        BOX = "box", "Box"
        BAG = "bag", "Bag"
        PACK = "pack", "Pack"
        BUNDLE = "bundle", "Bundle"
        LENGTH = "length", "Length"
        LITRE = "litre", "Litre"
        KILOGRAM = "kilogram", "Kilogram"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="products",
    )
    product_type = models.CharField(
        max_length=20,
        choices=ProductType.choices,
        default=ProductType.STANDARD,
    )
    name = models.CharField(max_length=180)
    sku = models.CharField(max_length=100)
    category = models.CharField(max_length=120)
    brand = models.CharField(max_length=120, blank=True)
    unit = models.CharField(
        max_length=20,
        choices=Unit.choices,
        default=Unit.PIECE,
    )

    # Shared stock and pricing fields used by all supported businesses.
    stock = models.PositiveIntegerField(default=0)

    # Holds stock temporarily while an external payment prompt is pending.
    reserved_stock = models.PositiveIntegerField(default=0)
    low_stock_level = models.PositiveIntegerField(default=0)
    cost_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )
    selling_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    # Tile-specific identification and box-conversion fields.
    design_code = models.CharField(max_length=100, blank=True)
    size = models.CharField(max_length=100, blank=True)
    finish = models.CharField(max_length=100, blank=True)
    color = models.CharField(max_length=120, blank=True)
    batch_number = models.CharField(max_length=120, blank=True)
    pieces_per_box = models.PositiveIntegerField(default=0)
    sqm_per_box = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )
    loose_pieces = models.PositiveIntegerField(default=0)

    # Boutique products use a style code plus the shared size and colour fields.
    style_code = models.CharField(max_length=100, blank=True)

    # Soft deactivation preserves products needed by future sales history.
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("business", "sku"),
                name="unique_product_sku_per_business",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    reserved_stock__lte=models.F("stock"),
                ),
                name="reserved_stock_cannot_exceed_stock",
            ),
        ]
        indexes = [
            models.Index(fields=("business", "is_active")),
            models.Index(fields=("business", "product_type")),
            models.Index(fields=("business", "category")),
            models.Index(fields=("business", "name")),
            models.Index(fields=("business", "design_code")),
        ]

    def clean(self):
        # Prevents product types from being assigned to the wrong business.
        errors = {}

        if (
            self.product_type == self.ProductType.FASHION
            and self.business.business_type
            != Business.BusinessType.BOUTIQUE
        ):
            errors["product_type"] = (
                "Boutique products can only belong to a boutique business."
            )

        if (
            self.product_type
            in (self.ProductType.STANDARD, self.ProductType.TILE)
            and self.business.business_type
            != Business.BusinessType.BUILDING_MATERIALS
        ):
            errors["product_type"] = (
                "Standard and tile products can only belong to a "
                "building materials business."
            )

        if (
            self.product_type == self.ProductType.TILE
            and not self.design_code.strip()
        ):
            errors["design_code"] = (
                "A tile design number or design code is required."
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.name} ({self.sku})"


class StockMovement(models.Model):
    # Records every inventory increase or reduction for audit history.

    class MovementType(models.TextChoices):
        STOCK_IN = "stock_in", "New stock received"
        ADJUSTMENT = "adjustment", "Manual correction"
        DAMAGE = "damage", "Damaged stock"
        RETURN = "return", "Customer return"
        SALE = "sale", "Sale"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="stock_movements",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )

    # Snapshots keep history readable even after product details change.
    product_name = models.CharField(max_length=180)
    unit = models.CharField(max_length=20)

    movement_type = models.CharField(
        max_length=20,
        choices=MovementType.choices,
    )
    quantity = models.IntegerField()
    previous_stock = models.PositiveIntegerField()
    new_stock = models.PositiveIntegerField()

    reason = models.CharField(max_length=255)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        related_name="created_stock_movements",
        blank=True,
        null=True,
    )
    created_by_name = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("business", "created_at")),
            models.Index(fields=("business", "movement_type")),
            models.Index(fields=("product", "created_at")),
        ]

    def clean(self):
        # Prevents cross-business stock history and invalid stock totals.
        errors = {}

        if self.product_id and self.business_id:
            if self.product.business_id != self.business_id:
                errors["product"] = (
                    "The selected product does not belong to this business."
                )

        if self.quantity == 0:
            errors["quantity"] = (
                "A stock movement quantity cannot be zero."
            )

        if self.previous_stock + self.quantity != self.new_stock:
            errors["new_stock"] = (
                "The new stock must equal previous stock plus quantity."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Stores readable product and user snapshots automatically.
        if self.product_id:
            self.product_name = self.product.name
            self.unit = self.product.unit

        if self.created_by_id:
            self.created_by_name = (
                self.created_by.full_name
                or self.created_by.email
            )

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.product_name}: "
            f"{self.quantity:+d} {self.unit}"
        )

