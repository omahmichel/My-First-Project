from django.contrib import admin

from .models import (
    DebtOverdueCharge,
    DebtReminderAttempt,
    DebtReminderSchedule,
    DocumentSequence,
    Payment,
    Sale,
    SaleItem,
)


class ReadOnlyAuditAdminMixin:
    # Keeps financial and numbering records view-only in Django Admin.

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return tuple(
            field.name
            for field in self.model._meta.fields
        )


class SaleItemInline(admin.TabularInline):
    # Shows immutable sale-line snapshots inside the related sale.

    model = SaleItem
    extra = 0
    can_delete = False
    show_change_link = True
    fields = (
        "product_name",
        "sku",
        "design_code",
        "quantity",
        "unit",
        "unit_price",
        "cost_price",
        "line_total",
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Sale)
class SaleAdmin(ReadOnlyAuditAdminMixin, admin.ModelAdmin):
    # Provides a searchable, business-aware audit view of sales.

    list_display = (
        "sale_number",
        "invoice_number",
        "business",
        "customer_name",
        "payment_method",
        "status",
        "total",
        "amount_paid",
        "outstanding_balance",
        "cashier_name",
        "created_at",
    )
    list_filter = (
        "status",
        "payment_method",
        "business__business_type",
        "business",
        "created_at",
    )
    search_fields = (
        "sale_number",
        "invoice_number",
        "customer_name",
        "customer_phone",
        "cashier_name",
        "business__name",
    )
    list_select_related = (
        "business",
        "customer",
        "cashier",
    )
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    list_per_page = 50
    inlines = (SaleItemInline,)


@admin.register(SaleItem)
class SaleItemAdmin(ReadOnlyAuditAdminMixin, admin.ModelAdmin):
    # Exposes historical product and pricing snapshots for auditing.

    list_display = (
        "product_name",
        "sku",
        "sale",
        "quantity",
        "unit",
        "unit_price",
        "cost_price",
        "line_total",
    )
    list_filter = (
        "sale__business",
        "unit",
    )
    search_fields = (
        "product_name",
        "sku",
        "design_code",
        "sale__sale_number",
        "sale__invoice_number",
    )
    list_select_related = (
        "sale",
        "sale__business",
        "product",
    )
    ordering = ("sale__created_at",)
    list_per_page = 50


@admin.register(Payment)
class PaymentAdmin(ReadOnlyAuditAdminMixin, admin.ModelAdmin):
    # Provides a protected audit view of all payment attempts and receipts.

    list_display = (
        "receipt_number",
        "business",
        "sale",
        "customer",
        "payment_type",
        "method",
        "status",
        "amount",
        "mobile_money_network",
        "gateway",
        "initiated_by_name",
        "created_at",
    )
    list_filter = (
        "status",
        "method",
        "payment_type",
        "mobile_money_network",
        "gateway",
        "business",
        "created_at",
    )
    search_fields = (
        "receipt_number",
        "gateway_reference",
        "provider_reference",
        "mobile_money_number",
        "reference",
        "initiated_by_name",
        "sale__sale_number",
        "sale__invoice_number",
        "customer__name",
        "business__name",
    )
    list_select_related = (
        "business",
        "sale",
        "customer",
        "initiated_by",
    )
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    list_per_page = 50


@admin.register(DebtOverdueCharge)
class DebtOverdueChargeAdmin(
    ReadOnlyAuditAdminMixin,
    admin.ModelAdmin,
):
    # Provides a protected audit trail of overdue tier changes.

    list_display = (
        "sale",
        "business",
        "customer",
        "tier_percentage",
        "principal_base",
        "total_charge_required",
        "incremental_amount",
        "applied_at",
    )
    list_filter = (
        "tier_percentage",
        "business",
        "applied_at",
    )
    search_fields = (
        "sale__sale_number",
        "sale__invoice_number",
        "customer__name",
        "business__name",
    )
    list_select_related = (
        "business",
        "customer",
        "sale",
    )
    ordering = ("-applied_at",)
    date_hierarchy = "applied_at"
    list_per_page = 50


@admin.register(DebtReminderSchedule)
class DebtReminderScheduleAdmin(
    ReadOnlyAuditAdminMixin,
    admin.ModelAdmin,
):
    # Shows each deterministic reminder slot and its final state.

    list_display = (
        "sale",
        "business",
        "customer",
        "scheduled_for",
        "reminder_sequence_number",
        "status",
        "last_attempted_at",
    )
    list_filter = (
        "status",
        "business",
        "scheduled_for",
    )
    search_fields = (
        "sale__sale_number",
        "sale__invoice_number",
        "customer__name",
        "business__name",
    )
    list_select_related = (
        "business",
        "customer",
        "sale",
    )
    ordering = ("-scheduled_for", "-created_at")
    date_hierarchy = "scheduled_for"
    list_per_page = 50


@admin.register(DebtReminderAttempt)
class DebtReminderAttemptAdmin(
    ReadOnlyAuditAdminMixin,
    admin.ModelAdmin,
):
    # Shows every send, retry, failure, and safe reminder skip.

    list_display = (
        "schedule",
        "sale",
        "business",
        "customer",
        "attempt_number",
        "status",
        "provider",
        "attempted_at",
    )
    list_filter = (
        "status",
        "provider",
        "business",
        "attempted_at",
    )
    search_fields = (
        "sale__sale_number",
        "sale__invoice_number",
        "customer__name",
        "recipient_snapshot",
        "provider_reference",
        "failure_reason",
        "business__name",
    )
    list_select_related = (
        "schedule",
        "business",
        "customer",
        "sale",
    )
    ordering = ("-attempted_at",)
    date_hierarchy = "attempted_at"
    list_per_page = 50


@admin.register(DocumentSequence)
class DocumentSequenceAdmin(
    ReadOnlyAuditAdminMixin,
    admin.ModelAdmin,
):
    # Shows protected counters used for unique document numbers.

    list_display = (
        "business",
        "next_sale_number",
        "next_invoice_number",
        "next_receipt_number",
        "updated_at",
    )
    search_fields = ("business__name",)
    list_select_related = ("business",)
    ordering = ("business__name",)
