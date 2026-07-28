from django.contrib import admin

from .models import Product, StockMovement


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # Gives administrators a searchable, business-aware inventory view.

    list_display = (
        "name",
        "sku",
        "business",
        "product_type",
        "category",
        "stock",
        "unit",
        "selling_price",
        "is_active",
        "updated_at",
    )
    list_filter = (
        "product_type",
        "unit",
        "is_active",
        "business__business_type",
        "category",
    )
    search_fields = (
        "name",
        "sku",
        "category",
        "brand",
        "design_code",
        "style_code",
        "batch_number",
        "business__name",
        "business__owner__email",
    )
    ordering = (
        "business__name",
        "name",
    )
    list_select_related = (
        "business",
        "business__owner",
    )
    autocomplete_fields = ("business",)
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )
    list_per_page = 50

    fieldsets = (
        (
            "Business and product identity",
            {
                "fields": (
                    "id",
                    "business",
                    "product_type",
                    "name",
                    "sku",
                    "category",
                    "brand",
                    "is_active",
                )
            },
        ),
        (
            "Stock and pricing",
            {
                "fields": (
                    "unit",
                    "stock",
                    "low_stock_level",
                    "cost_price",
                    "selling_price",
                )
            },
        ),
        (
            "Shared size and colour",
            {
                "fields": (
                    "size",
                    "color",
                )
            },
        ),
        (
            "Tile details",
            {
                "fields": (
                    "design_code",
                    "finish",
                    "batch_number",
                    "pieces_per_box",
                    "sqm_per_box",
                    "loose_pieces",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Boutique details",
            {
                "fields": ("style_code",),
                "classes": ("collapse",),
            },
        ),
        (
            "System information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    # Provides a searchable, read-only inventory audit trail.

    list_display = (
        "created_at",
        "product_name",
        "business",
        "movement_type",
        "quantity",
        "previous_stock",
        "new_stock",
        "unit",
        "created_by_name",
    )
    list_filter = (
        "movement_type",
        "business__business_type",
        "business",
        "created_at",
    )
    search_fields = (
        "product_name",
        "product__sku",
        "product__design_code",
        "product__style_code",
        "reason",
        "created_by_name",
        "created_by__email",
        "business__name",
    )
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    list_select_related = (
        "business",
        "product",
        "created_by",
    )
    readonly_fields = (
        "id",
        "business",
        "product",
        "product_name",
        "unit",
        "movement_type",
        "quantity",
        "previous_stock",
        "new_stock",
        "reason",
        "created_by",
        "created_by_name",
        "created_at",
    )
    list_per_page = 50

    fieldsets = (
        (
            "Movement",
            {
                "fields": (
                    "id",
                    "business",
                    "product",
                    "product_name",
                    "movement_type",
                    "quantity",
                    "unit",
                )
            },
        ),
        (
            "Stock balance",
            {
                "fields": (
                    "previous_stock",
                    "new_stock",
                )
            },
        ),
        (
            "Audit information",
            {
                "fields": (
                    "reason",
                    "created_by",
                    "created_by_name",
                    "created_at",
                )
            },
        ),
    )

    def has_add_permission(self, request):
        # Stock history must be created only through controlled workflows.
        return False

    def has_delete_permission(self, request, obj=None):
        # Audit records must not be deleted from Django Admin.
        return False

