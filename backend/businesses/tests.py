from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Business, BusinessMembership

User = get_user_model()


class BusinessSubscriptionFoundationTests(APITestCase):
    """Protects trial creation, reminders, expiry and paid access."""

    def setUp(self):
        # Creates one authenticated owner for business API tests.
        self.owner = User.objects.create_user(
            email="owner@stockflow.test",
            password="StrongPass123!",
            full_name="StockFlow Owner",
        )
        self.client.force_authenticate(user=self.owner)
        self.url = reverse("business-list")

    def create_business(self, **overrides):
        # Creates one business through the real API workflow.
        payload = {
            "name": "Trial Business",
            "business_type": Business.BusinessType.BUILDING_MATERIALS,
            "phone": "0240000000",
            "email": "business@stockflow.test",
            "location": "Accra",
        }
        payload.update(overrides)
        return self.client.post(self.url, payload, format="json")

    def test_new_business_receives_sixty_day_trial(self):
        # New workspaces receive owner membership and full trial access.
        response = self.create_business()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        business = Business.objects.get(pk=response.data["id"])
        trial_length = business.trial_ends_at - business.trial_started_at

        self.assertEqual(
            business.subscription_status,
            Business.SubscriptionStatus.TRIAL,
        )
        self.assertGreaterEqual(trial_length, timedelta(days=59, hours=23))
        self.assertLessEqual(trial_length, timedelta(days=60, minutes=1))
        self.assertTrue(business.is_trial_active)
        self.assertTrue(business.has_system_access)
        self.assertFalse(business.subscription_reminder_due)
        self.assertEqual(response.data["trialDaysRemaining"], 60)
        self.assertTrue(response.data["isTrialActive"])
        self.assertTrue(response.data["hasSystemAccess"])
        self.assertTrue(
            BusinessMembership.objects.filter(
                business=business,
                user=self.owner,
                role=BusinessMembership.Role.OWNER,
                is_active=True,
            ).exists()
        )

    def test_reminder_begins_in_final_fifteen_days(self):
        # Day 45 starts reminders without blocking normal access.
        business = Business.objects.create(
            owner=self.owner,
            name="Reminder Business",
            slug="reminder-business",
            business_type=Business.BusinessType.BOUTIQUE,
            trial_started_at=timezone.now() - timedelta(days=45),
            trial_ends_at=timezone.now() + timedelta(days=15),
        )
        self.assertTrue(business.subscription_reminder_due)
        self.assertTrue(business.has_system_access)

    def test_expired_trial_is_restored_by_paid_subscription(self):
        # Expiry blocks access until a current paid subscription exists.
        business = Business.objects.create(
            owner=self.owner,
            name="Expired Business",
            slug="expired-business",
            business_type=Business.BusinessType.BOUTIQUE,
            trial_started_at=timezone.now() - timedelta(days=61),
            trial_ends_at=timezone.now() - timedelta(days=1),
        )
        self.assertFalse(business.has_system_access)

        business.subscription_status = Business.SubscriptionStatus.ACTIVE
        business.subscription_started_at = timezone.now()
        business.subscription_ends_at = timezone.now() + timedelta(days=30)
        business.save(
            update_fields=(
                "subscription_status",
                "subscription_started_at",
                "subscription_ends_at",
            )
        )
        self.assertTrue(business.has_active_subscription)
        self.assertTrue(business.has_system_access)

    def test_clients_cannot_forge_subscription_access(self):
        # Request data cannot activate or extend subscriptions.
        forged_end = timezone.now() + timedelta(days=365)
        response = self.create_business(
            subscription_status=Business.SubscriptionStatus.ACTIVE,
            subscription_ends_at=forged_end.isoformat(),
            trial_ends_at=forged_end.isoformat(),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        business = Business.objects.get(pk=response.data["id"])
        self.assertEqual(
            business.subscription_status,
            Business.SubscriptionStatus.TRIAL,
        )
        self.assertIsNone(business.subscription_ends_at)
        self.assertLess(
            business.trial_ends_at,
            timezone.now() + timedelta(days=61),
        )
