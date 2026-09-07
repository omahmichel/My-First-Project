import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from businesses.models import Business, BusinessMembership
from customers.models import Customer
from intelligence.models import BusinessInsight, ForecastRun
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


    def test_forecast_engine_generates_and_stores_combined_forecast(self):
        forecast_business = Business.objects.create(
            owner=self.owner,
            name="Forecast Test Shop",
            slug="forecast-test-shop",
            business_type=Business.BusinessType.BUILDING_MATERIALS,
        )
        product = Product.objects.create(
            business=forecast_business,
            name="Forecast Cement",
            sku="INT-FORECAST-001",
            category="Cement",
            unit=Product.Unit.BAG,
            stock=5,
            reserved_stock=0,
            low_stock_level=2,
            cost_price=Decimal("6.00"),
            selling_price=Decimal("10.00"),
        )

        now = timezone.now()
        today_start = timezone.localtime(now).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        anchor_time = today_start - timedelta(hours=12)

        for index, days_back in enumerate(
            (0, 3, 6, 9, 12, 15, 18, 21, 24, 35),
            start=1,
        ):
            completed_at = anchor_time - timedelta(days=days_back)
            sale = Sale.objects.create(
                business=forecast_business,
                customer=None,
                customer_name="Walk-in customer",
                customer_phone="",
                sale_number=f"INT-FORECAST-{index}",
                invoice_number=f"INT-FORECAST-INV-{index}",
                payment_method=Sale.PaymentMethod.CASH,
                status=Sale.Status.COMPLETED,
                subtotal=Decimal("100.00"),
                discount=Decimal("0.00"),
                total=Decimal("100.00"),
                amount_paid=Decimal("100.00"),
                outstanding_balance=Decimal("0.00"),
                cashier=self.owner,
                cashier_name=self.owner.full_name,
                completed_at=completed_at,
            )
            SaleItem.objects.create(
                sale=sale,
                product=product,
                product_name=product.name,
                sku=product.sku,
                design_code="",
                unit=product.unit,
                quantity=10,
                unit_price=Decimal("10.00"),
                cost_price=Decimal("6.00"),
                line_total=Decimal("100.00"),
            )

        url = reverse(
            "business-intelligence-forecast",
            kwargs={"business_id": forecast_business.id},
        )
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            url,
            {"horizonDays": 7},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(response.data["horizonDays"], 7)
        self.assertEqual(
            response.data["algorithm"],
            "weighted_daily_velocity",
        )
        self.assertEqual(
            response.data["algorithmVersion"],
            "1.0",
        )
        self.assertEqual(
            response.data["confidence"]["grade"],
            "medium",
        )
        self.assertEqual(
            response.data["confidence"]["dataGrade"],
            "medium",
        )
        self.assertGreater(
            Decimal(str(
                response.data["businessForecast"][
                    "expectedRevenue"
                ]
            )),
            Decimal("0.00"),
        )
        self.assertGreater(
            Decimal(str(
                response.data["businessForecast"][
                    "expectedGrossProfit"
                ]
            )),
            Decimal("0.00"),
        )
        self.assertEqual(
            response.data["businessForecast"][
                "stockOutRiskCount"
            ],
            1,
        )

        product_forecast = response.data["productForecasts"][0]
        self.assertEqual(
            product_forecast["sku"],
            "INT-FORECAST-001",
        )
        self.assertEqual(
            product_forecast["availableStock"],
            5,
        )
        self.assertTrue(
            product_forecast["stockOutWithinHorizon"]
        )
        self.assertIsNotNone(
            product_forecast["projectedStockOutDate"]
        )

        category_forecast = response.data["categoryForecasts"][0]
        self.assertEqual(
            category_forecast["category"],
            "Cement",
        )
        self.assertEqual(
            category_forecast["stockOutRiskCount"],
            1,
        )
        self.assertEqual(
            response.data["methodology"][
                "recognizedSaleStatuses"
            ],
            ["completed", "partially_paid"],
        )
        self.assertTrue(
            response.data["methodology"]["completedDaysOnly"]
        )

        self.assertEqual(
            ForecastRun.objects.filter(
                business=forecast_business,
                horizon_days=7,
            ).count(),
            1,
        )

        history_response = self.client.get(
            f"{url}?horizonDays=7"
        )
        self.assertEqual(
            history_response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(len(history_response.data), 1)
        self.assertEqual(
            history_response.data[0]["id"],
            response.data["id"],
        )

        long_response = self.client.post(
            url,
            {"horizonDays": 90},
            format="json",
        )
        self.assertEqual(
            long_response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(
            long_response.data["confidence"]["dataGrade"],
            "medium",
        )
        self.assertEqual(
            long_response.data["confidence"]["grade"],
            "low",
        )
        self.assertEqual(
            long_response.data["methodology"][
                "horizonConfidencePolicy"
            ],
            "90_day_downgrades_one_level",
        )

    def test_forecast_engine_keeps_low_data_forecast_low_confidence(self):
        low_data_business = Business.objects.create(
            owner=self.owner,
            name="Low Data Forecast Shop",
            slug="low-data-forecast-shop",
            business_type=Business.BusinessType.BOUTIQUE,
        )
        product = Product.objects.create(
            business=low_data_business,
            name="Low Data Shirt",
            sku="INT-FORECAST-LOW-001",
            category="Shirts",
            unit=Product.Unit.PIECE,
            stock=20,
            reserved_stock=0,
            low_stock_level=3,
            cost_price=Decimal("20.00"),
            selling_price=Decimal("30.00"),
        )

        today_start = timezone.localtime(timezone.now()).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        completed_at = today_start - timedelta(hours=12)

        sale = Sale.objects.create(
            business=low_data_business,
            customer=None,
            customer_name="Walk-in customer",
            customer_phone="",
            sale_number="INT-FORECAST-LOW",
            invoice_number="INT-FORECAST-LOW-INV",
            payment_method=Sale.PaymentMethod.CASH,
            status=Sale.Status.COMPLETED,
            subtotal=Decimal("60.00"),
            discount=Decimal("0.00"),
            total=Decimal("60.00"),
            amount_paid=Decimal("60.00"),
            outstanding_balance=Decimal("0.00"),
            cashier=self.owner,
            cashier_name=self.owner.full_name,
            completed_at=completed_at,
        )
        SaleItem.objects.create(
            sale=sale,
            product=product,
            product_name=product.name,
            sku=product.sku,
            design_code="",
            unit=product.unit,
            quantity=2,
            unit_price=Decimal("30.00"),
            cost_price=Decimal("20.00"),
            line_total=Decimal("60.00"),
        )

        url = reverse(
            "business-intelligence-forecast",
            kwargs={"business_id": low_data_business.id},
        )
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            url,
            {"horizonDays": 30},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(
            response.data["confidence"]["grade"],
            "low",
        )
        self.assertEqual(
            response.data["confidence"]["dataGrade"],
            "low",
        )
        self.assertGreater(
            Decimal(str(
                response.data["businessForecast"][
                    "expectedRevenue"
                ]
            )),
            Decimal("0.00"),
        )
        self.assertEqual(
            response.data["productForecasts"][0][
                "confidenceGrade"
            ],
            "low",
        )

    def test_forecast_engine_rejects_unsupported_horizon(self):
        forecast_business = Business.objects.create(
            owner=self.owner,
            name="Invalid Forecast Horizon Shop",
            slug="invalid-forecast-horizon-shop",
            business_type=Business.BusinessType.BUILDING_MATERIALS,
        )
        url = reverse(
            "business-intelligence-forecast",
            kwargs={"business_id": forecast_business.id},
        )
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            url,
            {"horizonDays": 14},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            ForecastRun.objects.filter(
                business=forecast_business,
            ).count(),
            0,
        )


    @patch(
        "intelligence.services.recommendations.calculate_forecast"
    )
    @patch(
        "intelligence.services.recommendations.calculate_business_overview"
    )
    def test_recommendation_engine_generates_combined_persisted_insights(
        self,
        mock_overview,
        mock_forecast,
    ):
        recommendation_business = Business.objects.create(
            owner=self.owner,
            name="Recommendation Test Shop",
            slug="recommendation-test-shop",
            business_type=Business.BusinessType.BUILDING_MATERIALS,
        )

        old_engine_insight = BusinessInsight.objects.create(
            business=recommendation_business,
            insight_type=BusinessInsight.InsightType.INVENTORY,
            severity=BusinessInsight.Severity.ATTENTION,
            confidence=BusinessInsight.Confidence.MEDIUM,
            title="Old engine recommendation",
            summary="Old generated recommendation",
            evidence={
                "engine": "deterministic_recommendation_v1",
                "recommendation_code": "old",
            },
        )
        unrelated_insight = BusinessInsight.objects.create(
            business=recommendation_business,
            insight_type=BusinessInsight.InsightType.PERFORMANCE,
            severity=BusinessInsight.Severity.INFO,
            confidence=BusinessInsight.Confidence.LOW,
            title="Unrelated future insight",
            summary="Must remain active",
            evidence={"source": "manual_test"},
        )

        mock_overview.return_value = {
            "confidence": {"grade": "high"},
            "inventory_overstock": {
                "overstock_cover_days": 60,
                "candidates": [
                    {
                        "product_id": str(uuid.uuid4()),
                        "name": "Slow Cement",
                        "sku": "REC-OVER-001",
                        "available_stock": 100,
                        "quantity_sold_30d": 10,
                        "target_stock_units": 20,
                        "excess_units": 80,
                        "estimated_days_of_cover": Decimal("300.0"),
                        "excess_cost_value": Decimal("400.00"),
                    }
                ],
            },
            "product_profitability": {
                "comparison_period_days": 30,
                "margin_deterioration": [
                    {
                        "product_id": str(uuid.uuid4()),
                        "name": "Margin Block",
                        "sku": "REC-MARGIN-001",
                        "profit_margin": Decimal("20.00"),
                        "previous_profit_margin": Decimal("35.00"),
                        "margin_change_points": Decimal("-15.00"),
                        "realized_revenue": Decimal("500.00"),
                        "gross_profit": Decimal("100.00"),
                    }
                ],
            },
            "sales_anomaly": {
                "status": "anomaly",
                "signal_type": "revenue_drop",
                "severity": "high",
                "confidence_grade": "high",
                "evaluated_date": timezone.localdate(),
                "current_revenue": Decimal("100.00"),
                "baseline_average_revenue": Decimal("500.00"),
                "percentage_change": Decimal("-80.00"),
                "baseline_sample_count": 4,
                "threshold_percent": Decimal("75.00"),
            },
            "debts": {
                "customer_debt": Decimal("300.00"),
                "supplier_debt": Decimal("200.00"),
                "customers_with_debt": 2,
                "supplier_purchases_with_balance": 1,
            },
            "sales_trend": {
                "period_days": 30,
                "direction": "down",
                "current_revenue": Decimal("700.00"),
                "previous_revenue": Decimal("1000.00"),
                "absolute_change": Decimal("-300.00"),
                "percentage_change": Decimal("-30.00"),
            },
        }
        mock_forecast.return_value = {
            "results": {
                "products": [
                    {
                        "product_id": str(uuid.uuid4()),
                        "name": "Fast Cement",
                        "sku": "REC-STOCK-001",
                        "available_stock": 5,
                        "daily_demand": "2.00",
                        "days_of_stock_remaining": "2.5",
                        "projected_stock_out_date": (
                            timezone.localdate()
                            + timedelta(days=3)
                        ).isoformat(),
                        "stock_out_within_horizon": True,
                        "expected_quantity": "60.00",
                        "confidence_grade": "high",
                    }
                ]
            }
        }

        url = reverse(
            "business-intelligence-recommendations",
            kwargs={"business_id": recommendation_business.id},
        )
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(url, {}, format="json")

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(
            response.data["engine"],
            "deterministic_recommendation_v1",
        )
        self.assertEqual(
            response.data["forecastHorizonDays"],
            30,
        )
        self.assertEqual(response.data["count"], 7)
        self.assertEqual(
            response.data["recommendations"][0]["severity"],
            "high",
        )

        codes = {
            item["evidence"]["recommendation_code"]
            for item in response.data["recommendations"]
        }
        self.assertEqual(
            codes,
            {
                "restock_stockout_risk",
                "reduce_overstock_exposure",
                "review_margin_deterioration",
                "investigate_sales_anomaly",
                "collect_customer_debt",
                "review_supplier_debt",
                "review_revenue_decline",
            },
        )

        old_engine_insight.refresh_from_db()
        unrelated_insight.refresh_from_db()
        self.assertEqual(
            old_engine_insight.status,
            BusinessInsight.Status.RESOLVED,
        )
        self.assertIsNotNone(old_engine_insight.resolved_at)
        self.assertEqual(
            unrelated_insight.status,
            BusinessInsight.Status.ACTIVE,
        )

        active_engine_count = sum(
            1
            for insight in BusinessInsight.objects.filter(
                business=recommendation_business,
                status=BusinessInsight.Status.ACTIVE,
            )
            if insight.evidence.get("engine")
            == "deterministic_recommendation_v1"
        )
        self.assertEqual(active_engine_count, 7)

        get_response = self.client.get(url)
        self.assertEqual(
            get_response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(get_response.data["count"], 7)


    @patch("intelligence.views.answer_business_question")
    def test_owner_can_ask_grounded_stockflow_analyst(
        self,
        mocked_answer,
    ):
        mocked_answer.return_value = {
            "answer": (
                "Verified 30-day revenue is ₵300.00. "
                "Data confidence is low."
            ),
            "provider": "openai",
            "model": "gpt-5.6-luna",
            "generated_at": timezone.now(),
            "confidence": "low",
            "evidence": {
                "overallConfidence": "low",
                "overviewGeneratedAt": timezone.now().isoformat(),
                "availableForecastHorizons": [],
                "activeRecommendationCount": 0,
                "sources": [
                    "verified_intelligence_overview",
                    "stored_forecasts",
                    "active_recommendations",
                ],
            },
            "read_only": True,
        }
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            reverse(
                "business-intelligence-analyst",
                kwargs={"business_id": self.business.id},
            ),
            {
                "question": "What happened in my business?",
                "history": [],
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(response.data["confidence"], "low")
        self.assertTrue(response.data["readOnly"])
        self.assertIn("₵300.00", response.data["answer"])
        mocked_answer.assert_called_once()

    @patch("intelligence.views.answer_business_question")
    def test_cashier_cannot_use_stockflow_analyst(
        self,
        mocked_answer,
    ):
        self.client.force_authenticate(user=self.cashier)

        response = self.client.post(
            reverse(
                "business-intelligence-analyst",
                kwargs={"business_id": self.business.id},
            ),
            {"question": "Tell me the business strategy."},
            format="json",
        )

        self.assertIn(
            response.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
        )
        mocked_answer.assert_not_called()

    @patch("intelligence.views.answer_business_question")
    def test_analyst_configuration_failure_is_safe(
        self,
        mocked_answer,
    ):
        from intelligence.ai.analyst import AIAnalystUnavailable

        mocked_answer.side_effect = AIAnalystUnavailable(
            code="ai_not_configured",
            message="Ask StockFlow is not configured yet.",
        )
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            reverse(
                "business-intelligence-analyst",
                kwargs={"business_id": self.business.id},
            ),
            {"question": "What should I review today?"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )
        self.assertEqual(
            response.data["code"],
            "ai_not_configured",
        )


    def test_report_engine_defines_all_roadmap_report_types(self):
        from intelligence.services.reports import REPORT_DEFINITIONS

        self.assertEqual(
            set(REPORT_DEFINITIONS),
            {
                "daily_summary",
                "weekly_management",
                "monthly_management",
                "sales_profit",
                "stock_risk_restocking",
                "supplier_balances",
                "customer_debt",
            },
        )

    def test_weekly_report_top_products_use_weekly_window(self):
        from intelligence.services.reports import build_report_payload

        older_product = Product.objects.create(
            business=self.business,
            name="Older Period Product",
            sku="INT-REPORT-OLDER",
            category="Test",
            unit=Product.Unit.PIECE,
            stock=20,
            reserved_stock=0,
            low_stock_level=2,
            cost_price=Decimal("10.00"),
            selling_price=Decimal("20.00"),
        )
        older_sale = Sale.objects.create(
            business=self.business,
            customer=None,
            customer_name="Walk-in customer",
            customer_phone="",
            sale_number="INT-REPORT-OLDER-SALE",
            invoice_number="INT-REPORT-OLDER-INV",
            payment_method=Sale.PaymentMethod.CASH,
            status=Sale.Status.COMPLETED,
            subtotal=Decimal("2000.00"),
            discount=Decimal("0.00"),
            total=Decimal("2000.00"),
            amount_paid=Decimal("2000.00"),
            outstanding_balance=Decimal("0.00"),
            cashier=self.owner,
            cashier_name=self.owner.full_name,
            completed_at=timezone.now() - timedelta(days=20),
        )
        SaleItem.objects.create(
            sale=older_sale,
            product=older_product,
            product_name=older_product.name,
            sku=older_product.sku,
            design_code="",
            unit=older_product.unit,
            quantity=100,
            unit_price=Decimal("20.00"),
            cost_price=Decimal("10.00"),
            line_total=Decimal("2000.00"),
        )

        payload = build_report_payload(
            business=self.business,
            report_type="weekly_management",
        )
        top_section = next(
            section
            for section in payload["sections"]
            if section["key"] == "top_products"
        )
        product_names = {
            row["name"]
            for row in top_section["rows"]
        }

        self.assertIn(self.product.name, product_names)
        self.assertNotIn(older_product.name, product_names)

    def test_owner_generates_and_reads_persisted_weekly_report(self):
        from intelligence.models import GeneratedReport

        self.client.force_authenticate(user=self.owner)

        create_response = self.client.post(
            reverse(
                "business-intelligence-reports",
                kwargs={"business_id": self.business.id},
            ),
            {
                "reportType": "weekly_management",
                "includeAiSummary": False,
            },
            format="json",
        )

        self.assertEqual(
            create_response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(
            create_response.data["reportType"],
            "weekly_management",
        )
        self.assertEqual(
            create_response.data["aiStatus"],
            "not_requested",
        )
        self.assertIn(
            "whatHappened",
            create_response.data["payload"]["managementQuestions"],
        )
        self.assertEqual(
            GeneratedReport.objects.filter(
                business=self.business,
            ).count(),
            1,
        )

        detail_response = self.client.get(
            reverse(
                "business-intelligence-report-detail",
                kwargs={
                    "business_id": self.business.id,
                    "report_id": create_response.data["id"],
                },
            )
        )
        self.assertEqual(
            detail_response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            detail_response.data["id"],
            create_response.data["id"],
        )

    @patch("intelligence.services.reports.generate_report_narrative")
    def test_ai_report_failure_keeps_deterministic_report_available(
        self,
        mocked_narrative,
    ):
        mocked_narrative.return_value = {
            "status": "unavailable",
            "narrative": "",
            "provider": "openai",
            "model": "gpt-5.6-luna",
        }
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            reverse(
                "business-intelligence-reports",
                kwargs={"business_id": self.business.id},
            ),
            {
                "reportType": "monthly_management",
                "includeAiSummary": True,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(response.data["aiStatus"], "unavailable")
        self.assertTrue(response.data["payload"]["metrics"])
        mocked_narrative.assert_called_once()

    def test_manager_can_list_intelligence_reports(self):
        from intelligence.models import GeneratedReport

        GeneratedReport.objects.create(
            business=self.business,
            generated_by=self.owner,
            report_type="daily_summary",
            title="Daily Business Summary",
            payload={},
        )
        self.client.force_authenticate(user=self.manager)

        response = self.client.get(
            reverse(
                "business-intelligence-reports",
                kwargs={"business_id": self.business.id},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_cashier_cannot_generate_intelligence_report(self):
        self.client.force_authenticate(user=self.cashier)

        response = self.client.post(
            reverse(
                "business-intelligence-reports",
                kwargs={"business_id": self.business.id},
            ),
            {"reportType": "weekly_management"},
            format="json",
        )

        self.assertIn(
            response.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
        )


    def test_owner_can_create_and_list_automation_rule(self):
        self.client.force_authenticate(user=self.owner)
        url = reverse(
            "business-intelligence-automation-rules",
            kwargs={"business_id": self.business.id},
        )

        response = self.client.post(
            url,
            {
                "ruleType": "risk_monitor",
                "isEnabled": True,
                "largeDiscountPercent": 20,
                "stockAdjustmentPercent": 25,
                "stockAdjustmentMinUnits": 5,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(response.data["ruleType"], "risk_monitor")
        self.assertEqual(
            response.data["scheduleFrequency"],
            "hourly",
        )
        self.assertIsNotNone(response.data["nextRunAt"])

        list_response = self.client.get(url)
        self.assertEqual(
            list_response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(len(list_response.data), 1)

    def test_weekly_automation_rejects_null_weekday_on_create_and_update(self):
        self.client.force_authenticate(user=self.owner)
        collection_url = reverse(
            "business-intelligence-automation-rules",
            kwargs={"business_id": self.business.id},
        )

        invalid_create = self.client.post(
            collection_url,
            {
                "ruleType": "weekly_management",
                "hourUtc": 8,
                "weekday": None,
            },
            format="json",
        )
        self.assertEqual(
            invalid_create.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        valid_create = self.client.post(
            collection_url,
            {
                "ruleType": "weekly_management",
                "hourUtc": 8,
                "weekday": 0,
            },
            format="json",
        )
        self.assertEqual(
            valid_create.status_code,
            status.HTTP_201_CREATED,
        )

        detail_url = reverse(
            "business-intelligence-automation-rule-detail",
            kwargs={
                "business_id": self.business.id,
                "rule_id": valid_create.data["id"],
            },
        )
        invalid_update = self.client.patch(
            detail_url,
            {"weekday": None},
            format="json",
        )
        self.assertEqual(
            invalid_update.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_cashier_cannot_access_automation_rules(self):
        self.client.force_authenticate(user=self.cashier)
        response = self.client.get(
            reverse(
                "business-intelligence-automation-rules",
                kwargs={"business_id": self.business.id},
            )
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
        )

    def test_transaction_event_window_includes_exact_scan_boundary(self):
        from intelligence.models import AutomationRule
        from intelligence.services.automation import _transaction_events

        rule = AutomationRule.objects.create(
            business=self.business,
            created_by=self.owner,
            rule_type=AutomationRule.RuleType.RISK_MONITOR,
            schedule_frequency=AutomationRule.ScheduleFrequency.HOURLY,
            is_enabled=True,
            config={
                "large_discount_percent": 20,
                "stock_adjustment_percent": 25,
                "stock_adjustment_min_units": 5,
                "first_run_lookback_hours": 24,
            },
        )

        movement = StockMovement.objects.create(
            business=self.business,
            product=self.product,
            movement_type=StockMovement.MovementType.ADJUSTMENT,
            quantity=5,
            previous_stock=1,
            new_stock=6,
            reason="Exact automation boundary test",
            created_by=self.owner,
        )

        events = _transaction_events(
            rule=rule,
            now=movement.created_at,
        )

        self.assertIn(
            "suspicious_stock_adjustment",
            {event.event_type for event in events},
        )

    @patch(
        "intelligence.services.automation.generate_and_store_recommendations"
    )
    def test_risk_monitor_creates_advisory_events_without_business_mutation(
        self,
        mocked_recommendations,
    ):
        from intelligence.models import AutomationEvent, AutomationRule
        from intelligence.services.automation import execute_automation_rule

        mocked_recommendations.return_value = {
            "recommendations": [],
        }
        rule = AutomationRule.objects.create(
            business=self.business,
            created_by=self.owner,
            rule_type=AutomationRule.RuleType.RISK_MONITOR,
            schedule_frequency=AutomationRule.ScheduleFrequency.HOURLY,
            is_enabled=True,
            config={
                "large_discount_percent": 20,
                "stock_adjustment_percent": 25,
                "stock_adjustment_min_units": 5,
                "first_run_lookback_hours": 24,
            },
        )

        discounted_sale = Sale.objects.create(
            business=self.business,
            customer=None,
            customer_name="Walk-in customer",
            customer_phone="",
            sale_number="INT-AUTO-DISCOUNT",
            invoice_number="INT-AUTO-DISCOUNT-INV",
            payment_method=Sale.PaymentMethod.CASH,
            status=Sale.Status.COMPLETED,
            subtotal=Decimal("100.00"),
            discount=Decimal("30.00"),
            total=Decimal("70.00"),
            amount_paid=Decimal("70.00"),
            outstanding_balance=Decimal("0.00"),
            cashier=self.owner,
            cashier_name=self.owner.full_name,
            completed_at=timezone.now() - timedelta(minutes=10),
        )

        StockMovement.objects.create(
            business=self.business,
            product=self.product,
            movement_type=StockMovement.MovementType.ADJUSTMENT,
            quantity=5,
            previous_stock=1,
            new_stock=6,
            reason="Automation review test",
            created_by=self.owner,
        )

        original_stock = self.product.stock
        original_sale_total = discounted_sale.total

        run = execute_automation_rule(
            rule,
            trigger_type="manual",
            requested_by=self.owner,
        )

        self.assertEqual(run.status, "completed")
        rule.refresh_from_db()
        self.assertIsNotNone(rule.last_run_at)
        self.assertIsNotNone(run.finished_at)
        self.assertLess(rule.last_run_at, run.finished_at)
        event_types = set(
            AutomationEvent.objects.filter(
                business=self.business,
            ).values_list("event_type", flat=True)
        )
        self.assertIn("low_stock", event_types)
        self.assertIn("large_discount", event_types)
        self.assertIn(
            "suspicious_stock_adjustment",
            event_types,
        )

        self.product.refresh_from_db()
        discounted_sale.refresh_from_db()
        self.assertEqual(self.product.stock, original_stock)
        self.assertEqual(
            discounted_sale.total,
            original_sale_total,
        )

    @patch(
        "intelligence.services.automation.generate_and_store_recommendations"
    )
    def test_risk_monitor_deduplicates_persistent_daily_events(
        self,
        mocked_recommendations,
    ):
        from intelligence.models import AutomationEvent, AutomationRule
        from intelligence.services.automation import execute_automation_rule

        mocked_recommendations.return_value = {
            "recommendations": [],
        }
        rule = AutomationRule.objects.create(
            business=self.business,
            created_by=self.owner,
            rule_type=AutomationRule.RuleType.RISK_MONITOR,
            schedule_frequency=AutomationRule.ScheduleFrequency.HOURLY,
            is_enabled=True,
            config={},
        )

        execute_automation_rule(
            rule,
            trigger_type="manual",
            requested_by=self.owner,
        )
        execute_automation_rule(
            rule,
            trigger_type="manual",
            requested_by=self.owner,
        )

        self.assertEqual(
            AutomationEvent.objects.filter(
                business=self.business,
                event_type="low_stock",
                evidence__productId=str(self.product.id),
            ).count(),
            1,
        )

    def test_daily_automation_generates_persisted_report(self):
        from intelligence.models import (
            AutomationEvent,
            AutomationRule,
            GeneratedReport,
        )
        from intelligence.services.automation import execute_automation_rule

        rule = AutomationRule.objects.create(
            business=self.business,
            created_by=self.owner,
            rule_type=AutomationRule.RuleType.DAILY_CLOSING,
            schedule_frequency=AutomationRule.ScheduleFrequency.DAILY,
            is_enabled=True,
            hour_utc=18,
            include_ai_summary=False,
        )

        run = execute_automation_rule(
            rule,
            trigger_type="manual",
            requested_by=self.owner,
        )

        self.assertEqual(run.status, "completed")
        self.assertEqual(
            GeneratedReport.objects.filter(
                business=self.business,
                report_type="daily_summary",
            ).count(),
            1,
        )
        self.assertEqual(
            AutomationEvent.objects.filter(
                business=self.business,
                event_type="report_generated",
            ).count(),
            1,
        )

    @patch(
        "intelligence.services.automation.generate_and_store_report",
        side_effect=RuntimeError("test failure"),
    )
    def test_failed_automation_records_safe_failure(self, mocked_report):
        from intelligence.models import AutomationRule, AutomationRun
        from intelligence.services.automation import execute_automation_rule

        rule = AutomationRule.objects.create(
            business=self.business,
            created_by=self.owner,
            rule_type=AutomationRule.RuleType.DAILY_CLOSING,
            schedule_frequency=AutomationRule.ScheduleFrequency.DAILY,
            is_enabled=True,
            hour_utc=18,
        )

        run = execute_automation_rule(
            rule,
            trigger_type="manual",
            requested_by=self.owner,
        )

        self.assertEqual(run.status, AutomationRun.Status.FAILED)
        self.assertEqual(
            run.error_message,
            (
                "Automation execution failed. StockFlow made no "
                "transactional business changes."
            ),
        )
        rule.refresh_from_db()
        self.assertEqual(rule.last_status, "failed")
        self.assertEqual(rule.consecutive_failures, 1)
        mocked_report.assert_called_once()

    def test_manager_can_run_rule_but_other_business_is_isolated(self):
        from intelligence.models import AutomationRule

        rule = AutomationRule.objects.create(
            business=self.business,
            created_by=self.owner,
            rule_type=AutomationRule.RuleType.DAILY_CLOSING,
            schedule_frequency=AutomationRule.ScheduleFrequency.DAILY,
            is_enabled=False,
            hour_utc=18,
        )

        self.client.force_authenticate(user=self.manager)
        response = self.client.post(
            reverse(
                "business-intelligence-automation-run-now",
                kwargs={
                    "business_id": self.business.id,
                    "rule_id": rule.id,
                },
            ),
            {},
            format="json",
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(response.data["status"], "completed")

        self.client.force_authenticate(user=self.outsider)
        denied = self.client.post(
            reverse(
                "business-intelligence-automation-run-now",
                kwargs={
                    "business_id": self.business.id,
                    "rule_id": rule.id,
                },
            ),
            {},
            format="json",
        )
        self.assertIn(
            denied.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
        )

    def test_due_automation_worker_advances_schedule_and_runs_rule(self):
        from intelligence.models import AutomationRule, AutomationRun
        from intelligence.services.automation import process_due_automations

        rule = AutomationRule.objects.create(
            business=self.business,
            created_by=self.owner,
            rule_type=AutomationRule.RuleType.DAILY_CLOSING,
            schedule_frequency=AutomationRule.ScheduleFrequency.DAILY,
            is_enabled=True,
            hour_utc=18,
            next_run_at=timezone.now() - timedelta(minutes=1),
        )

        result = process_due_automations(limit=10)

        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["completed"], 1)
        rule.refresh_from_db()
        self.assertGreater(rule.next_run_at, timezone.now())
        self.assertEqual(
            AutomationRun.objects.filter(
                business=self.business,
                rule=rule,
                trigger_type="scheduled",
                status="completed",
            ).count(),
            1,
        )

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
