import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("businesses", "0005_business_vat_registered_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BusinessPaymentAccount",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "account_type",
                    models.CharField(
                        choices=[
                            ("bank", "Bank account"),
                            ("mobile_money", "Mobile Money wallet"),
                        ],
                        max_length=30,
                    ),
                ),
                ("display_name", models.CharField(max_length=120)),
                (
                    "bank_name",
                    models.CharField(blank=True, max_length=120),
                ),
                ("account_name", models.CharField(max_length=150)),
                (
                    "network",
                    models.CharField(blank=True, max_length=40),
                ),
                ("encrypted_account_number", models.TextField()),
                (
                    "account_last_four",
                    models.CharField(max_length=4),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("is_default", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "business",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payment_accounts",
                        to="businesses.business",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_business_payment_accounts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_business_payment_accounts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": (
                    "-is_default",
                    "display_name",
                    "created_at",
                ),
            },
        ),
        migrations.AddConstraint(
            model_name="businesspaymentaccount",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    is_active=True,
                    is_default=True,
                ),
                fields=("business",),
                name="uniq_active_default_pay_account",
            ),
        ),
    ]
