import logging

from django.conf import settings
from django.core.mail import EmailMessage
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import Business, BusinessMembership


logger = logging.getLogger(__name__)


ISSUE_CATEGORY_CHOICES = (
    ("general", "General issue"),
    ("inventory", "Inventory or stock"),
    ("sales", "Sales"),
    ("invoice_document", "Invoice, receipt or waybill"),
    ("customer", "Customer records"),
    ("payment_subscription", "Payment or subscription"),
    ("account_login", "Account or login"),
    ("performance", "Performance or loading"),
    ("data_issue", "Incorrect or missing data"),
    ("other", "Other"),
)
ISSUE_CATEGORY_LABELS = dict(ISSUE_CATEGORY_CHOICES)


class SupportIssueReportSerializer(serializers.Serializer):
    category = serializers.ChoiceField(choices=ISSUE_CATEGORY_CHOICES)
    subject = serializers.CharField(
        min_length=5,
        max_length=120,
        trim_whitespace=True,
    )
    description = serializers.CharField(
        min_length=10,
        max_length=5000,
        trim_whitespace=True,
    )

    def validate_subject(self, value):
        # Prevents user-controlled mail headers from containing line breaks.
        if "\n" in value or "\r" in value:
            raise serializers.ValidationError(
                "Subject cannot contain line breaks."
            )
        return value


def get_support_business_and_role(*, user, business_id):
    """
    Resolves support access without requiring a current subscription.

    This intentionally does not call the operational subscription guard:
    users must be able to report a problem even when their workspace is
    expired. Business ownership/membership is still enforced.
    """
    membership_filter = Q(
        memberships__user=user,
        memberships__is_active=True,
    )
    business = get_object_or_404(
        Business.objects.filter(
            Q(owner=user) | membership_filter,
            status=Business.Status.ACTIVE,
        )
        .select_related("owner")
        .distinct(),
        pk=business_id,
    )

    if business.owner_id == user.id:
        return business, BusinessMembership.Role.OWNER

    membership = get_object_or_404(
        BusinessMembership,
        business=business,
        user=user,
        is_active=True,
    )
    return business, membership.role


class SupportIssueReportAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "support_issue_report"

    def post(self, request, business_id):
        business, role = get_support_business_and_role(
            user=request.user,
            business_id=business_id,
        )

        serializer = SupportIssueReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        category_label = ISSUE_CATEGORY_LABELS[payload["category"]]
        submitted_at = timezone.localtime().strftime(
            "%Y-%m-%d %H:%M:%S %Z"
        )

        body = (
            "A StockFlow user reported an issue.\n\n"
            f"Category: {category_label}\n"
            f"Subject: {payload['subject']}\n\n"
            "Reporter\n"
            f"Name: {request.user.full_name or 'Not provided'}\n"
            f"Email: {request.user.email}\n"
            f"User ID: {request.user.pk}\n\n"
            "Business workspace\n"
            f"Business: {business.name}\n"
            f"Business ID: {business.id}\n"
            f"Business type: {business.get_business_type_display()}\n"
            f"Role: {role}\n"
            f"Subscription access active: {business.has_system_access}\n\n"
            f"Submitted: {submitted_at}\n\n"
            "Issue description\n"
            "-----------------\n"
            f"{payload['description']}\n"
        )

        message = EmailMessage(
            subject=(
                f"[StockFlow Support] {category_label}: "
                f"{payload['subject']}"
            ),
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[settings.STOCKFLOW_SUPPORT_EMAIL],
            reply_to=(
                [request.user.email]
                if request.user.email
                else None
            ),
        )

        try:
            message.send(fail_silently=False)
        except Exception:
            logger.exception(
                "StockFlow support email delivery failed for user=%s "
                "business=%s",
                request.user.pk,
                business.pk,
            )
            return Response(
                {
                    "detail": (
                        "Your report could not be delivered right now. "
                        "Please try again shortly."
                    ),
                    "code": "support_email_unavailable",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "detail": (
                    "Your report has been sent. We'll respond as "
                    "quickly as possible."
                )
            },
            status=status.HTTP_201_CREATED,
        )
