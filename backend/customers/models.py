import uuid

from django.db import models

from businesses.models import Business


class Customer(models.Model):
    # Stores one customer account inside a single business workspace.

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="customers",
    )
    name = models.CharField(max_length=180)
    phone = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)

    # These values will later be updated through controlled sales and payment flows.
    outstanding_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )
    total_purchases = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    # Soft deactivation preserves customer links needed by sales history.
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        related_name="created_customers",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(outstanding_balance__gte=0),
                name="customer_outstanding_balance_not_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(total_purchases__gte=0),
                name="customer_total_purchases_not_negative",
            ),
        ]
        indexes = [
            models.Index(fields=("business", "is_active")),
            models.Index(fields=("business", "name")),
            models.Index(fields=("business", "phone")),
            models.Index(fields=("business", "outstanding_balance")),
        ]

    def __str__(self):
        return f"{self.name} - {self.phone}"
