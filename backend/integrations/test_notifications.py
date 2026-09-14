from datetime import timedelta
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase
from accounts.models import User
from businesses.models import Business, BusinessMembership, Branch, BranchAccess
from inventory.models import Product, BranchInventory
from intelligence.models import AutomationEvent
from integrations.models import NotificationRead


class NotificationTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email="owner@notification.test", password="test-password")
        self.other = User.objects.create_user(email="other@notification.test", password="test-password")
        self.staff = User.objects.create_user(email="cashier@notification.test", password="test-password")
        self.business = Business.objects.create(owner=self.owner, name="Main business", slug="notification-main", business_type="building_materials")
        self.foreign = Business.objects.create(owner=self.other, name="Other business", slug="notification-other", business_type="building_materials")
        self.branch = Branch.objects.create(business=self.business, name="Main", code="MAIN", is_main=True)
        self.second = Branch.objects.create(business=self.business, name="Second", code="SECOND")
        self.foreign_branch = Branch.objects.create(business=self.foreign, name="Other", code="MAIN", is_main=True)
        membership = BusinessMembership.objects.create(business=self.business, user=self.staff, role="cashier")
        BranchAccess.objects.create(membership=membership, branch=self.branch)
        self.stock = self.make_stock(self.business, self.branch, "Product A")
        self.make_stock(self.business, self.second, "Product B")
        self.make_stock(self.foreign, self.foreign_branch, "Secret product")
        self.event = AutomationEvent.objects.create(business=self.business, event_type="customer_debt", title="Management only", summary="Debt requires attention", dedupe_key="notification-test")
        self.url = reverse("integrations:notifications", args=[self.business.id]) + "?branchId=" + str(self.branch.id)
        self.read_url = reverse("integrations:notifications-read", args=[self.business.id]) + "?branchId=" + str(self.branch.id)
        self.client.force_authenticate(self.owner)

    def make_stock(self, business, branch, name):
        product = Product.objects.create(business=business, name=name, sku=name, category="Tiles", unit="box", stock=1, low_stock_level=3)
        return BranchInventory.objects.create(branch=branch, product=product, stock=1, low_stock_level=3)

    def test_authentication_required(self):
        self.client.force_authenticate(None)
        self.assertIn(self.client.get(self.url).status_code, (401, 403))

    def test_other_business_and_branch_denied(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.client.force_authenticate(self.owner)
        url = self.url.split("?")[0] + "?branchId=" + str(self.foreign_branch.id)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(self.url.split("?")[0] + "?branchId=broken").status_code, 400)

    def test_feed_scoped_and_management_events_hidden_from_cashier(self):
        data = self.client.get(self.url).data
        self.assertEqual(len(data["items"]), 2)
        self.assertNotIn("Product B", str(data))
        self.assertNotIn("Secret product", str(data))
        self.client.force_authenticate(self.staff)
        data = self.client.get(self.url).data
        self.assertEqual(len(data["items"]), 1)
        self.assertNotIn("Management only", str(data))
        url = self.url.split("?")[0] + "?branchId=" + str(self.second.id)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_read_state_is_per_user_and_idempotent(self):
        key = next(item["id"] for item in self.client.get(self.url).data["items"] if item["id"].startswith("stock:"))
        for _ in range(2):
            self.assertEqual(self.client.post(self.read_url, {"ids": [key]}, format="json").status_code, 200)
        self.assertEqual(NotificationRead.objects.count(), 1)
        self.assertEqual(self.client.get(self.url).data["unreadCount"], 1)
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.get(self.url).data["unreadCount"], 1)

    def test_read_rejects_foreign_and_management_keys(self):
        self.assertEqual(self.client.post(self.read_url, {"ids": ["event:foreign"]}, format="json").status_code, 400)
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.post(self.read_url, {"ids": [f"event:{self.event.id}"]}, format="json").status_code, 400)
        self.assertEqual(NotificationRead.objects.count(), 0)

    def test_limit_and_read_do_not_filter_a_sliced_queryset(self):
        for i in range(35):
            AutomationEvent.objects.create(business=self.business, event_type="recommendation", title=str(i), summary="Action", dedupe_key=f"test-{i}")
        data = self.client.get(self.url).data
        self.assertEqual(len(data["items"]), 30)
        keys = [item["id"] for item in data["items"]]
        self.assertEqual(self.client.post(self.read_url, {"ids": keys}, format="json").status_code, 200)
        self.assertEqual(self.client.get(self.url).data["unreadCount"], 0)

    def test_restock_removes_alert_and_new_stock_change_is_unread(self):
        key = next(item["id"] for item in self.client.get(self.url).data["items"] if item["id"].startswith("stock:"))
        self.client.post(self.read_url, {"ids": [key]}, format="json")
        self.stock.stock = 10
        self.stock.save()
        self.assertEqual(len(self.client.get(self.url).data["items"]), 1)
        self.stock.stock = 0
        self.stock.save()
        item = next(item for item in self.client.get(self.url).data["items"] if item["id"].startswith("stock:"))
        self.assertFalse(item["read"])
        self.assertEqual(item["title"], "Out of stock")

    def test_expired_business_denied(self):
        self.business.trial_ends_at = timezone.now() - timedelta(days=1)
        self.business.save()
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_admin_notices_not_accessible_to_business_owner(self):
        # Admin login uses session auth; a workspace owner is not a platform admin.
        self.client.force_authenticate(None)
        self.client.force_login(self.owner)
        url = reverse("admin:intelligence-operational-notices")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.owner.is_staff = True
        self.owner.save()
        self.assertEqual(self.client.get(url).status_code, 403)
        self.owner.is_superuser = True
        self.owner.save()
        self.assertEqual(self.client.get(url).status_code, 200)
