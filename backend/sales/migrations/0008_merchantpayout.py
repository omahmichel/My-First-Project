import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("businesses", "0008_businesspaymentaccount_paystack_payout"),
        ("sales", "0007_payment_receiving_account_account_name_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="MerchantPayout",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=14)),
                ("currency", models.CharField(default="GHS", max_length=3)),
                ("reference", models.CharField(max_length=50, unique=True)),
                ("transfer_code", models.CharField(blank=True, max_length=100)),
                ("provider_status", models.CharField(blank=True, max_length=40)),
                ("recipient_code_snapshot", models.CharField(blank=True, max_length=80)),
                ("receiving_account_name_snapshot", models.CharField(blank=True, max_length=150)),
                ("receiving_account_network_snapshot", models.CharField(blank=True, max_length=40)),
                ("receiving_account_masked_number_snapshot", models.CharField(blank=True, max_length=32)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("processing", "Processing"), ("retry", "Retry"), ("blocked", "Blocked"), ("successful", "Successful"), ("failed", "Failed"), ("reversed", "Reversed")], default="pending", max_length=20)),
                ("attempt_count", models.PositiveIntegerField(default=0)),
                ("failure_reason", models.TextField(blank=True)),
                ("last_attempted_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("business", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="merchant_payouts", to="businesses.business")),
                ("payment", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="merchant_payout", to="sales.payment")),
                ("receiving_account", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="merchant_payouts", to="businesses.businesspaymentaccount")),
            ],
            options={
                "ordering": ("created_at",),
                "indexes": [models.Index(fields=["status", "created_at"], name="sales_merch_status_08f718_idx"), models.Index(fields=["business", "created_at"], name="sales_merch_busines_43c620_idx")],
                "constraints": [models.CheckConstraint(condition=models.Q(("amount__gt", 0)), name="merchant_payout_amount_above_zero")],
            },
        ),
    ]
