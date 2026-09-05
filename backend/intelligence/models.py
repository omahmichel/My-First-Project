import uuid

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
