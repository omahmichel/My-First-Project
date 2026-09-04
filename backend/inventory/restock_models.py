import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from businesses.models import Business
from .models import Product


def generate_restock_number():
    return f"RST-{uuid.uuid4().hex[:10].upper()}"


class Supplier(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="suppliers"
    )
    name = models.CharField(max_length=180)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-is_active", "name")
        indexes = [
            models.Index(fields=("business", "is_active")),
            models.Index(fields=("business", "name")),
        ]

    def save(self, *args, **kwargs):
        self.name = self.name.strip()
        if not self.name:
            raise ValidationError({"name": "A supplier name is required."})
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class RestockPurchase(models.Model):
    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "Unpaid"
        PARTIAL = "partial", "Partially paid"
        PAID = "paid", "Paid"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="restock_purchases"
    )
    supplier = models.ForeignKey(
        Supplier, on_delete=models.PROTECT, related_name="restock_purchases"
    )
    purchase_number = models.CharField(
        max_length=32, unique=True, default=generate_restock_number, editable=False
    )
    supplier_reference = models.CharField(max_length=120, blank=True)
    purchase_date = models.DateField(default=timezone.localdate)
    total_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0.00")
    )
    amount_paid = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0.00")
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.UNPAID,
    )
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        related_name="created_restock_purchases",
        null=True,
        blank=True,
    )
    created_by_name = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-purchase_date", "-created_at")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(total_amount__gte=0),
                name="restock_total_not_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(amount_paid__gte=0),
                name="restock_paid_not_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(amount_paid__lte=models.F("total_amount")),
                name="restock_paid_not_above_total",
            ),
        ]
        indexes = [
            models.Index(fields=("business", "purchase_date")),
            models.Index(fields=("business", "payment_status")),
            models.Index(fields=("supplier", "purchase_date")),
        ]

    @property
    def outstanding_balance(self):
        return max(Decimal("0.00"), self.total_amount - self.amount_paid)

    def save(self, *args, **kwargs):
        if self.created_by_id:
            self.created_by_name = (
                self.created_by.full_name or self.created_by.email
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return self.purchase_number


class RestockItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase = models.ForeignKey(
        RestockPurchase, on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="restock_items"
    )
    product_name = models.CharField(max_length=180)
    sku = models.CharField(max_length=100)
    unit = models.CharField(max_length=20)
    quantity = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=14, decimal_places=2)
    line_total = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        ordering = ("id",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="restock_item_quantity_above_zero",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_cost__gte=0),
                name="restock_item_unit_cost_not_negative",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.product_id:
            self.product_name = self.product.name
            self.sku = self.product.sku
            self.unit = self.product.unit
        self.line_total = self.unit_cost * self.quantity
        super().save(*args, **kwargs)


class RestockPayment(models.Model):
    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        MOBILE_MONEY = "mobile_money", "Mobile Money"
        BANK_TRANSFER = "bank_transfer", "Bank transfer"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="restock_payments"
    )
    purchase = models.ForeignKey(
        RestockPurchase, on_delete=models.CASCADE, related_name="payments"
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    method = models.CharField(
        max_length=30, choices=Method.choices, default=Method.CASH
    )
    note = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        related_name="recorded_restock_payments",
        null=True,
        blank=True,
    )
    recorded_by_name = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="restock_payment_amount_above_zero",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.recorded_by_id:
            self.recorded_by_name = (
                self.recorded_by.full_name or self.recorded_by.email
            )
        super().save(*args, **kwargs)
