from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from businesses.models import Business, BusinessMembership

from .models import Product


class ProductStatusAPITests(APITestCase):
    # Builds isolated inventory records for product-status tests.

    def setUp(self):
        self.owner = User.objects.create_user(
            email="inventory.owner@stockflow.local",
            password="StrongPass123!",
            full_name="Inventory Owner",
        )
        self.cashier = User.objects.create_user(
            email="inventory.cashier@stockflow.local",
            password="StrongPass123!",
            full_name="Inventory Cashier",
        )

        self.business = Business.objects.create(
            owner=self.owner,
            name="Inventory Test Shop",
            slug="inventory-test-shop",
            business_type=Business.BusinessType.BUILDING_MATERIALS,
        )
        self.other_business = Business.objects.create(
            owner=self.owner,
            name="Second Inventory Shop",
            slug="second-inventory-shop",
            business_type=Business.BusinessType.BUILDING_MATERIALS,
        )

        BusinessMembership.objects.create(
            business=self.business,
            user=self.cashier,
            role=BusinessMembership.Role.CASHIER,
            is_active=True,
        )

        self.active_product = Product.objects.create(
            business=self.business,
            product_type=Product.ProductType.STANDARD,
            name="Premium Cement",
            sku="CEMENT-001",
            category="Cement",
            unit=Product.Unit.BAG,
            stock=20,
            cost_price=Decimal("80.00"),
            selling_price=Decimal("95.00"),
            is_active=True,
        )
        self.inactive_product = Product.objects.create(
            business=self.business,
            product_type=Product.ProductType.TILE,
            name="Royal Ceramic Tile",
            sku="TILE-6052",
            category="Tiles",
            unit=Product.Unit.BOX,
            stock=10,
            cost_price=Decimal("120.00"),
            selling_price=Decimal("150.00"),
            design_code="6052",
            is_active=False,
        )

        self.list_url = (
            f"/api/businesses/{self.business.id}/products/"
        )
        self.status_url = (
            f"/api/businesses/{self.business.id}/products/"
            f"{self.active_product.id}/status/"
        )

    def authenticate(self, user):
        # Authenticates directly without depending on the login endpoint.
        self.client.force_authenticate(user=user)

    def test_product_list_returns_active_and_inactive_records(self):
        # The inventory UI needs both states for filtering and restoration.
        self.authenticate(self.owner)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

        records = {
            str(record["id"]): record
            for record in response.data
        }
        self.assertTrue(
            records[str(self.active_product.id)]["isActive"]
        )
        self.assertFalse(
            records[str(self.inactive_product.id)]["isActive"]
        )

    def test_owner_can_deactivate_and_reactivate_product(self):
        # Product status changes preserve the database record.
        self.authenticate(self.owner)

        deactivate_response = self.client.patch(
            self.status_url,
            {"isActive": False},
            format="json",
        )
        self.assertEqual(
            deactivate_response.status_code,
            status.HTTP_200_OK,
            deactivate_response.data,
        )
        self.assertFalse(deactivate_response.data["isActive"])

        self.active_product.refresh_from_db()
        self.assertFalse(self.active_product.is_active)

        reactivate_response = self.client.patch(
            self.status_url,
            {"isActive": True},
            format="json",
        )
        self.assertEqual(
            reactivate_response.status_code,
            status.HTTP_200_OK,
            reactivate_response.data,
        )
        self.assertTrue(reactivate_response.data["isActive"])

        self.active_product.refresh_from_db()
        self.assertTrue(self.active_product.is_active)

    def test_cashier_cannot_change_product_status(self):
        # Cashiers may sell products but cannot deactivate inventory.
        self.authenticate(self.cashier)

        response = self.client.patch(
            self.status_url,
            {"isActive": False},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.active_product.refresh_from_db()
        self.assertTrue(self.active_product.is_active)

    def test_status_change_is_isolated_by_business(self):
        # A product cannot be changed through another business URL.
        self.authenticate(self.owner)
        cross_business_url = (
            f"/api/businesses/{self.other_business.id}/products/"
            f"{self.active_product.id}/status/"
        )

        response = self.client.patch(
            cross_business_url,
            {"isActive": False},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.active_product.refresh_from_db()
        self.assertTrue(self.active_product.is_active)

    def test_inactive_product_cannot_receive_stock_adjustment(self):
        # Stock changes remain blocked while a product is inactive.
        self.authenticate(self.owner)
        adjustment_url = (
            f"/api/businesses/{self.business.id}/products/"
            f"{self.inactive_product.id}/adjust-stock/"
        )

        response = self.client.post(
            adjustment_url,
            {
                "quantity": 5,
                "type": "stock_in",
                "reason": "Restock attempt",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.inactive_product.refresh_from_db()
        self.assertEqual(self.inactive_product.stock, 10)
