import uuid

from django.conf import settings
from django.db import models

from businesses.models import Business


class DataImport(models.Model):
    """Audits one previewed or applied business data import without storing the source file."""

    class Dataset(models.TextChoices):
        PRODUCTS = "products", "Products"
        CUSTOMERS = "customers", "Customers"
        SUPPLIERS = "suppliers", "Suppliers"
        BRANCH_INVENTORY = "branch_inventory", "Branch inventory"

    class FileType(models.TextChoices):
        CSV = "csv", "CSV"
        XLSX = "xlsx", "Excel workbook"

    class Status(models.TextChoices):
        PREVIEWED = "previewed", "Previewed"
        APPLIED = "applied", "Applied"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="data_imports",
    )
    dataset = models.CharField(max_length=30, choices=Dataset.choices)
    file_type = models.CharField(max_length=10, choices=FileType.choices)
    original_filename = models.CharField(max_length=255)
    file_sha256 = models.CharField(max_length=64)

    # Branch is intentionally snapshotted instead of referenced so import audit
    # remains readable if branch configuration changes later.
    branch_id_snapshot = models.UUIDField(blank=True, null=True)
    branch_name_snapshot = models.CharField(max_length=180, blank=True)
    branch_code_snapshot = models.CharField(max_length=40, blank=True)

    header_mapping = models.JSONField(default=dict, blank=True)
    row_count = models.PositiveIntegerField(default=0)
    valid_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    create_count = models.PositiveIntegerField(default=0)
    update_count = models.PositiveIntegerField(default=0)
    skip_count = models.PositiveIntegerField(default=0)

    # Raw rows are never persisted. A short-lived signed preview token carries
    # normalized rows between preview and explicit apply confirmation.
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PREVIEWED,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_data_imports",
        blank=True,
        null=True,
    )
    applied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="applied_data_imports",
        blank=True,
        null=True,
    )
    applied_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(
                fields=("business", "created_at"),
                name="integration_busines_f98dc0_idx",
            ),
            models.Index(
                fields=("business", "status"),
                name="integration_busines_a9aa6f_idx",
            ),
        ]

    def __str__(self):
        return f"{self.business.name} - {self.dataset} - {self.status}"



class MessagingPreference(models.Model):
    """Business-owned controls for outbound StockFlow intelligence messaging."""

    class MinimumSeverity(models.TextChoices):
        INFO = "info", "Information and above"
        ATTENTION = "attention", "Needs attention and above"
        HIGH = "high", "High priority only"

    business = models.OneToOneField(
        Business,
        on_delete=models.CASCADE,
        related_name="messaging_preference",
    )
    sms_enabled = models.BooleanField(default=False)
    whatsapp_enabled = models.BooleanField(default=False)
    recipient_phone = models.CharField(max_length=30, blank=True)
    minimum_severity = models.CharField(
        max_length=20,
        choices=MinimumSeverity.choices,
        default=MinimumSeverity.ATTENTION,
    )
    # Empty means all supported Intelligence event types. This keeps the
    # default disabled preference simple while allowing precise opt-in later.
    event_types = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.business.name} messaging preferences"


class MessageDelivery(models.Model):
    """Audits one external StockFlow message without storing provider secrets."""

    class Channel(models.TextChoices):
        SMS = "sms", "SMS"
        WHATSAPP = "whatsapp", "WhatsApp"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="message_deliveries",
    )
    channel = models.CharField(max_length=20, choices=Channel.choices)
    message_type = models.CharField(max_length=40, blank=True)
    source_type = models.CharField(max_length=40, blank=True)
    source_id = models.CharField(max_length=64, blank=True)
    dedupe_key = models.CharField(max_length=255, unique=True)
    recipient = models.CharField(max_length=30)
    message = models.TextField()
    provider = models.CharField(max_length=40, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    provider_reference = models.CharField(max_length=120, blank=True)
    provider_response_summary = models.TextField(blank=True)
    failure_reason = models.CharField(max_length=255, blank=True)
    attempt_count = models.PositiveIntegerField(default=0)
    sent_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(
                fields=("business", "created_at"),
                name="integ_msg_bus_created_idx",
            ),
            models.Index(
                fields=("business", "status"),
                name="integ_msg_bus_status_idx",
            ),
        ]

    def __str__(self):
        return f"{self.business.name} - {self.channel} - {self.status}"
