from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Business, BusinessMembership


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    STOCKFLOW_SUPPORT_EMAIL="stockflowghana@gmail.com",
)
class SupportIssueReportTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            email="owner-support@example.com",
            password="StrongSupportPass123!",
            full_name="Support Owner",
        )
        self.cashier = user_model.objects.create_user(
            email="cashier-support@example.com",
            password="StrongSupportPass123!",
            full_name="Support Cashier",
        )
        self.outsider = user_model.objects.create_user(
            email="outsider-support@example.com",
            password="StrongSupportPass123!",
            full_name="Outside User",
        )

        self.business = Business.objects.create(
            owner=self.owner,
            name="Support Test Business",
            slug="support-test-business",
            business_type=Business.BusinessType.BOUTIQUE,
            trial_started_at=timezone.now() - timedelta(days=61),
            trial_ends_at=timezone.now() - timedelta(days=1),
        )
        BusinessMembership.objects.create(
            business=self.business,
            user=self.cashier,
            role=BusinessMembership.Role.CASHIER,
            is_active=True,
        )

        self.url = (
            f"/api/businesses/{self.business.id}/support/issues/"
        )
        self.payload = {
            "category": "inventory",
            "subject": "Stock quantity is not updating",
            "description": (
                "The quantity shown after saving a stock change does not "
                "match the value I entered."
            ),
        }

    def test_owner_can_report_issue_after_subscription_expiry(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(
            message.to,
            ["stockflowghana@gmail.com"],
        )
        self.assertEqual(
            message.reply_to,
            [self.owner.email],
        )
        self.assertIn(self.business.name, message.body)
        self.assertIn(self.owner.email, message.body)
        self.assertIn("Stock quantity is not updating", message.body)

    def test_staff_member_can_report_issue_after_subscription_expiry(self):
        self.client.force_authenticate(user=self.cashier)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.cashier.email, mail.outbox[0].body)
        self.assertIn(
            BusinessMembership.Role.CASHIER,
            mail.outbox[0].body,
        )

    def test_outsider_cannot_report_against_business(self):
        self.client.force_authenticate(user=self.outsider)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(len(mail.outbox), 0)

    def test_issue_report_validates_required_content(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            self.url,
            {
                "category": "general",
                "subject": "Bad",
                "description": "Too short",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(len(mail.outbox), 0)
