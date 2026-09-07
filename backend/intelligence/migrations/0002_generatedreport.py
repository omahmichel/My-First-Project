from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("intelligence", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="GeneratedReport",
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
                    "report_type",
                    models.CharField(
                        choices=[
                            (
                                "daily_summary",
                                "Daily business summary",
                            ),
                            (
                                "weekly_management",
                                "Weekly management report",
                            ),
                            (
                                "monthly_management",
                                "Monthly management report",
                            ),
                            (
                                "sales_profit",
                                "Sales and profit report",
                            ),
                            (
                                "stock_risk_restocking",
                                "Stock risk and restocking report",
                            ),
                            (
                                "supplier_balances",
                                "Supplier balances report",
                            ),
                            (
                                "customer_debt",
                                "Customer debt report",
                            ),
                        ],
                        db_index=True,
                        max_length=40,
                    ),
                ),
                ("title", models.CharField(max_length=180)),
                (
                    "period_start",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "period_end",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "data_confidence",
                    models.CharField(
                        default="low",
                        max_length=20,
                    ),
                ),
                (
                    "payload",
                    models.JSONField(default=dict),
                ),
                (
                    "ai_narrative",
                    models.TextField(blank=True),
                ),
                (
                    "ai_status",
                    models.CharField(
                        choices=[
                            ("not_requested", "Not requested"),
                            ("completed", "Completed"),
                            ("unavailable", "Unavailable"),
                        ],
                        default="not_requested",
                        max_length=20,
                    ),
                ),
                (
                    "ai_provider",
                    models.CharField(blank=True, max_length=40),
                ),
                (
                    "ai_model",
                    models.CharField(blank=True, max_length=80),
                ),
                (
                    "generated_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "business",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="generated_intelligence_reports",
                        to="businesses.business",
                    ),
                ),
                (
                    "generated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="generated_intelligence_reports",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-generated_at",),
            },
        ),
    ]
