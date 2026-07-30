from django.contrib import admin

from .models import Business, BusinessMembership


class BusinessMembershipInline(admin.TabularInline):
    """Lets administrators review a business team from the business page."""

    model = BusinessMembership
    extra = 0
    autocomplete_fields = ("user",)
    fields = (
        "user",
        "role",
        "is_active",
        "last_active_at",
        "joined_at",
    )
    readonly_fields = ("joined_at",)
    show_change_link = True


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    """Manages business workspaces and their owners."""

    list_display = (
        "name",
        "business_type",
        "owner",
        "status",
        "phone",
        "created_at",
    )
    list_filter = (
        "business_type",
        "status",
        "created_at",
    )
    search_fields = (
        "name",
        "slug",
        "owner__email",
        "owner__full_name",
        "phone",
        "email",
        "location",
    )
    ordering = ("name",)
    autocomplete_fields = ("owner",)
    readonly_fields = ("created_at", "updated_at")
    prepopulated_fields = {"slug": ("name",)}
    inlines = (BusinessMembershipInline,)

    fieldsets = (
        (
            "Business details",
            {
                "fields": (
                    "name",
                    "slug",
                    "business_type",
                    "status",
                )
            },
        ),
        (
            "Ownership",
            {
                "fields": ("owner",)
            },
        ),
        (
            "Contact information",
            {
                "fields": (
                    "phone",
                    "email",
                    "location",
                )
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


@admin.register(BusinessMembership)
class BusinessMembershipAdmin(admin.ModelAdmin):
    """Manages staff access and roles inside each business."""

    list_display = (
        "user",
        "business",
        "role",
        "is_active",
        "last_active_at",
        "joined_at",
    )
    list_filter = (
        "role",
        "is_active",
        "business__business_type",
        "joined_at",
    )
    search_fields = (
        "user__email",
        "user__full_name",
        "business__name",
    )
    ordering = (
        "business__name",
        "user__email",
    )
    autocomplete_fields = (
        "business",
        "user",
    )
    readonly_fields = (
        "joined_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Membership",
            {
                "fields": (
                    "business",
                    "user",
                    "role",
                    "is_active",
                )
            },
        ),
        (
            "Activity",
            {
                "fields": (
                    "last_active_at",
                    "joined_at",
                    "updated_at",
                )
            },
        ),
    )
