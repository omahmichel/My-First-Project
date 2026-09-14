from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from django.urls import path
from .models import IntelligenceSnapshot, ForecastRun, BusinessInsight, GeneratedReport, AutomationEvent, AutomationRun

OPERATIONAL_NOTICES = (
    ("Data verification", "Sales, inventory, debt and profitability figures come from StockFlow business records. Django calculates the figures; optional AI narratives explain them without replacing the totals."),
    ("Read-only analyst", "Ask StockFlow cannot change business records. Evidence and confidence must remain available when interpreting forecasts and recommendations."),
    ("Recommendations", "Recommendations are advisory. Consequential business actions require explicit user confirmation."),
    ("Automation worker", "Due rules are processed by the StockFlow management command. No Redis, Celery or third-party scheduler is required. Running the web server alone does not schedule these rules."),
    ("Automation boundaries", "Automation may refresh recommendations, create advisory events and generate reports. It must not silently alter inventory, prices, sales, customer debt, supplier balances or payments."),
    ("Documents", "PDF downloads use GHS for reliable document rendering."),
    ("Notification access", "Notification queries require authenticated active business membership, current subscription access and an authorized branch. Intelligence events are limited to owners and managers. Read acknowledgements belong to one user and business."),
)


def operational_notices(request):
    if not (request.user.is_superuser or request.user.has_perm("intelligence.view_forecastrun")):
        raise PermissionDenied
    return TemplateResponse(request, "admin/intelligence/operational_notices.html", {
        **admin.site.each_context(request), "title": "StockFlow operational notices",
        "notices": OPERATIONAL_NOTICES,
    })


_original_admin_urls = admin.site.get_urls

def intelligence_admin_urls():
    return [path("intelligence/operational-notices/", admin.site.admin_view(operational_notices), name="intelligence-operational-notices")] + _original_admin_urls()

admin.site.get_urls = intelligence_admin_urls


class IntelligenceAuditAdmin(admin.ModelAdmin):
    change_list_template = "admin/intelligence/audit_change_list.html"
    list_filter = ("business",)
    actions = None

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

for model in (IntelligenceSnapshot, ForecastRun, BusinessInsight, GeneratedReport, AutomationEvent, AutomationRun):
    admin.site.register(model, IntelligenceAuditAdmin)
