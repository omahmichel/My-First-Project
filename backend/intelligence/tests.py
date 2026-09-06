from datetime import timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from businesses.models import Business, BusinessMembership
from customers.models import Customer
from inventory.models import Product, StockMovement
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
        self.assertFalse(response.data["salesAnomaly"]["eligible"])
        self.assertEqual(
            response.data["salesAnomaly"]["status"],
            "insufficient_history",
        )

    def test_sales_anomaly_uses_same_weekday_baseline(self):
        anomaly_business = Business.objects.create(
            owner=self.owner,
            name="Anomaly Test Shop",
            slug="anomaly-test-shop",
            business_type=Business.BusinessType.BUILDING_MATERIALS,
        )

        now = timezone.now()
        today_start = timezone.localtime(now).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        target_time = today_start - timedelta(hours=12)
        target_date = target_time.date()

        def create_sale(*, days_back, amount, suffix):
            completed_at = target_time - timedelta(days=days_back)
            return Sale.objects.create(
                business=anomaly_business,
                customer=None,
                customer_name="Walk-in customer",
                customer_phone="",
                sale_number=f"INT-ANOM-{suffix}",
                invoice_number=f"INT-ANOM-INV-{suffix}",
                payment_method=Sale.PaymentMethod.CASH,
                status=Sale.Status.COMPLETED,
                subtotal=amount,
                discount=Decimal("0.00"),
                total=amount,
                amount_paid=amount,
                outstanding_balance=Decimal("0.00"),
                cashier=self.owner,
                cashier_name=self.owner.full_name,
                completed_at=completed_at,
            )

        for offset, suffix in (
            (7, "B1"),
            (14, "B2"),
            (21, "B3"),
            (28, "B4"),
        ):
            create_sale(
                days_back=offset,
                amount=Decimal("100.00"),
                suffix=suffix,
            )

        for offset, suffix in (
            (30, "H1"),
            (31, "H2"),
            (32, "H3"),
            (33, "H4"),
            (34, "H5"),
            (35, "H6"),
        ):
            create_sale(
                days_back=offset,
                amount=Decimal("20.00"),
                suffix=suffix,
            )

        create_sale(
            days_back=0,
            amount=Decimal("300.00"),
            suffix="TARGET",
        )

        self.client.force_authenticate(user=self.owner)
        response = self.client.get(
            self.overview_url(anomaly_business)
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        anomaly = response.data["salesAnomaly"]
        self.assertTrue(anomaly["eligible"])
        self.assertEqual(anomaly["status"], "anomaly")
        self.assertEqual(anomaly["confidenceGrade"], "medium")
        self.assertEqual(
            anomaly["evaluatedDate"],
            target_date.isoformat(),
        )
        self.assertEqual(anomaly["baselineSampleCount"], 4)
        self.assertEqual(
            Decimal(str(anomaly["currentRevenue"])),
            Decimal("300.00"),
        )
        self.assertEqual(
            Decimal(str(anomaly["baselineAverageRevenue"])),
            Decimal("100.00"),
        )
        self.assertEqual(
            Decimal(str(anomaly["percentageChange"])),
            Decimal("200.00"),
        )
        self.assertEqual(anomaly["direction"], "up")
        self.assertEqual(anomaly["signalType"], "revenue_spike")
        self.assertEqual(anomaly["severity"], "high")
        self.assertEqual(len(anomaly["baselineSamples"]), 4)

    def test_inventory_overstock_uses_recent_demand_cover(self):
        overstock_business = Business.objects.create(
            owner=self.owner,
            name="Overstock Test Shop",
            slug="overstock-test-shop",
            business_type=Business.BusinessType.BUILDING_MATERIALS,
        )
        product = Product.objects.create(
            business=overstock_business,
            name="Overstock Cement",
            sku="INT-OVERSTOCK-001",
            category="Cement",
            unit=Product.Unit.BAG,
            stock=100,
            reserved_stock=0,
            low_stock_level=10,
            cost_price=Decimal("5.00"),
            selling_price=Decimal("8.00"),
        )

        sale = Sale.objects.create(
            business=overstock_business,
            customer=None,
            customer_name="Walk-in customer",
            customer_phone="",
            sale_number="INT-OVERSTOCK-SALE",
            invoice_number="INT-OVERSTOCK-INV",
            payment_method=Sale.PaymentMethod.CASH,
            status=Sale.Status.COMPLETED,
            subtotal=Decimal("80.00"),
            discount=Decimal("0.00"),
            total=Decimal("80.00"),
            amount_paid=Decimal("80.00"),
            outstanding_balance=Decimal("0.00"),
            cashier=self.owner,
            cashier_name=self.owner.full_name,
            completed_at=timezone.now() - timedelta(days=5),
        )
        SaleItem.objects.create(
            sale=sale,
            product=product,
            product_name=product.name,
            sku=product.sku,
            design_code="",
            unit=product.unit,
            quantity=10,
            unit_price=Decimal("8.00"),
            cost_price=product.cost_price,
            line_total=Decimal("80.00"),
        )

        StockMovement.objects.create(
            business=overstock_business,
            product=product,
            movement_type=StockMovement.MovementType.STOCK_IN,
            quantity=10,
            previous_stock=90,
            new_stock=100,
            reason="Recent restock for overstock test",
            created_by=self.owner,
        )

        self.client.force_authenticate(user=self.owner)
        response = self.client.get(
            self.overview_url(overstock_business)
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        overstock = response.data["inventoryOverstock"]
        self.assertEqual(overstock["demandLookbackDays"], 30)
        self.assertEqual(overstock["overstockCoverDays"], 60)
        self.assertEqual(overstock["candidateCount"], 1)
        self.assertEqual(overstock["totalExcessUnits"], 80)
        self.assertEqual(
            Decimal(str(overstock["totalExcessCostValue"])),
            Decimal("400.00"),
        )
        self.assertEqual(
            overstock["method"],
            "recent_demand_days_of_cover",
        )

        candidate = overstock["candidates"][0]
        self.assertEqual(candidate["sku"], "INT-OVERSTOCK-001")
        self.assertEqual(candidate["availableStock"], 100)
        self.assertEqual(candidate["quantitySold30d"], 10)
        self.assertEqual(candidate["targetStockUnits"], 20)
        self.assertEqual(candidate["excessUnits"], 80)
        self.assertEqual(
            Decimal(str(candidate["estimatedDaysOfCover"])),
            Decimal("300.0"),
        )
        self.assertEqual(
            Decimal(str(candidate["currentCostPrice"])),
            Decimal("5.00"),
        )
        self.assertEqual(
            Decimal(str(candidate["excessCostValue"])),
            Decimal("400.00"),
        )
        self.assertIsNotNone(candidate["lastStockInAt"])

    def test_product_profitability_allocates_sale_discount(self):
        profitability_business = Business.objects.create(
            owner=self.owner,
            name="Profitability Test Shop",
            slug="profitability-test-shop",
            business_type=Business.BusinessType.BUILDING_MATERIALS,
        )
        product_a = Product.objects.create(
            business=profitability_business,
            name="Profit Product A",
            sku="INT-PROFIT-A",
            category="Test",
            unit=Product.Unit.PIECE,
            stock=20,
            reserved_stock=0,
            low_stock_level=2,
            cost_price=Decimal("60.00"),
            selling_price=Decimal("100.00"),
        )
        product_b = Product.objects.create(
            business=profitability_business,
            name="Profit Product B",
            sku="INT-PROFIT-B",
            category="Test",
            unit=Product.Unit.PIECE,
            stock=20,
            reserved_stock=0,
            low_stock_level=2,
            cost_price=Decimal("20.00"),
            selling_price=Decimal("50.00"),
        )

        previous_sale = Sale.objects.create(
            business=profitability_business,
            customer=None,
            customer_name="Walk-in customer",
            customer_phone="",
            sale_number="INT-PROFIT-PREV",
            invoice_number="INT-PROFIT-INV-PREV",
            payment_method=Sale.PaymentMethod.CASH,
            status=Sale.Status.COMPLETED,
            subtotal=Decimal("100.00"),
            discount=Decimal("0.00"),
            total=Decimal("100.00"),
            amount_paid=Decimal("100.00"),
            outstanding_balance=Decimal("0.00"),
            cashier=self.owner,
            cashier_name=self.owner.full_name,
            completed_at=timezone.now() - timedelta(days=40),
        )

        product_a.cost_price = Decimal("40.00")
        product_a.save()
        SaleItem.objects.create(
            sale=previous_sale,
            product=product_a,
            product_name=product_a.name,
            sku=product_a.sku,
            design_code="",
            unit=product_a.unit,
            quantity=1,
            unit_price=Decimal("100.00"),
            cost_price=product_a.cost_price,
            line_total=Decimal("100.00"),
        )
        product_a.cost_price = Decimal("60.00")
        product_a.save()

        current_sale = Sale.objects.create(
            business=profitability_business,
            customer=None,
            customer_name="Walk-in customer",
            customer_phone="",
            sale_number="INT-PROFIT-CURRENT",
            invoice_number="INT-PROFIT-INV-CURRENT",
            payment_method=Sale.PaymentMethod.CASH,
            status=Sale.Status.COMPLETED,
            subtotal=Decimal("200.00"),
            discount=Decimal("20.00"),
            total=Decimal("180.00"),
            amount_paid=Decimal("180.00"),
            outstanding_balance=Decimal("0.00"),
            cashier=self.owner,
            cashier_name=self.owner.full_name,
            completed_at=timezone.now() - timedelta(days=5),
        )
        SaleItem.objects.create(
            sale=current_sale,
            product=product_a,
            product_name=product_a.name,
            sku=product_a.sku,
            design_code="",
            unit=product_a.unit,
            quantity=1,
            unit_price=Decimal("100.00"),
            cost_price=product_a.cost_price,
            line_total=Decimal("100.00"),
        )
        SaleItem.objects.create(
            sale=current_sale,
            product=product_b,
            product_name=product_b.name,
            sku=product_b.sku,
            design_code="",
            unit=product_b.unit,
            quantity=2,
            unit_price=Decimal("50.00"),
            cost_price=product_b.cost_price,
            line_total=Decimal("100.00"),
        )

        self.client.force_authenticate(user=self.owner)
        response = self.client.get(
            self.overview_url(profitability_business)
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        profitability = response.data["productProfitability"]
        self.assertEqual(profitability["periodDays"], 30)
        self.assertEqual(
            profitability["discountAllocationMethod"],
            "proportional_by_line_subtotal",
        )
        self.assertEqual(
            profitability["discountRoundingMethod"],
            "cent_reconciliation_to_largest_line",
        )

        best = profitability["bestPerformingProducts"][0]
        self.assertEqual(best["sku"], "INT-PROFIT-B")
        self.assertEqual(
            Decimal(str(best["realizedRevenue"])),
            Decimal("90.00"),
        )
        self.assertEqual(
            Decimal(str(best["historicalCost"])),
            Decimal("40.00"),
        )
        self.assertEqual(
            Decimal(str(best["grossProfit"])),
            Decimal("50.00"),
        )
        self.assertEqual(
            Decimal(str(best["profitMargin"])),
            Decimal("55.56"),
        )

        worst = profitability["worstPerformingProducts"][0]
        self.assertEqual(worst["sku"], "INT-PROFIT-A")
        self.assertEqual(
            Decimal(str(worst["realizedRevenue"])),
            Decimal("90.00"),
        )
        self.assertEqual(
            Decimal(str(worst["grossProfit"])),
            Decimal("30.00"),
        )
        self.assertEqual(
            Decimal(str(worst["previousProfitMargin"])),
            Decimal("60.00"),
        )
        self.assertEqual(
            Decimal(str(worst["marginChangePoints"])),
            Decimal("-26.67"),
        )

        deterioration = profitability["marginDeterioration"][0]
        self.assertEqual(deterioration["sku"], "INT-PROFIT-A")
        self.assertEqual(
            Decimal(str(deterioration["marginChangePoints"])),
            Decimal("-26.67"),
        )

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
