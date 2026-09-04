from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from businesses.models import Business, BusinessMembership
from .models import Product, StockMovement
from .restock_models import RestockPayment, RestockPurchase


class RestockingTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            email="restock-owner@example.com",
            password="StrongPass123!",
            full_name="Restock Owner",
        )
        self.cashier = user_model.objects.create_user(
            email="restock-cashier@example.com",
            password="StrongPass123!",
            full_name="Cashier",
        )
        self.business = Business.objects.create(
            owner=self.owner,
            name="Restock Test Business",
            slug="restock-test-business",
            business_type=Business.BusinessType.BUILDING_MATERIALS,
        )
        BusinessMembership.objects.create(
            business=self.business,
            user=self.cashier,
            role=BusinessMembership.Role.CASHIER,
            is_active=True,
        )
        self.product = Product.objects.create(
            business=self.business,
            product_type=Product.ProductType.STANDARD,
            name="Cement",
            sku="CEM-RST-1",
            category="Cement",
            unit=Product.Unit.BAG,
            stock=10,
            cost_price=Decimal("10.00"),
            selling_price=Decimal("25.00"),
        )
        self.suppliers_url = (
            f"/api/businesses/{self.business.id}/suppliers/"
        )
        self.restocks_url = (
            f"/api/businesses/{self.business.id}/restocks/"
        )

    def login(self, user=None):
        self.client.force_authenticate(user=user or self.owner)

    def supplier(self):
        response = self.client.post(
            self.suppliers_url,
            {"name": "Prime Supplier", "phone": "0244000000"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.data

    def test_restock_updates_stock_weighted_cost_and_movement(self):
        self.login()
        supplier = self.supplier()
        response = self.client.post(
            self.restocks_url,
            {
                "supplierId": supplier["id"],
                "supplierReference": "SUP-100",
                "initialPayment": "50.00",
                "items": [{
                    "productId": str(self.product.id),
                    "quantity": 10,
                    "unitCost": "20.00",
                }],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["totalAmount"], "200.00")
        self.assertEqual(response.data["paymentStatus"], "partial")
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 20)
        self.assertEqual(self.product.cost_price, Decimal("15.00"))
        self.assertEqual(
            StockMovement.objects.filter(
                business=self.business,
                movement_type=StockMovement.MovementType.STOCK_IN,
            ).count(),
            1,
        )

    def test_later_payment_completes_supplier_purchase(self):
        self.login()
        supplier = self.supplier()
        created = self.client.post(
            self.restocks_url,
            {
                "supplierId": supplier["id"],
                "items": [{
                    "productId": str(self.product.id),
                    "quantity": 2,
                    "unitCost": "20.00",
                }],
            },
            format="json",
        )
        payment_url = (
            f"/api/businesses/{self.business.id}/restocks/"
            f"{created.data['id']}/payments/"
        )
        paid = self.client.post(
            payment_url,
            {"amount": "40.00", "method": "bank_transfer"},
            format="json",
        )
        self.assertEqual(paid.status_code, status.HTTP_200_OK)
        self.assertEqual(paid.data["paymentStatus"], "paid")
        self.assertEqual(paid.data["outstandingBalance"], "0.00")
        self.assertEqual(RestockPayment.objects.count(), 1)

    def test_cashier_cannot_manage_restocking(self):
        self.login(self.cashier)
        response = self.client.get(self.suppliers_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_foreign_product_is_rejected_without_stock_change(self):
        other_owner = get_user_model().objects.create_user(
            email="foreign@example.com",
            password="StrongPass123!",
            full_name="Foreign",
        )
        other_business = Business.objects.create(
            owner=other_owner,
            name="Foreign Business",
            slug="foreign-restock-business",
            business_type=Business.BusinessType.BUILDING_MATERIALS,
        )
        foreign = Product.objects.create(
            business=other_business,
            product_type=Product.ProductType.STANDARD,
            name="Foreign Cement",
            sku="FOREIGN-RST",
            category="Cement",
            unit=Product.Unit.BAG,
            stock=5,
            cost_price=Decimal("8.00"),
            selling_price=Decimal("15.00"),
        )
        self.login()
        supplier = self.supplier()
        before = self.product.stock
        response = self.client.post(
            self.restocks_url,
            {
                "supplierId": supplier["id"],
                "items": [
                    {
                        "productId": str(self.product.id),
                        "quantity": 2,
                        "unitCost": "20.00",
                    },
                    {
                        "productId": str(foreign.id),
                        "quantity": 2,
                        "unitCost": "20.00",
                    },
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, before)
        self.assertEqual(RestockPurchase.objects.count(), 0)
