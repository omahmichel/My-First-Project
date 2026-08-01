from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from businesses.models import Business, BusinessMembership


class BusinessSubscriptionAccessTests(APITestCase):
    """Protects operational APIs after trial or subscription expiry."""

    def setUp(self):
        # Creates an owner, staff member and one expired business.
        self.owner = User.objects.create_user(
            email="expired.owner@stockflow.test",
            password="StrongPass123!",
            full_name="Expired Owner",
        )
        self.cashier = User.objects.create_user(
            email="expired.cashier@stockflow.test",
            password="StrongPass123!",
            full_name="Expired Cashier",
        )
        self.business = Business.objects.create(
            owner=self.owner,
            name="Expired StockFlow Shop",
            slug="expired-stockflow-shop",
            business_type=Business.BusinessType.BUILDING_MATERIALS,
            trial_started_at=timezone.now() - timedelta(days=61),
            trial_ends_at=timezone.now() - timedelta(days=1),
        )
        BusinessMembership.objects.create(
            business=self.business,
            user=self.cashier,
            role=BusinessMembership.Role.CASHIER,
            is_active=True,
        )

        base = f"/api/businesses/{self.business.id}"
        self.business_detail_url = (
            f"/api/businesses/{self.business.id}/"
        )
        self.operational_urls = (
            f"{base}/customers/",
            f"{base}/products/",
            f"{base}/sales/",
            f"{base}/team/",
        )

    def authenticate(self, user):
        # Authenticates directly without depending on login flows.
        self.client.force_authenticate(user=user)

    def test_expired_owner_can_still_read_business_details(self):
        # Subscription details remain visible so the owner can renew.
        self.authenticate(self.owner)

        response = self.client.get(self.business_detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["hasSystemAccess"])

    def test_expired_owner_is_blocked_from_operational_apis(self):
        # All operational APIs return one consistent subscription error.
        self.authenticate(self.owner)

        for url in self.operational_urls:
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(
                    response.status_code,
                    status.HTTP_403_FORBIDDEN,
                    response.data,
                )
                self.assertEqual(
                    response.data["code"],
                    "subscription_required",
                )

    def test_expired_staff_member_is_also_blocked(self):
        # Staff cannot bypass the business subscription requirement.
        self.authenticate(self.cashier)
        products_url = (
            f"/api/businesses/{self.business.id}/products/"
        )

        response = self.client.get(products_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            response.data["code"],
            "subscription_required",
        )

    def test_paid_subscription_restores_operational_access(self):
        # A current paid subscription restores normal API access.
        self.business.subscription_status = (
            Business.SubscriptionStatus.ACTIVE
        )
        self.business.subscription_started_at = timezone.now()
        self.business.subscription_ends_at = (
            timezone.now() + timedelta(days=30)
        )
        self.business.save(
            update_fields=(
                "subscription_status",
                "subscription_started_at",
                "subscription_ends_at",
            )
        )
        self.authenticate(self.owner)

        response = self.client.get(
            f"/api/businesses/{self.business.id}/products/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
