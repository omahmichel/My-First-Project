from datetime import timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from businesses.models import Business, BusinessMembership
from customers.models import Customer
from inventory.models import Product
from sales.models import Sale, SaleItem


class BusinessIntelligenceOverviewTests(APITestCase):
    """Protects the first verified StockFlow Intelligence overview."""

    def setUp(self):
        self.owner = User.objects.create_user(
            email="intelligence.owner@stockflow.local",
            password="StrongPass123!",
            full_name="Intelligence Owner",
        )
        self.manager = User.objects.create_user(
            email="intelligence.manager@stockflow.local",
            password="StrongPass123!",
            full_name="Intelligence Manager",
        )
        self.cashier = User.objects.create_user(
            email="intelligence.cashier@stockflow.local",
            password="StrongPass123!",
            full_name="Intelligence Cashier",
        )
        self.outsider = User.objects.create_user(
            email="intelligence.outsider@stockflow.local",
            password="StrongPass123!",
            full_name="Intelligence Outsider",
        )

        self.business = Business.objects.create(
            owner=self.owner,
            name="Intelligence Test Shop",
            slug="intelligence-test-shop",
            business_type=Business.BusinessType.BUILDING_MATERIALS,
        )
        self.other_business = Business.objects.create(
            owner=self.outsider,
            name="Other Intelligence Shop",
            slug="other-intelligence-shop",
            business_type=Business.BusinessType.BOUTIQUE,
        )

        BusinessMembership.objects.create(
            business=self.business,
            user=self.manager,
            role=BusinessMembership.Role.MANAGER,
            is_active=True,
        )
        BusinessMembership.objects.create(
            business=self.business,
            user=self.cashier,
            role=BusinessMembership.Role.CASHIER,
            is_active=True,
        )

        self.product = Product.objects.create(
            business=self.business,
            name="Intelligence Cement",
            sku="INT-CEMENT-001",
            category="Cement",
            unit=Product.Unit.BAG,
            stock=1,
            reserved_stock=0,
            low_stock_level=2,
            cost_price=Decimal("60.00"),
            selling_price=Decimal("100.00"),
        )
        self.customer = Customer.objects.create(
            business=self.business,
            name="Intelligence Customer",
            phone="0240000000",
            email="intelligence.customer@example.com",
            created_by=self.owner,
        )

        now = timezone.now()

        completed = Sale.objects.create(
            business=self.business,
            customer=None,
            customer_name="Walk-in customer",
            customer_phone="",
            sale_number="INT-SALE-001",
            invoice_number="INT-INV-001",
            payment_method=Sale.PaymentMethod.CASH,
            status=Sale.Status.COMPLETED,
            subtotal=Decimal("200.00"),
            discount=Decimal("0.00"),
            total=Decimal("200.00"),
            amount_paid=Decimal("200.00"),
            outstanding_balance=Decimal("0.00"),
            cashier=self.owner,
            cashier_name=self.owner.full_name,
            completed_at=now - timedelta(days=1),
        )
        SaleItem.objects.create(
            sale=completed,
            product=self.product,
            product_name=self.product.name,
            sku=self.product.sku,
            design_code="",
            unit=self.product.unit,
            quantity=2,
            unit_price=Decimal("100.00"),
            cost_price=self.product.cost_price,
            line_total=Decimal("200.00"),
        )

        partially_paid = Sale.objects.create(
            business=self.business,
            customer=self.customer,
            customer_name=self.customer.name,
            customer_phone=self.customer.phone,
            sale_number="INT-SALE-002",
            invoice_number="INT-INV-002",
            payment_method=Sale.PaymentMethod.CREDIT,
            status=Sale.Status.PARTIALLY_PAID,
            subtotal=Decimal("100.00"),
            discount=Decimal("0.00"),
            total=Decimal("100.00"),
            amount_paid=Decimal("50.00"),
            outstanding_balance=Decimal("50.00"),
            debt_due_date=timezone.localdate() + timedelta(days=7),
            debt_principal_at_due=Decimal("50.00"),
            cashier=self.owner,
            cashier_name=self.owner.full_name,
            completed_at=now - timedelta(days=2),
        )
        SaleItem.objects.create(
            sale=partially_paid,
            product=self.product,
            product_name=self.product.name,
            sku=self.product.sku,
            design_code="",
            unit=self.product.unit,
            quantity=1,
            unit_price=Decimal("100.00"),
            cost_price=self.product.cost_price,
            line_total=Decimal("100.00"),
        )

        pending = Sale.objects.create(
            business=self.business,
            customer=None,
            customer_name="Walk-in customer",
            customer_phone="",
            sale_number="INT-SALE-PENDING",
            invoice_number="INT-INV-PENDING",
            payment_method=Sale.PaymentMethod.MOBILE_MONEY,
            status=Sale.Status.PENDING_PAYMENT,
            subtotal=Decimal("999.00"),
            discount=Decimal("0.00"),
            total=Decimal("999.00"),
            amount_paid=Decimal("0.00"),
            outstanding_balance=Decimal("999.00"),
            cashier=self.owner,
            cashier_name=self.owner.full_name,
        )
        SaleItem.objects.create(
            sale=pending,
            product=self.product,
            product_name=self.product.name,
            sku=self.product.sku,
            design_code="",
            unit=self.product.unit,
            quantity=1,
            unit_price=Decimal("999.00"),
            cost_price=self.product.cost_price,
            line_total=Decimal("999.00"),
        )

    def overview_url(self, business=None):
        target = business or self.business
        return reverse(
            "business-intelligence-overview",
            kwargs={"business_id": target.id},
        )

    def test_owner_receives_verified_overview(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(self.overview_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            Decimal(str(response.data["sales"]["revenue"])),
            Decimal("300.00"),
        )
        self.assertEqual(
            Decimal(str(response.data["sales"]["historicalCost"])),
            Decimal("180.00"),
        )
        self.assertEqual(
            Decimal(str(response.data["sales"]["grossProfit"])),
            Decimal("120.00"),
        )

        periods = response.data["performancePeriods"]
        self.assertEqual(
            Decimal(str(periods["today"]["revenue"])),
            Decimal("0.00"),
        )
        self.assertEqual(
            Decimal(str(periods["last7Days"]["revenue"])),
            Decimal("300.00"),
        )
        self.assertEqual(
            Decimal(str(periods["last7Days"]["grossProfit"])),
            Decimal("120.00"),
        )
        self.assertEqual(
            Decimal(str(periods["last7Days"]["previousRevenue"])),
            Decimal("0.00"),
        )
        self.assertEqual(
            Decimal(str(periods["last7Days"]["revenueChange"])),
            Decimal("300.00"),
        )
        self.assertIsNone(
            periods["last7Days"]["revenueChangePercentage"]
        )
        self.assertEqual(
            periods["last7Days"]["revenueDirection"],
            "up",
        )
        self.assertEqual(
            Decimal(str(periods["last30Days"]["revenue"])),
            Decimal("300.00"),
        )

        self.assertEqual(response.data["sales"]["unitsSold"], 3)
        self.assertEqual(
            Decimal(str(response.data["debts"]["customerDebt"])),
            Decimal("50.00"),
        )
        self.assertEqual(response.data["inventory"]["lowStockCount"], 1)
        self.assertEqual(
            response.data["products"]["topProducts"][0]["quantitySold"],
            3,
        )
        self.assertEqual(len(response.data["products"]["stockOutRisks"]), 1)
        self.assertEqual(
            response.data["methodology"]["recognizedSaleStatuses"],
            ["completed", "partially_paid"],
        )
        self.assertEqual(
            response.data["methodology"]["periodPerformanceWindows"],
            ["today", "rolling_7_days", "rolling_30_days"],
        )
        self.assertEqual(
            response.data["methodology"]["todayComparisonBasis"],
            "previous_day_same_elapsed_time",
        )
        self.assertEqual(response.data["confidence"]["grade"], "low")

    def test_period_performance_compares_against_real_previous_window(self):
        previous_period_sale = Sale.objects.create(
            business=self.business,
            customer=None,
            customer_name="Walk-in customer",
            customer_phone="",
            sale_number="INT-SALE-PREV-7D",
            invoice_number="INT-INV-PREV-7D",
            payment_method=Sale.PaymentMethod.CASH,
            status=Sale.Status.COMPLETED,
            subtotal=Decimal("80.00"),
            discount=Decimal("0.00"),
            total=Decimal("80.00"),
            amount_paid=Decimal("80.00"),
            outstanding_balance=Decimal("0.00"),
            cashier=self.owner,
            cashier_name=self.owner.full_name,
            completed_at=timezone.now() - timedelta(days=10),
        )
        original_cost_price = self.product.cost_price
        self.product.cost_price = Decimal("40.00")
        self.product.save()

        SaleItem.objects.create(
            sale=previous_period_sale,
            product=self.product,
            product_name=self.product.name,
            sku=self.product.sku,
            design_code="",
            unit=self.product.unit,
            quantity=1,
            unit_price=Decimal("80.00"),
            cost_price=self.product.cost_price,
            line_total=Decimal("80.00"),
        )

        self.product.cost_price = original_cost_price
        self.product.save()

        self.client.force_authenticate(user=self.owner)
        response = self.client.get(self.overview_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        period = response.data["performancePeriods"]["last7Days"]

        self.assertEqual(
            Decimal(str(period["revenue"])),
            Decimal("300.00"),
        )
        self.assertEqual(
            Decimal(str(period["previousRevenue"])),
            Decimal("80.00"),
        )
        self.assertEqual(
            Decimal(str(period["revenueChange"])),
            Decimal("220.00"),
        )
        self.assertEqual(
            Decimal(str(period["revenueChangePercentage"])),
            Decimal("275.00"),
        )
        self.assertEqual(period["revenueDirection"], "up")
        self.assertEqual(
            Decimal(str(period["grossProfit"])),
            Decimal("120.00"),
        )
        self.assertEqual(
            Decimal(str(period["previousGrossProfit"])),
            Decimal("40.00"),
        )
        self.assertEqual(
            Decimal(str(period["grossProfitChange"])),
            Decimal("80.00"),
        )
        self.assertEqual(
            Decimal(str(period["grossProfitChangePercentage"])),
            Decimal("200.00"),
        )
        self.assertEqual(period["grossProfitDirection"], "up")

    def test_manager_can_read_overview(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.get(self.overview_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_cashier_cannot_read_strategic_intelligence(self):
        self.client.force_authenticate(user=self.cashier)
        response = self.client.get(self.overview_url())
        self.assertIn(
            response.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
        )

    def test_user_cannot_read_another_business_overview(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.get(self.overview_url(self.other_business))
        self.assertIn(
            response.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
        )

    def test_anonymous_user_is_rejected(self):
        response = self.client.get(self.overview_url())
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
