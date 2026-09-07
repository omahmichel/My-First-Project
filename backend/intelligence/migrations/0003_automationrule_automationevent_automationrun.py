from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("intelligence", "0002_generatedreport"),
    ]

    operations = [
        migrations.CreateModel(
            name="AutomationRule",
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
                    "rule_type",
                    models.CharField(
                        choices=[
                            ("risk_monitor", "Business risk monitor"),
                            ("daily_closing", "Daily closing summary"),
                            (
                                "weekly_management",
                                "Weekly management summary",
                            ),
                        ],
                        max_length=40,
                    ),
                ),
                (
                    "schedule_frequency",
                    models.CharField(
                        choices=[
                            ("hourly", "Hourly"),
                            ("daily", "Daily"),
                            ("weekly", "Weekly"),
                        ],
                        max_length=20,
                    ),
                ),
                ("is_enabled", models.BooleanField(default=True)),
                ("hour_utc", models.PositiveSmallIntegerField(default=0)),
                (
                    "weekday",
                    models.PositiveSmallIntegerField(blank=True, null=True),
                ),
                ("include_ai_summary", models.BooleanField(default=False)),
                ("config", models.JSONField(blank=True, default=dict)),
                (
                    "next_run_at",
                    models.DateTimeField(
                        blank=True,
                        db_index=True,
                        null=True,
                    ),
                ),
                ("last_run_at", models.DateTimeField(blank=True, null=True)),
                (
                    "last_status",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        max_length=20,
                    ),
                ),
                ("last_error", models.CharField(blank=True, max_length=255)),
                ("consecutive_failures", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "business",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="intelligence_automation_rules",
                        to="businesses.business",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_intelligence_automation_rules",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ("rule_type", "created_at")},
        ),
        migrations.CreateModel(
            name="AutomationEvent",
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
                    "event_type",
                    models.CharField(
                        choices=[
                            ("low_stock", "Low stock"),
                            ("stockout_risk", "Forecasted stock-out"),
                            ("dead_stock", "Dead stock"),
                            ("overstock", "Overstock"),
                            ("sales_anomaly", "Sales anomaly"),
                            ("margin_deterioration", "Margin deterioration"),
                            ("supplier_debt", "Supplier debt"),
                            ("customer_debt", "Customer debt"),
                            ("large_discount", "Large discount"),
                            (
                                "suspicious_stock_adjustment",
                                "Suspicious stock adjustment",
                            ),
                            ("revenue_decline", "Revenue decline"),
                            ("recommendation", "Recommendation"),
                            ("report_generated", "Report generated"),
                        ],
                        max_length=40,
                    ),
                ),
                (
                    "severity",
                    models.CharField(
                        choices=[
                            ("info", "Information"),
                            ("attention", "Needs attention"),
                            ("high", "High priority"),
                        ],
                        default="info",
                        max_length=20,
                    ),
                ),
                ("title", models.CharField(max_length=180)),
                ("summary", models.TextField()),
                ("evidence", models.JSONField(blank=True, default=dict)),
                ("dedupe_key", models.CharField(max_length=255)),
                ("generated_at", models.DateTimeField(auto_now_add=True)),
                (
                    "business",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="intelligence_automation_events",
                        to="businesses.business",
                    ),
                ),
                (
                    "rule",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="events",
                        to="intelligence.automationrule",
                    ),
                ),
            ],
            options={"ordering": ("-generated_at",)},
        ),
        migrations.CreateModel(
            name="AutomationRun",
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
                    "trigger_type",
                    models.CharField(
                        choices=[
                            ("scheduled", "Scheduled"),
                            ("manual", "Manual"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("running", "Running"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        default="running",
                        max_length=20,
                    ),
                ),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("event_count", models.PositiveIntegerField(default=0)),
                ("result", models.JSONField(blank=True, default=dict)),
                ("error_code", models.CharField(blank=True, max_length=80)),
                ("error_message", models.CharField(blank=True, max_length=255)),
                (
                    "business",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="intelligence_automation_runs",
                        to="businesses.business",
                    ),
                ),
                (
                    "requested_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="requested_intelligence_automation_runs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "rule",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="runs",
                        to="intelligence.automationrule",
                    ),
                ),
            ],
            options={"ordering": ("-started_at",)},
        ),
        migrations.AddConstraint(
            model_name="automationrule",
            constraint=models.UniqueConstraint(
                fields=("business", "rule_type"),
                name="unique_intelligence_automation_rule_per_business",
            ),
        ),
        migrations.AddConstraint(
            model_name="automationevent",
            constraint=models.UniqueConstraint(
                fields=("business", "dedupe_key"),
                name="unique_intelligence_automation_event_dedupe",
            ),
        ),
    ]
