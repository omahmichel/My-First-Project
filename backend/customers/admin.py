from django.contrib import admin

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    # Gives administrators a searchable, business-aware customer view.

    list_display = (
        "name",
        "phone",
        "business",
        "outstanding_balance",
        "total_purchases",
        "is_active",
        "created_at",
    )
    list_filter = (
        "is_active",
        "business__business_type",
        "business",
        "created_at",
    )
    search_fields = (
        "name",
        "phone",
        "email",
        "address",
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
        "created_by",
    )
    autocomplete_fields = (
        "business",
        "created_by",
    )
    readonly_fields = (
        "id",
        "outstanding_balance",
        "total_purchases",
        "created_at",
        "updated_at",
    )
    list_per_page = 50

    fieldsets = (
        (
            "Business and customer",
            {
                "fields": (
                    "id",
                    "business",
                    "name",
                    "phone",
                    "email",
                    "address",
                    "is_active",
                )
            },
        ),
        (
            "Account summary",
            {
                "fields": (
                    "outstanding_balance",
                    "total_purchases",
                )
            },
        ),
        (
            "Audit information",
            {
                "fields": (
                    "created_by",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )
