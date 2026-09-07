import uuid

from django.conf import settings
from django.db import models

from businesses.models import Business


class IntelligenceSnapshot(models.Model):
    """Stores a historical, verified business-intelligence snapshot."""

    class SnapshotType(models.TextChoices):
        OVERVIEW = "overview", "Overview"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="intelligence_snapshots",
    )
    snapshot_type = models.CharField(
        max_length=30,
        choices=SnapshotType.choices,
        default=SnapshotType.OVERVIEW,
    )
    period_start = models.DateTimeField(blank=True, null=True)
    period_end = models.DateTimeField(blank=True, null=True)
    metrics = models.JSONField(default=dict, blank=True)
    confidence = models.JSONField(default=dict, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-generated_at",)
        indexes = [
            models.Index(
                fields=("business", "snapshot_type", "generated_at")
            ),
            models.Index(fields=("business", "generated_at")),
        ]

    def __str__(self):
        return (
            f"{self.business.name} - {self.snapshot_type} "
            f"- {self.generated_at:%Y-%m-%d %H:%M}"
        )


class BusinessInsight(models.Model):
    """Stores one explainable intelligence finding for a business."""

    class InsightType(models.TextChoices):
        PERFORMANCE = "performance", "Performance"
        INVENTORY = "inventory", "Inventory"
        DEBT = "debt", "Debt"
        MARGIN = "margin", "Margin"
        ANOMALY = "anomaly", "Anomaly"

    class Severity(models.TextChoices):
        INFO = "info", "Information"
        ATTENTION = "attention", "Needs attention"
        HIGH = "high", "High priority"

    class Confidence(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        DISMISSED = "dismissed", "Dismissed"
        RESOLVED = "resolved", "Resolved"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="business_insights",
    )
    source_snapshot = models.ForeignKey(
        IntelligenceSnapshot,
        on_delete=models.SET_NULL,
        related_name="insights",
        blank=True,
        null=True,
    )
    insight_type = models.CharField(
        max_length=30,
        choices=InsightType.choices,
    )
    severity = models.CharField(
        max_length=20,
        choices=Severity.choices,
        default=Severity.INFO,
    )
    confidence = models.CharField(
        max_length=20,
        choices=Confidence.choices,
        default=Confidence.LOW,
    )
    title = models.CharField(max_length=180)
    summary = models.TextField()
    evidence = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    generated_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("-generated_at",)
        indexes = [
            models.Index(fields=("business", "status", "generated_at")),
            models.Index(
                fields=("business", "insight_type", "generated_at")
            ),
        ]

    def __str__(self):
        return self.title


class ForecastRun(models.Model):
    """Stores one deterministic forecast run and its verified output."""

    class Horizon(models.IntegerChoices):
        SEVEN_DAYS = 7, "7 days"
        THIRTY_DAYS = 30, "30 days"
        NINETY_DAYS = 90, "90 days"

    class Status(models.TextChoices):
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="forecast_runs",
    )
    horizon_days = models.PositiveSmallIntegerField(
        choices=Horizon.choices,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.COMPLETED,
    )
    algorithm = models.CharField(max_length=80)
    algorithm_version = models.CharField(max_length=40, blank=True)
    history_start = models.DateField(blank=True, null=True)
    history_end = models.DateField(blank=True, null=True)
    parameters = models.JSONField(default=dict, blank=True)
    results = models.JSONField(default=dict, blank=True)
    confidence = models.JSONField(default=dict, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-generated_at",)
        indexes = [
            models.Index(
                fields=("business", "horizon_days", "generated_at")
            ),
            models.Index(fields=("business", "generated_at")),
        ]

    def __str__(self):
        return (
            f"{self.business.name} - {self.horizon_days} day forecast "
            f"- {self.generated_at:%Y-%m-%d %H:%M}"
        )

class GeneratedReport(models.Model):
    """Stores one verified management report generated from StockFlow truth."""

    class ReportType(models.TextChoices):
        DAILY_SUMMARY = "daily_summary", "Daily business summary"
        WEEKLY_MANAGEMENT = "weekly_management", "Weekly management report"
        MONTHLY_MANAGEMENT = "monthly_management", "Monthly management report"
        SALES_PROFIT = "sales_profit", "Sales and profit report"
        STOCK_RISK = (
            "stock_risk_restocking",
            "Stock risk and restocking report",
        )
        SUPPLIER_BALANCES = "supplier_balances", "Supplier balances report"
        CUSTOMER_DEBT = "customer_debt", "Customer debt report"

    class AIStatus(models.TextChoices):
        NOT_REQUESTED = "not_requested", "Not requested"
        COMPLETED = "completed", "Completed"
        UNAVAILABLE = "unavailable", "Unavailable"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="generated_intelligence_reports",
    )
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="generated_intelligence_reports",
        blank=True,
        null=True,
    )
    report_type = models.CharField(
        max_length=40,
        choices=ReportType.choices,
        db_index=True,
    )
    title = models.CharField(max_length=180)
    period_start = models.DateTimeField(blank=True, null=True)
    period_end = models.DateTimeField(blank=True, null=True)
    data_confidence = models.CharField(max_length=20, default="low")
    payload = models.JSONField(default=dict)
    ai_narrative = models.TextField(blank=True)
    ai_status = models.CharField(
        max_length=20,
        choices=AIStatus.choices,
        default=AIStatus.NOT_REQUESTED,
    )
    ai_provider = models.CharField(max_length=40, blank=True)
    ai_model = models.CharField(max_length=80, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-generated_at",)

    def __str__(self):
        return (
            f"{self.business.name} - {self.get_report_type_display()} "
            f"- {self.generated_at:%Y-%m-%d %H:%M}"
        )


class AutomationRule(models.Model):
    """Stores one business-scoped StockFlow Intelligence automation rule."""

    class RuleType(models.TextChoices):
        RISK_MONITOR = "risk_monitor", "Business risk monitor"
        DAILY_CLOSING = "daily_closing", "Daily closing summary"
        WEEKLY_MANAGEMENT = (
            "weekly_management",
            "Weekly management summary",
        )

    class ScheduleFrequency(models.TextChoices):
        HOURLY = "hourly", "Hourly"
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"

    class LastStatus(models.TextChoices):
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="intelligence_automation_rules",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_intelligence_automation_rules",
        blank=True,
        null=True,
    )
    rule_type = models.CharField(
        max_length=40,
        choices=RuleType.choices,
    )
    schedule_frequency = models.CharField(
        max_length=20,
        choices=ScheduleFrequency.choices,
    )
    is_enabled = models.BooleanField(default=True)
    hour_utc = models.PositiveSmallIntegerField(default=0)
    weekday = models.PositiveSmallIntegerField(blank=True, null=True)
    include_ai_summary = models.BooleanField(default=False)
    config = models.JSONField(default=dict, blank=True)
    next_run_at = models.DateTimeField(
        blank=True,
        null=True,
        db_index=True,
    )
    last_run_at = models.DateTimeField(blank=True, null=True)
    last_status = models.CharField(
        max_length=20,
        choices=LastStatus.choices,
        blank=True,
    )
    last_error = models.CharField(max_length=255, blank=True)
    consecutive_failures = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("rule_type", "created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("business", "rule_type"),
                name="unique_intelligence_automation_rule_per_business",
            )
        ]

    def __str__(self):
        return f"{self.business.name} - {self.get_rule_type_display()}"


class AutomationEvent(models.Model):
    """Immutable advisory event emitted by an Intelligence automation rule."""

    class EventType(models.TextChoices):
        LOW_STOCK = "low_stock", "Low stock"
        STOCKOUT_RISK = "stockout_risk", "Forecasted stock-out"
        DEAD_STOCK = "dead_stock", "Dead stock"
        OVERSTOCK = "overstock", "Overstock"
        SALES_ANOMALY = "sales_anomaly", "Sales anomaly"
        MARGIN = "margin_deterioration", "Margin deterioration"
        SUPPLIER_DEBT = "supplier_debt", "Supplier debt"
        CUSTOMER_DEBT = "customer_debt", "Customer debt"
        LARGE_DISCOUNT = "large_discount", "Large discount"
        STOCK_ADJUSTMENT = (
            "suspicious_stock_adjustment",
            "Suspicious stock adjustment",
        )
        REVENUE_DECLINE = "revenue_decline", "Revenue decline"
        RECOMMENDATION = "recommendation", "Recommendation"
        REPORT_GENERATED = "report_generated", "Report generated"

    class Severity(models.TextChoices):
        INFO = "info", "Information"
        ATTENTION = "attention", "Needs attention"
        HIGH = "high", "High priority"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="intelligence_automation_events",
    )
    rule = models.ForeignKey(
        AutomationRule,
        on_delete=models.SET_NULL,
        related_name="events",
        blank=True,
        null=True,
    )
    event_type = models.CharField(
        max_length=40,
        choices=EventType.choices,
    )
    severity = models.CharField(
        max_length=20,
        choices=Severity.choices,
        default=Severity.INFO,
    )
    title = models.CharField(max_length=180)
    summary = models.TextField()
    evidence = models.JSONField(default=dict, blank=True)
    dedupe_key = models.CharField(max_length=255)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-generated_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("business", "dedupe_key"),
                name="unique_intelligence_automation_event_dedupe",
            )
        ]

    def __str__(self):
        return self.title


class AutomationRun(models.Model):
    """Stores one scheduled or manual automation execution audit record."""

    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    class TriggerType(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        MANUAL = "manual", "Manual"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="intelligence_automation_runs",
    )
    rule = models.ForeignKey(
        AutomationRule,
        on_delete=models.SET_NULL,
        related_name="runs",
        blank=True,
        null=True,
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="requested_intelligence_automation_runs",
        blank=True,
        null=True,
    )
    trigger_type = models.CharField(
        max_length=20,
        choices=TriggerType.choices,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RUNNING,
    )
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(blank=True, null=True)
    event_count = models.PositiveIntegerField(default=0)
    result = models.JSONField(default=dict, blank=True)
    error_code = models.CharField(max_length=80, blank=True)
    error_message = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("-started_at",)

    def __str__(self):
        return f"{self.business.name} - {self.trigger_type} - {self.status}"
