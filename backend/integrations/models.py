import uuid

from django.conf import settings as django_settings
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
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_data_imports",
        blank=True,
        null=True,
    )
    applied_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
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


class ApiCredential(models.Model):
    """Business-scoped public API credential; the raw secret is never stored."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="api_credentials"
    )
    name = models.CharField(max_length=120)
    key_prefix = models.CharField(max_length=40, unique=True)
    secret_hash = models.CharField(max_length=64)
    scopes = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    revoked_at = models.DateTimeField(blank=True, null=True)
    last_used_at = models.DateTimeField(blank=True, null=True)
    created_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_stockflow_api_credentials",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "created_at")
        indexes = [
            models.Index(
                fields=("business", "is_active"),
                name="integ_api_bus_active_idx",
            )
        ]


class WebhookEndpoint(models.Model):
    """Business-owned HTTPS target for signed StockFlow events."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="webhook_endpoints"
    )
    name = models.CharField(max_length=120)
    url = models.URLField(max_length=500)
    events = models.JSONField(default=list, blank=True)
    secret_salt = models.CharField(max_length=64, default=uuid.uuid4)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_webhook_endpoints",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "created_at")
        indexes = [
            models.Index(
                fields=("business", "is_active"),
                name="integ_hook_bus_active_idx",
            )
        ]


class WebhookEvent(models.Model):
    """Immutable outbound event/outbox record."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="webhook_events"
    )
    event_type = models.CharField(max_length=60)
    source_type = models.CharField(max_length=80, blank=True)
    source_id = models.CharField(max_length=80, blank=True)
    dedupe_key = models.CharField(max_length=255, unique=True)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(
                fields=("business", "created_at"),
                name="integ_event_bus_created_idx",
            )
        ]


class WebhookDelivery(models.Model):
    """Audit/retry state for one event sent to one endpoint."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        WebhookEvent, on_delete=models.CASCADE, related_name="deliveries"
    )
    endpoint = models.ForeignKey(
        WebhookEndpoint, on_delete=models.CASCADE, related_name="deliveries"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    attempt_count = models.PositiveIntegerField(default=0)
    response_code = models.PositiveIntegerField(default=0)
    response_summary = models.TextField(blank=True)
    failure_reason = models.CharField(max_length=255, blank=True)
    claimed_at = models.DateTimeField(blank=True, null=True)
    last_attempt_at = models.DateTimeField(blank=True, null=True)
    next_attempt_at = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("event", "endpoint"),
                name="uniq_integ_webhook_event_endpoint",
            )
        ]
        indexes = [
            models.Index(
                fields=("status", "next_attempt_at"),
                name="integ_delivery_due_idx",
            )
        ]


class AccountingConnection(models.Model):
    """Provider-neutral accounting link; StockFlow stays authoritative."""

    class Provider(models.TextChoices):
        QUICKBOOKS = "quickbooks", "QuickBooks Online"
        XERO = "xero", "Xero"

    class Status(models.TextChoices):
        DISCONNECTED = "disconnected", "Disconnected"
        CONNECTED = "connected", "Connected"
        ERROR = "error", "Error"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="accounting_connections"
    )
    provider = models.CharField(max_length=30, choices=Provider.choices)
    name = models.CharField(max_length=120)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DISCONNECTED
    )
    external_company_id = models.CharField(max_length=160, blank=True)
    external_company_name = models.CharField(max_length=180, blank=True)
    settings = models.JSONField(default=dict, blank=True)
    last_synced_at = models.DateTimeField(blank=True, null=True)
    last_error = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_accounting_connections",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("provider", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("business", "provider", "name"),
                name="uniq_integ_account_conn_name",
            )
        ]


class AccountingExternalReference(models.Model):
    connection = models.ForeignKey(
        AccountingConnection,
        on_delete=models.CASCADE,
        related_name="external_references",
    )
    entity_type = models.CharField(max_length=40)
    stockflow_id = models.CharField(max_length=80)
    external_id = models.CharField(max_length=160)
    sync_hash = models.CharField(max_length=64, blank=True)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("connection", "entity_type", "stockflow_id"),
                name="uniq_integ_acct_stockflow_ref",
            ),
            models.UniqueConstraint(
                fields=("connection", "entity_type", "external_id"),
                name="uniq_integ_acct_external_ref",
            ),
        ]


class AccountingSyncRun(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connection = models.ForeignKey(
        AccountingConnection, on_delete=models.CASCADE, related_name="sync_runs"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.RUNNING
    )
    entity_type = models.CharField(max_length=40, blank=True)
    requested_count = models.PositiveIntegerField(default=0)
    synced_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    result = models.JSONField(default=dict, blank=True)
    error_message = models.CharField(max_length=500, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("-started_at",)
        indexes = [
            models.Index(
                fields=("connection", "started_at"),
                name="integ_sync_conn_start_idx",
            )
        ]


class CommerceConnection(models.Model):
    """Provider-neutral e-commerce connection. No provider secrets are stored."""

    class Provider(models.TextChoices):
        SHOPIFY = "shopify", "Shopify"
        WOOCOMMERCE = "woocommerce", "WooCommerce"

    class Status(models.TextChoices):
        DISCONNECTED = "disconnected", "Disconnected"
        CONNECTED = "connected", "Connected"
        ERROR = "error", "Error"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="commerce_connections",
    )
    provider = models.CharField(max_length=30, choices=Provider.choices)
    name = models.CharField(max_length=120)
    shop_url = models.URLField(max_length=500, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DISCONNECTED,
    )
    settings = models.JSONField(default=dict, blank=True)
    last_synced_at = models.DateTimeField(blank=True, null=True)
    last_error = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_commerce_connections",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("provider", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("business", "provider", "name"),
                name="uniq_integ_commerce_conn_name",
            )
        ]
        indexes = [
            models.Index(
                fields=("business", "status"),
                name="integ_com_bus_status_idx",
            )
        ]


class CommerceExternalReference(models.Model):
    """Maps StockFlow records to stable provider-side e-commerce identifiers."""

    connection = models.ForeignKey(
        CommerceConnection,
        on_delete=models.CASCADE,
        related_name="external_references",
    )
    entity_type = models.CharField(max_length=40)
    stockflow_id = models.CharField(max_length=80)
    external_id = models.CharField(max_length=180)
    sync_hash = models.CharField(max_length=64, blank=True)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("connection", "entity_type", "stockflow_id"),
                name="uniq_integ_com_stockflow_ref",
            ),
            models.UniqueConstraint(
                fields=("connection", "entity_type", "external_id"),
                name="uniq_integ_com_external_ref",
            ),
        ]
        indexes = [
            models.Index(
                fields=("connection", "entity_type"),
                name="integ_com_ref_type_idx",
            )
        ]


class CommerceSyncRun(models.Model):
    """Audits one provider-neutral commerce synchronization attempt."""

    class Direction(models.TextChoices):
        OUTBOUND = "outbound", "StockFlow to commerce"
        INBOUND = "inbound", "Commerce to StockFlow"

    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connection = models.ForeignKey(
        CommerceConnection,
        on_delete=models.CASCADE,
        related_name="sync_runs",
    )
    direction = models.CharField(max_length=20, choices=Direction.choices)
    entity_type = models.CharField(max_length=40)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RUNNING,
    )
    requested_count = models.PositiveIntegerField(default=0)
    synced_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    result = models.JSONField(default=dict, blank=True)
    error_message = models.CharField(max_length=500, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("-started_at",)
        indexes = [
            models.Index(
                fields=("connection", "started_at"),
                name="integ_com_sync_start_idx",
            )
        ]


class ExternalCommerceOrder(models.Model):
    """Normalized external order staged for review without mutating StockFlow."""

    class Status(models.TextChoices):
        STAGED = "staged", "Staged"
        READY = "ready", "Ready for review"
        BLOCKED = "blocked", "Blocked by missing mappings"
        REJECTED = "rejected", "Rejected"

    class PaymentStatus(models.TextChoices):
        UNKNOWN = "unknown", "Unknown"
        UNPAID = "unpaid", "Unpaid"
        PARTIAL = "partially_paid", "Partially paid"
        PAID = "paid", "Paid"
        REFUNDED = "refunded", "Refunded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="external_commerce_orders",
    )
    connection = models.ForeignKey(
        CommerceConnection,
        on_delete=models.CASCADE,
        related_name="external_orders",
    )
    external_order_id = models.CharField(max_length=180)
    external_order_number = models.CharField(max_length=120, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.STAGED,
    )
    payment_status = models.CharField(
        max_length=30,
        choices=PaymentStatus.choices,
        default=PaymentStatus.UNKNOWN,
    )
    currency = models.CharField(max_length=10, default="GHS")
    customer_name = models.CharField(max_length=180, blank=True)
    customer_email = models.EmailField(blank=True)
    customer_phone = models.CharField(max_length=40, blank=True)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    shipping_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    source_hash = models.CharField(max_length=64)
    source_summary = models.JSONField(default=dict, blank=True)
    staged_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="staged_external_commerce_orders",
        blank=True,
        null=True,
    )
    staged_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-staged_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("connection", "external_order_id"),
                name="uniq_integ_com_external_order",
            )
        ]
        indexes = [
            models.Index(
                fields=("business", "status", "staged_at"),
                name="integ_com_order_status_idx",
            )
        ]


class ExternalCommerceOrderItem(models.Model):
    """Normalized commerce line with optional StockFlow product mapping."""

    order = models.ForeignKey(
        ExternalCommerceOrder,
        on_delete=models.CASCADE,
        related_name="items",
    )
    external_item_id = models.CharField(max_length=180)
    external_product_id = models.CharField(max_length=180, blank=True)
    name = models.CharField(max_length=220)
    sku = models.CharField(max_length=120, blank=True)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    product = models.ForeignKey(
        "inventory.Product",
        on_delete=models.PROTECT,
        related_name="external_commerce_order_items",
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(
                fields=("order", "external_item_id"),
                name="uniq_integ_com_order_item",
            )
        ]


class SupplierPurchaseOrder(models.Model):
    """Pre-receipt supplier order that becomes stock only through restocking."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ISSUED = "issued", "Issued"
        PARTIALLY_RECEIVED = "partially_received", "Partially received"
        RECEIVED = "received", "Received"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="supplier_purchase_orders",
    )
    branch = models.ForeignKey(
        "businesses.Branch",
        on_delete=models.PROTECT,
        related_name="supplier_purchase_orders",
    )
    supplier = models.ForeignKey(
        "inventory.Supplier",
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )
    po_number = models.CharField(max_length=40, unique=True)
    supplier_reference = models.CharField(max_length=120, blank=True)
    order_date = models.DateField()
    expected_date = models.DateField(blank=True, null=True)
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    notes = models.CharField(max_length=500, blank=True)
    issued_at = models.DateTimeField(blank=True, null=True)
    created_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_supplier_purchase_orders",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-order_date", "-created_at")
        indexes = [
            models.Index(
                fields=("business", "status", "order_date"),
                name="integ_spo_bus_status_idx",
            ),
            models.Index(
                fields=("supplier", "order_date"),
                name="integ_spo_supplier_idx",
            ),
        ]


class SupplierPurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(
        SupplierPurchaseOrder,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        "inventory.Product",
        on_delete=models.PROTECT,
        related_name="supplier_purchase_order_items",
    )
    product_name = models.CharField(max_length=220)
    sku = models.CharField(max_length=120, blank=True)
    unit = models.CharField(max_length=40, blank=True)
    quantity_ordered = models.PositiveIntegerField()
    quantity_received = models.PositiveIntegerField(default=0)
    unit_cost = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(
                fields=("purchase_order", "product"),
                name="uniq_integ_spo_product",
            )
        ]


class SupplierPurchaseOrderReceipt(models.Model):
    """Idempotent link between a PO receipt action and a RestockPurchase."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase_order = models.ForeignKey(
        SupplierPurchaseOrder,
        on_delete=models.CASCADE,
        related_name="receipts",
    )
    idempotency_key = models.CharField(max_length=128)
    restock_purchase_id = models.CharField(max_length=80)
    received_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="received_supplier_purchase_orders",
        blank=True,
        null=True,
    )
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("received_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("purchase_order", "idempotency_key"),
                name="uniq_integ_spo_receipt_key",
            )
        ]

