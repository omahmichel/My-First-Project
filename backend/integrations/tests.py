from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from businesses.models import Branch, Business, BusinessMembership
from inventory.models import BranchInventory, Product
from sales.models import Sale, SaleItem


class AccountingIntegrationExportTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            email="owner-integrations@example.com",
            password="StrongPass123!",
        )
        self.manager = user_model.objects.create_user(
            email="manager-integrations@example.com",
            password="StrongPass123!",
        )
        self.business = Business.objects.create(
            owner=self.owner,
            name="Integration Test Business",
            slug="integration-test-business",
            business_type=Business.BusinessType.BUILDING_MATERIALS,
        )
        BusinessMembership.objects.create(
            business=self.business,
            user=self.manager,
            role=BusinessMembership.Role.MANAGER,
        )
        self.branch = Branch.objects.create(
            business=self.business,
            name="Main Branch",
            code="MAIN",
            is_main=True,
            created_by=self.owner,
        )
        self.product = Product.objects.create(
            business=self.business,
            product_type=Product.ProductType.STANDARD,
            name="Test Cement",
            sku="CEM-001",
            category="Cement",
            unit=Product.Unit.BAG,
            stock=5,
            reserved_stock=0,
            low_stock_level=2,
            cost_price=Decimal("30.00"),
            selling_price=Decimal("50.00"),
        )
        BranchInventory.objects.create(
            branch=self.branch,
            product=self.product,
            stock=5,
            reserved_stock=0,
            low_stock_level=2,
        )
        self.sale = Sale.objects.create(
            business=self.business,
            branch=self.branch,
            customer_name="Walk-in customer",
            customer_phone="",
            sale_number="SALE-INT-001",
            invoice_number="INV-INT-001",
            payment_method=Sale.PaymentMethod.CASH,
            status=Sale.Status.COMPLETED,
            subtotal=Decimal("100.00"),
            discount=Decimal("0.00"),
            total=Decimal("100.00"),
            amount_paid=Decimal("100.00"),
            outstanding_balance=Decimal("0.00"),
            cashier=self.owner,
            cashier_name=self.owner.email,
            completed_at=timezone.now(),
        )
        SaleItem.objects.create(
            sale=self.sale,
            product=self.product,
            quantity=2,
            unit_price=Decimal("50.00"),
            cost_price=Decimal("30.00"),
            line_total=Decimal("100.00"),
        )

    def test_owner_can_read_export_manifest(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get(
            f"/api/businesses/{self.business.id}/integrations/accounting/exports/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["version"], 1)
        self.assertEqual(
            {item["key"] for item in response.data["datasets"]},
            {"sales", "inventory", "purchases", "customers", "suppliers"},
        )
        self.assertTrue(response.data["safety"]["readOnly"])

    def test_sales_export_is_branch_aware_and_uses_historical_cost(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get(
            f"/api/businesses/{self.business.id}/integrations/"
            "accounting/exports/sales/"
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8-sig")
        self.assertIn("SALE-INT-001", content)
        self.assertIn("Main Branch", content)
        self.assertIn("60.00", content)
        self.assertIn("40.00", content)

    def test_inventory_export_uses_branch_inventory(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get(
            f"/api/businesses/{self.business.id}/integrations/"
            "accounting/exports/inventory/"
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8-sig")
        self.assertIn("Main Branch", content)
        self.assertIn("CEM-001", content)
        self.assertIn("150.00", content)
        self.assertIn("250.00", content)

    def test_manager_cannot_export_owner_accounting_data(self):
        self.client.force_authenticate(self.manager)
        response = self.client.get(
            f"/api/businesses/{self.business.id}/integrations/accounting/exports/"
        )
        self.assertEqual(response.status_code, 403)
