from uuid import UUID
from django.db.models import F
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView
from businesses.access import get_business_and_role_for_user
from businesses.branch_access import resolve_branch_for_user
from businesses.models import BusinessMembership
from inventory.models import BranchInventory
from intelligence.models import AutomationEvent
from .models import NotificationRead


class NotificationThrottle(UserRateThrottle):
    rate = "120/min"
    scope = "stockflow_notifications"


def notification_scope(request, business_id):
    business, role = get_business_and_role_for_user(user=request.user, business_id=business_id)
    branch_id = request.query_params.get("branchId")
    if branch_id:
        try:
            UUID(branch_id)
        except (ValueError, TypeError, AttributeError):
            raise ValidationError({"branchId": "Choose a valid branch."})
    branch = resolve_branch_for_user(business=business, user=request.user, role=role, branch_id=branch_id)
    return business, role, branch


def notification_feed(business, role, branch):
    """Read live branch alerts; never emit financial data to non-management roles."""
    rows = BranchInventory.objects.filter(
        branch=branch, product__business=business, product__is_active=True,
        stock__lte=F("reserved_stock") + F("low_stock_level"),
    ).select_related("product").order_by("-updated_at", "id")[:30]
    items = []
    for row in rows:
        available = row.available_stock
        items.append({
            "id": f"stock:{row.id}:{row.updated_at.isoformat()}",
            "title": "Out of stock" if available == 0 else "Low stock",
            "message": f"{row.product.name}: {available} {row.product.unit}(s) available at {branch.name}.",
            "createdAt": row.updated_at.isoformat(),
            "href": "/app/products",
        })
    if role in (BusinessMembership.Role.OWNER, BusinessMembership.Role.MANAGER):
        events = AutomationEvent.objects.filter(business=business).order_by("-generated_at", "id")[:30]
        for event in events:
            items.append({
                "id": f"event:{event.id}", "title": event.title,
                "message": event.summary, "createdAt": event.generated_at.isoformat(),
                "href": "/intelligence/automation",
            })
    return sorted(items, key=lambda item: (item["createdAt"], item["id"]), reverse=True)[:30]


class NotificationCollectionAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    throttle_classes = (NotificationThrottle,)

    def get(self, request, business_id):
        business, role, branch = notification_scope(request, business_id)
        items = notification_feed(business, role, branch)
        read_keys = set(NotificationRead.objects.filter(
            business=business, user=request.user,
            notification_key__in=[item["id"] for item in items],
        ).values_list("notification_key", flat=True))
        for item in items:
            item["read"] = item["id"] in read_keys
        response = Response({"items": items, "unreadCount": sum(not item["read"] for item in items), "limit": 30})
        response["Cache-Control"] = "no-store"
        return response


class NotificationReadAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    throttle_classes = (NotificationThrottle,)

    def post(self, request, business_id):
        business, role, branch = notification_scope(request, business_id)
        keys = request.data.get("ids")
        if not isinstance(keys, list) or not 1 <= len(keys) <= 30 or any(not isinstance(key, str) for key in keys):
            raise ValidationError({"ids": "Choose between 1 and 30 notifications."})
        allowed = {item["id"] for item in notification_feed(business, role, branch)}
        if not set(keys).issubset(allowed):
            raise ValidationError({"ids": "These notifications have changed. Refresh and try again."})
        NotificationRead.objects.bulk_create([
            NotificationRead(business=business, user=request.user, notification_key=key)
            for key in set(keys)
        ], ignore_conflicts=True)
        response = Response({"readIds": keys})
        response["Cache-Control"] = "no-store"
        return response
