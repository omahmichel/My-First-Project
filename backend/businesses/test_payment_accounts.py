from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import (
    Business,
    BusinessMembership,
    BusinessPaymentAccount,
)


User = get_user_model()


class BusinessPaymentAccountSecurityTests(APITestCase):
    # Protects encrypted receiving-account storage and workspace isolation.

    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com",
            password="StrongPass123!",
            full_name="Owner User",
        )
        self.other_owner = User.objects.create_user(
            email="other@example.com",
            password="StrongPass123!",
            full_name="Other Owner",
        )
        self.cashier = User.objects.create_user(
            email="cashier@example.com",
            password="StrongPass123!",
            full_name="Cashier User",
        )

        self.business = Business.objects.create(
            owner=self.owner,
            name="Secure Shop",
            slug="secure-shop",
            business_type=Business.BusinessType.BOUTIQUE,
        )
        self.other_business = Business.objects.create(
            owner=self.other_owner,
            name="Other Shop",
            slug="other-shop",
            business_type=Business.BusinessType.BOUTIQUE,
        )
        BusinessMembership.objects.create(
            business=self.business,
            user=self.owner,
            role=BusinessMembership.Role.OWNER,
            is_active=True,
        )
        BusinessMembership.objects.create(
            business=self.other_business,
            user=self.other_owner,
            role=BusinessMembership.Role.OWNER,
            is_active=True,
        )
        BusinessMembership.objects.create(
            business=self.business,
            user=self.cashier,
            role=BusinessMembership.Role.CASHIER,
            is_active=True,
        )

    def list_url(self, business):
        return reverse(
            "business-payment-account-list-create",
            kwargs={"business_id": business.id},
        )

    def detail_url(self, business, account):
        return reverse(
            "business-payment-account-detail",
            kwargs={
                "business_id": business.id,
                "account_id": account.id,
            },
        )

    def create_bank_account(self, *, is_default=False):
        self.client.force_authenticate(user=self.owner)
        return self.client.post(
            self.list_url(self.business),
            {
                "accountType": "bank",
                "displayName": "Main GCB Account",
                "bankName": "GCB Bank",
                "accountName": "Secure Shop",
                "accountNumber": "123456789012",
                "isDefault": is_default,
            },
            format="json",
        )

    def test_owner_creates_encrypted_bank_account(self):
        response = self.create_bank_account()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["maskedNumber"], "••••9012")
        self.assertNotIn("accountNumber", response.data)

        account = BusinessPaymentAccount.objects.get(
            business=self.business
        )
        self.assertNotIn(
            "123456789012",
            account.encrypted_account_number,
        )
        self.assertEqual(
            account.get_account_number(),
            "123456789012",
        )

    def test_mobile_money_account_requires_network(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            self.list_url(self.business),
            {
                "accountType": "mobile_money",
                "displayName": "Shop MoMo",
                "accountName": "Secure Shop",
                "accountNumber": "0241234567",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("network", response.data)
        self.assertFalse(
            BusinessPaymentAccount.objects.filter(
                business=self.business
            ).exists()
        )

    def test_cashier_reads_active_accounts_but_cannot_create(self):
        create_response = self.create_bank_account()
        self.assertEqual(
            create_response.status_code,
            status.HTTP_201_CREATED,
        )

        self.client.force_authenticate(user=self.cashier)

        list_response = self.client.get(self.list_url(self.business))
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)
        self.assertEqual(
            list_response.data[0]["maskedNumber"],
            "••••9012",
        )

        create_denied = self.client.post(
            self.list_url(self.business),
            {
                "accountType": "bank",
                "displayName": "Forbidden",
                "bankName": "Other Bank",
                "accountName": "Cashier",
                "accountNumber": "998877665544",
            },
            format="json",
        )
        self.assertIn(
            create_denied.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
        )

    def test_account_cannot_be_managed_from_another_business(self):
        create_response = self.create_bank_account()
        account = BusinessPaymentAccount.objects.get(
            pk=create_response.data["id"]
        )

        self.client.force_authenticate(user=self.other_owner)
        response = self.client.patch(
            self.detail_url(self.other_business, account),
            {"displayName": "Cross-business edit"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        account.refresh_from_db()
        self.assertEqual(account.display_name, "Main GCB Account")

    def test_delete_soft_deactivates_financial_account(self):
        create_response = self.create_bank_account(is_default=True)
        account = BusinessPaymentAccount.objects.get(
            pk=create_response.data["id"]
        )

        response = self.client.delete(
            self.detail_url(self.business, account)
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        account.refresh_from_db()
        self.assertFalse(account.is_active)
        self.assertFalse(account.is_default)

    def test_only_one_active_default_account_per_business(self):
        first = self.create_bank_account(is_default=True)
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        response = self.client.post(
            self.list_url(self.business),
            {
                "accountType": "mobile_money",
                "displayName": "Default MoMo",
                "accountName": "Secure Shop",
                "network": "mtn",
                "accountNumber": "0241234567",
                "isDefault": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        defaults = BusinessPaymentAccount.objects.filter(
            business=self.business,
            is_active=True,
            is_default=True,
        )
        self.assertEqual(defaults.count(), 1)
        self.assertEqual(
            str(defaults.get().id),
            str(response.data["id"]),
        )
