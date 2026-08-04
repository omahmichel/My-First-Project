import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from businesses.models import Business
from customers.models import Customer
from inventory.models import Product


class DocumentSequence(models.Model):
    # Stores business-specific counters used for safe document numbering.

    business = models.OneToOneField(
        Business,
        on_delete=models.CASCADE,
        related_name="document_sequence",
    )
    next_sale_number = models.PositiveBigIntegerField(default=1)
    next_invoice_number = models.PositiveBigIntegerField(default=1)
    next_receipt_number = models.PositiveBigIntegerField(default=1)
    next_waybill_number = models.PositiveBigIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Document sequence for {self.business.name}"


class Sale(models.Model):
    # Stores one completed, credit, or payment-pending business sale.

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Cash"
        MOBILE_MONEY = "mobile_money", "Mobile Money"
        BANK_TRANSFER = "bank_transfer", "Bank transfer"
        CREDIT = "credit", "Credit or part payment"

    class Status(models.TextChoices):
        PENDING_PAYMENT = "pending_payment", "Payment pending"
        COMPLETED = "completed", "Completed"
        PARTIALLY_PAID = "partially_paid", "Partially paid"
        CANCELLED = "cancelled", "Cancelled"
        FAILED = "failed", "Failed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="sales",
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="sales",
        blank=True,
        null=True,
    )

    # Snapshots preserve customer details used on historical invoices.
    customer_name = models.CharField(
        max_length=180,
        default="Walk-in customer",
    )
    customer_phone = models.CharField(max_length=30, blank=True)

    sale_number = models.CharField(max_length=40)
    invoice_number = models.CharField(max_length=40)

    # Prevents retries from creating duplicate sales.
    idempotency_key = models.CharField(
        max_length=128,
        blank=True,
    )

    payment_method = models.CharField(
        max_length=30,
        choices=PaymentMethod.choices,
    )
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING_PAYMENT,
    )

    subtotal = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )
    discount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )
    total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )
    amount_paid = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )
    outstanding_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    # Stores the agreed due date for credit or part-payment debt.
    debt_due_date = models.DateField(
        blank=True,
        null=True,
    )

    # Freezes the principal used for non-compounding overdue tiers.
    debt_principal_at_due = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    cashier = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        related_name="processed_sales",
        blank=True,
        null=True,
    )
    cashier_name = models.CharField(max_length=150)

    # Pending external payments release their reserved stock after this time.
    reservation_expires_at = models.DateTimeField(
        blank=True,
        null=True,
    )
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("business", "sale_number"),
                name="unique_sale_number_per_business",
            ),
            models.UniqueConstraint(
                fields=("business", "invoice_number"),
                name="unique_invoice_number_per_business",
            ),
            models.UniqueConstraint(
                fields=("business", "idempotency_key"),
                condition=~models.Q(idempotency_key=""),
                name="unique_sale_idempotency_per_business",
            ),
            models.CheckConstraint(
                condition=models.Q(subtotal__gte=0),
                name="sale_subtotal_not_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(discount__gte=0),
                name="sale_discount_not_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(total__gte=0),
                name="sale_total_not_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(amount_paid__gte=0),
                name="sale_amount_paid_not_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(outstanding_balance__gte=0),
                name="sale_outstanding_not_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(debt_principal_at_due__gte=0),
                name="sale_debt_principal_not_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    debt_principal_at_due__lte=models.F("total"),
                ),
                name="sale_debt_principal_not_above_total",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    discount__lte=models.F("subtotal"),
                ),
                name="sale_discount_not_above_subtotal",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    amount_paid__lte=models.F("total"),
                ),
                name="sale_amount_paid_not_above_total",
            ),
        ]
        indexes = [
            models.Index(fields=("business", "created_at")),
            models.Index(fields=("business", "status")),
            models.Index(fields=("business", "payment_method")),
            models.Index(fields=("business", "reservation_expires_at")),
            models.Index(fields=("business", "debt_due_date")),
            models.Index(fields=("customer", "created_at")),
        ]

    def clean(self):
        # Protects business isolation and financial totals.
        errors = {}

        if (
            self.customer_id
            and self.business_id
            and self.customer.business_id != self.business_id
        ):
            errors["customer"] = (
                "The selected customer does not belong to this business."
            )

        expected_total = self.subtotal - self.discount
        expected_outstanding = self.total - self.amount_paid

        if self.total != expected_total:
            errors["total"] = (
                "The total must equal subtotal minus discount."
            )

        if self.outstanding_balance != expected_outstanding:
            errors["outstanding_balance"] = (
                "Outstanding balance must equal total minus amount paid."
            )

        # Only credit or part-payment sales require a customer account.
        # Pending Mobile Money prompts may still belong to walk-in customers.
        if (
            self.payment_method == self.PaymentMethod.CREDIT
            and self.outstanding_balance > Decimal("0")
            and not self.customer_id
        ):
            errors["customer"] = (
                "Select a customer before completing a credit sale."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Stores readable customer and cashier snapshots automatically.
        if self.customer_id:
            self.customer_name = self.customer.name
            self.customer_phone = self.customer.phone
        else:
            self.customer_name = "Walk-in customer"
            self.customer_phone = ""

        if self.cashier_id:
            self.cashier_name = (
                self.cashier.full_name
                or self.cashier.email
            )

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.sale_number} - {self.business.name}"


class DebtOverdueCharge(models.Model):
    # Audits each non-compounding overdue tier applied to one sale.

    class Tier(models.IntegerChoices):
        FIVE = 5, "5%"
        TEN = 10, "10%"
        FIFTEEN = 15, "15%"
        TWENTY = 20, "20%"
        TWENTY_FIVE = 25, "25%"
        THIRTY = 30, "30%"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="debt_overdue_charges",
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="debt_overdue_charges",
    )
    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name="overdue_charges",
    )
    tier_percentage = models.PositiveSmallIntegerField(
        choices=Tier.choices,
    )
    principal_base = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )
    total_charge_required = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )
    incremental_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )
    applied_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("applied_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("sale", "tier_percentage"),
                name="unique_overdue_tier_per_sale",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    tier_percentage__in=(5, 10, 15, 20, 25, 30),
                ),
                name="valid_overdue_tier_percentage",
            ),
            models.CheckConstraint(
                condition=models.Q(principal_base__gte=0),
                name="overdue_principal_base_not_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(total_charge_required__gte=0),
                name="overdue_total_charge_not_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(incremental_amount__gte=0),
                name="overdue_increment_not_negative",
            ),
        ]
        indexes = [
            models.Index(fields=("business", "applied_at")),
            models.Index(fields=("customer", "applied_at")),
            models.Index(fields=("sale", "tier_percentage")),
        ]

    def clean(self):
        # Prevents overdue records from crossing account boundaries.
        errors = {}

        if (
            self.sale_id
            and self.business_id
            and self.sale.business_id != self.business_id
        ):
            errors["business"] = (
                "The overdue charge business must match the sale."
            )

        if (
            self.sale_id
            and self.customer_id
            and self.sale.customer_id != self.customer_id
        ):
            errors["customer"] = (
                "The overdue charge customer must match the sale."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.sale.sale_number} - "
            f"{self.tier_percentage}% overdue tier"
        )


class DebtReminderSchedule(models.Model):
    # Owns one deterministic 10-day reminder slot for one sale.

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="debt_reminder_schedules",
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="debt_reminder_schedules",
    )
    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name="debt_reminder_schedules",
    )
    scheduled_for = models.DateField()
    reminder_sequence_number = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    last_attempted_at = models.DateTimeField(
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("scheduled_for", "created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("sale", "scheduled_for"),
                name="unique_debt_reminder_schedule_per_sale",
            ),
            models.CheckConstraint(
                condition=models.Q(reminder_sequence_number__gt=0),
                name="debt_reminder_sequence_above_zero",
            ),
        ]
        indexes = [
            models.Index(fields=("business", "scheduled_for")),
            models.Index(fields=("customer", "scheduled_for")),
            models.Index(fields=("status", "scheduled_for")),
        ]

    def clean(self):
        # Prevents reminder schedules from crossing account boundaries.
        errors = {}

        if (
            self.sale_id
            and self.business_id
            and self.sale.business_id != self.business_id
        ):
            errors["business"] = (
                "The reminder business must match the sale."
            )

        if (
            self.sale_id
            and self.customer_id
            and self.sale.customer_id != self.customer_id
        ):
            errors["customer"] = (
                "The reminder customer must match the sale."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.sale.sale_number} - reminder "
            f"{self.reminder_sequence_number}"
        )


class DebtReminderAttempt(models.Model):
    # Audits every send, failure, retry, or safe reminder skip.

    class Status(models.TextChoices):
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    schedule = models.ForeignKey(
        DebtReminderSchedule,
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="debt_reminder_attempts",
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="debt_reminder_attempts",
    )
    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name="debt_reminder_attempts",
    )
    attempt_number = models.PositiveIntegerField()
    attempted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
    )
    recipient_snapshot = models.CharField(
        max_length=30,
        blank=True,
    )
    message_snapshot = models.TextField(blank=True)
    provider = models.CharField(
        max_length=50,
        blank=True,
    )
    provider_reference = models.CharField(
        max_length=120,
        blank=True,
    )
    provider_response_summary = models.TextField(blank=True)
    failure_reason = models.TextField(blank=True)

    class Meta:
        ordering = ("attempted_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("schedule", "attempt_number"),
                name="unique_debt_reminder_attempt_number",
            ),
            models.CheckConstraint(
                condition=models.Q(attempt_number__gt=0),
                name="debt_reminder_attempt_above_zero",
            ),
        ]
        indexes = [
            models.Index(fields=("business", "attempted_at")),
            models.Index(fields=("customer", "attempted_at")),
            models.Index(fields=("status", "attempted_at")),
        ]

    def clean(self):
        # Keeps every attempt aligned with its locked schedule slot.
        errors = {}

        if self.schedule_id:
            if (
                self.business_id
                and self.schedule.business_id != self.business_id
            ):
                errors["business"] = (
                    "The attempt business must match its schedule."
                )

            if (
                self.customer_id
                and self.schedule.customer_id != self.customer_id
            ):
                errors["customer"] = (
                    "The attempt customer must match its schedule."
                )

            if (
                self.sale_id
                and self.schedule.sale_id != self.sale_id
            ):
                errors["sale"] = (
                    "The attempt sale must match its schedule."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.schedule.sale.sale_number} - attempt "
            f"{self.attempt_number}"
        )


class SaleItem(models.Model):

    # Stores immutable product and price snapshots for one sale line.

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="sale_items",
    )

    product_name = models.CharField(max_length=180)
    sku = models.CharField(max_length=100)
    design_code = models.CharField(max_length=100, blank=True)
    unit = models.CharField(max_length=20)

    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )
    cost_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )
    line_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )

    class Meta:
        ordering = ("id",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="sale_item_quantity_above_zero",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name="sale_item_unit_price_not_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(cost_price__gte=0),
                name="sale_item_cost_price_not_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(line_total__gte=0),
                name="sale_item_line_total_not_negative",
            ),
        ]
        indexes = [
            models.Index(fields=("sale", "product")),
            models.Index(fields=("product",)),
        ]

    def clean(self):
        # Prevents cross-business products and incorrect line totals.
        errors = {}

        if self.sale_id and self.product_id:
            if self.product.business_id != self.sale.business_id:
                errors["product"] = (
                    "The selected product does not belong to this sale's "
                    "business."
                )

        expected_line_total = self.unit_price * self.quantity

        if self.line_total != expected_line_total:
            errors["line_total"] = (
                "Line total must equal unit price multiplied by quantity."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Stores product details used by the invoice and profit reports.
        if self.product_id:
            self.product_name = self.product.name
            self.sku = self.product.sku
            self.design_code = self.product.design_code
            self.unit = self.product.unit
            self.cost_price = self.product.cost_price

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.product_name} x {self.quantity} "
            f"on {self.sale.sale_number}"
        )


class Payment(models.Model):
    # Tracks cash, bank, credit and external mobile-money payments.

    class PaymentType(models.TextChoices):
        SALE_PAYMENT = "sale_payment", "Sale payment"
        DEBT_PAYMENT = "debt_payment", "Customer debt payment"
        REFUND = "refund", "Refund"

    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        MOBILE_MONEY = "mobile_money", "Mobile Money"
        BANK_TRANSFER = "bank_transfer", "Bank transfer"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESSFUL = "successful", "Successful"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        REVERSED = "reversed", "Reversed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    sale = models.ForeignKey(
        Sale,
        on_delete=models.PROTECT,
        related_name="payments",
        blank=True,
        null=True,
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="payments",
        blank=True,
        null=True,
    )

    payment_type = models.CharField(
        max_length=30,
        choices=PaymentType.choices,
        default=PaymentType.SALE_PAYMENT,
    )
    method = models.CharField(
        max_length=30,
        choices=Method.choices,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )

    # The network remains flexible so additional providers need no migration.
    mobile_money_network = models.CharField(
        max_length=40,
        blank=True,
    )
    mobile_money_number = models.CharField(
        max_length=30,
        blank=True,
    )

    gateway = models.CharField(max_length=40, blank=True)
    gateway_reference = models.CharField(max_length=120, blank=True)
    provider_reference = models.CharField(max_length=180, blank=True)
    idempotency_key = models.CharField(max_length=128, blank=True)

    receipt_number = models.CharField(max_length=40, blank=True)
    reference = models.CharField(max_length=180, blank=True)
    note = models.TextField(blank=True)
    failure_reason = models.TextField(blank=True)

    initiated_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        related_name="initiated_payments",
        blank=True,
        null=True,
    )
    initiated_by_name = models.CharField(max_length=150)
    verified_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="payment_amount_above_zero",
            ),
            models.UniqueConstraint(
                fields=("business", "receipt_number"),
                condition=~models.Q(receipt_number=""),
                name="unique_receipt_number_per_business",
            ),
            models.UniqueConstraint(
                fields=("business", "idempotency_key"),
                condition=~models.Q(idempotency_key=""),
                name="unique_payment_idempotency_per_business",
            ),
            models.UniqueConstraint(
                fields=("gateway", "provider_reference"),
                condition=~models.Q(provider_reference=""),
                name="unique_provider_payment_reference",
            ),
            models.UniqueConstraint(
                fields=("gateway", "gateway_reference"),
                condition=~models.Q(gateway_reference=""),
                name="unique_gateway_payment_reference",
            ),
        ]
        indexes = [
            models.Index(fields=("business", "created_at")),
            models.Index(fields=("business", "status")),
            models.Index(fields=("business", "method")),
            models.Index(fields=("sale", "created_at")),
            models.Index(fields=("customer", "created_at")),
        ]

    def clean(self):
        # Protects business isolation and required mobile-money data.
        errors = {}

        if (
            self.sale_id
            and self.business_id
            and self.sale.business_id != self.business_id
        ):
            errors["sale"] = (
                "The selected sale does not belong to this business."
            )

        if (
            self.customer_id
            and self.business_id
            and self.customer.business_id != self.business_id
        ):
            errors["customer"] = (
                "The selected customer does not belong to this business."
            )

        if self.method == self.Method.MOBILE_MONEY:
            if not self.mobile_money_network.strip():
                errors["mobile_money_network"] = (
                    "Select the customer's mobile-money network."
                )

            if not self.mobile_money_number.strip():
                errors["mobile_money_number"] = (
                    "Enter the customer's mobile-money number."
                )

        if (
            self.status == self.Status.SUCCESSFUL
            and not self.receipt_number.strip()
        ):
            errors["receipt_number"] = (
                "A successful payment must have a receipt number."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Stores readable staff details without exposing sensitive credentials.
        if self.initiated_by_id:
            self.initiated_by_name = (
                self.initiated_by.full_name
                or self.initiated_by.email
            )

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.get_method_display()} payment "
            f"{self.amount} ({self.get_status_display()})"
        )


class Waybill(models.Model):
    # Stores one persistent delivery document for a completed sale.

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        DISPATCHED = "dispatched", "Dispatched"
        DELIVERED = "delivered", "Delivered"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="waybills",
    )
    sale = models.OneToOneField(
        Sale,
        on_delete=models.CASCADE,
        related_name="waybill",
    )
    waybill_number = models.CharField(max_length=40)
    recipient_name = models.CharField(max_length=180)
    recipient_phone = models.CharField(max_length=30, blank=True)
    delivery_address = models.TextField()
    dispatch_date = models.DateField()
    driver_name = models.CharField(max_length=180, blank=True)
    vehicle_number = models.CharField(max_length=80, blank=True)
    delivery_notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        related_name="created_waybills",
        blank=True,
        null=True,
    )
    created_by_name = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("business", "waybill_number"),
                name="unique_waybill_number_per_business",
            ),
        ]
        indexes = [
            models.Index(fields=("business", "created_at")),
            models.Index(fields=("business", "status")),
            models.Index(fields=("business", "dispatch_date")),
        ]

    def clean(self):
        # Prevents a waybill from crossing business boundaries.
        errors = {}

        if (
            self.sale_id
            and self.business_id
            and self.sale.business_id != self.business_id
        ):
            errors["sale"] = (
                "The selected sale does not belong to this business."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Keeps a readable creator snapshot without exposing credentials.
        if self.created_by_id:
            self.created_by_name = (
                self.created_by.full_name
                or self.created_by.email
            )

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.waybill_number} - {self.sale.sale_number}"

class DebtPaymentAllocation(models.Model):
    # Audits how one successful debt payment was split.
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    payment = models.OneToOneField(
        Payment,
        on_delete=models.CASCADE,
        related_name="debt_allocation",
    )
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="debt_payment_allocations",
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="debt_payment_allocations",
    )
    sale = models.ForeignKey(
        Sale,
        on_delete=models.PROTECT,
        related_name="debt_payment_allocations",
    )
    amount_received = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )
    overdue_charge_paid = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    principal_paid = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount_received__gt=0),
                name="debt_allocation_amount_above_zero",
            ),
            models.CheckConstraint(
                condition=models.Q(overdue_charge_paid__gte=0),
                name="debt_allocation_charge_not_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(principal_paid__gte=0),
                name="debt_allocation_principal_not_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    amount_received=(
                        models.F("overdue_charge_paid")
                        + models.F("principal_paid")
                    )
                ),
                name="debt_allocation_parts_equal_amount",
            ),
        ]
        indexes = [
            models.Index(fields=("business", "created_at")),
            models.Index(fields=("customer", "created_at")),
            models.Index(fields=("sale", "created_at")),
        ]

    def clean(self):
        # Prevents allocation records from crossing financial boundaries.
        errors = {}

        if self.payment_id:
            if self.payment.payment_type != Payment.PaymentType.DEBT_PAYMENT:
                errors["payment"] = (
                    "The allocation payment must be a debt payment."
                )

            if self.payment.status != Payment.Status.SUCCESSFUL:
                errors["payment"] = (
                    "The allocation payment must be successful."
                )

            if self.payment.business_id != self.business_id:
                errors["business"] = (
                    "The allocation business must match the payment."
                )

            if self.payment.sale_id != self.sale_id:
                errors["sale"] = (
                    "The allocation sale must match the payment."
                )

            if self.payment.customer_id != self.customer_id:
                errors["customer"] = (
                    "The allocation customer must match the payment."
                )

            if self.payment.amount != self.amount_received:
                errors["amount_received"] = (
                    "The allocation amount must match the payment."
                )

        if (
            self.overdue_charge_paid + self.principal_paid
            != self.amount_received
        ):
            errors["amount_received"] = (
                "Charge and principal allocations must equal "
                "the amount received."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.payment.receipt_number or self.payment.id} - "
            f"charge {self.overdue_charge_paid}, "
            f"principal {self.principal_paid}"
        )
