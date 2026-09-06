from rest_framework import serializers


class IntelligenceSalesSummarySerializer(serializers.Serializer):
    saleCount = serializers.IntegerField(source="sale_count")
    unitsSold = serializers.IntegerField(source="units_sold")
    revenue = serializers.DecimalField(max_digits=18, decimal_places=2)
    historicalCost = serializers.DecimalField(
        source="historical_cost", max_digits=18, decimal_places=2
    )
    grossProfit = serializers.DecimalField(
        source="gross_profit", max_digits=18, decimal_places=2
    )
    profitMargin = serializers.DecimalField(
        source="profit_margin", max_digits=8, decimal_places=2
    )


class IntelligenceSalesTrendSerializer(serializers.Serializer):
    periodDays = serializers.IntegerField(source="period_days")
    currentRevenue = serializers.DecimalField(
        source="current_revenue", max_digits=18, decimal_places=2
    )
    previousRevenue = serializers.DecimalField(
        source="previous_revenue", max_digits=18, decimal_places=2
    )
    absoluteChange = serializers.DecimalField(
        source="absolute_change", max_digits=18, decimal_places=2
    )
    percentageChange = serializers.DecimalField(
        source="percentage_change",
        max_digits=10,
        decimal_places=2,
        allow_null=True,
    )
    direction = serializers.CharField()
    currentSaleCount = serializers.IntegerField(source="current_sale_count")
    previousSaleCount = serializers.IntegerField(source="previous_sale_count")
    periodStart = serializers.DateTimeField(source="period_start")
    periodEnd = serializers.DateTimeField(source="period_end")


class IntelligencePeriodPerformanceEntrySerializer(
    serializers.Serializer
):
    saleCount = serializers.IntegerField(source="sale_count")
    unitsSold = serializers.IntegerField(source="units_sold")
    revenue = serializers.DecimalField(max_digits=18, decimal_places=2)
    historicalCost = serializers.DecimalField(
        source="historical_cost",
        max_digits=18,
        decimal_places=2,
    )
    grossProfit = serializers.DecimalField(
        source="gross_profit",
        max_digits=18,
        decimal_places=2,
    )
    profitMargin = serializers.DecimalField(
        source="profit_margin",
        max_digits=8,
        decimal_places=2,
    )
    previousSaleCount = serializers.IntegerField(
        source="previous_sale_count"
    )
    previousUnitsSold = serializers.IntegerField(
        source="previous_units_sold"
    )
    previousRevenue = serializers.DecimalField(
        source="previous_revenue",
        max_digits=18,
        decimal_places=2,
    )
    previousGrossProfit = serializers.DecimalField(
        source="previous_gross_profit",
        max_digits=18,
        decimal_places=2,
    )
    revenueChange = serializers.DecimalField(
        source="revenue_change",
        max_digits=18,
        decimal_places=2,
    )
    revenueChangePercentage = serializers.DecimalField(
        source="revenue_change_percentage",
        max_digits=10,
        decimal_places=2,
        allow_null=True,
    )
    revenueDirection = serializers.CharField(
        source="revenue_direction"
    )
    grossProfitChange = serializers.DecimalField(
        source="gross_profit_change",
        max_digits=18,
        decimal_places=2,
    )
    grossProfitChangePercentage = serializers.DecimalField(
        source="gross_profit_change_percentage",
        max_digits=10,
        decimal_places=2,
        allow_null=True,
    )
    grossProfitDirection = serializers.CharField(
        source="gross_profit_direction"
    )
    periodStart = serializers.DateTimeField(source="period_start")
    periodEnd = serializers.DateTimeField(source="period_end")
    previousPeriodStart = serializers.DateTimeField(
        source="previous_period_start"
    )
    previousPeriodEnd = serializers.DateTimeField(
        source="previous_period_end"
    )


class IntelligencePerformancePeriodsSerializer(serializers.Serializer):
    today = IntelligencePeriodPerformanceEntrySerializer()
    last7Days = IntelligencePeriodPerformanceEntrySerializer(
        source="last_7_days"
    )
    last30Days = IntelligencePeriodPerformanceEntrySerializer(
        source="last_30_days"
    )


class IntelligenceInventorySummarySerializer(serializers.Serializer):
    activeProductCount = serializers.IntegerField(source="active_product_count")
    totalStockUnits = serializers.IntegerField(source="total_stock_units")
    reservedStockUnits = serializers.IntegerField(source="reserved_stock_units")
    availableStockUnits = serializers.IntegerField(source="available_stock_units")
    inventoryCostValue = serializers.DecimalField(
        source="inventory_cost_value", max_digits=18, decimal_places=2
    )
    availableInventoryCostValue = serializers.DecimalField(
        source="available_inventory_cost_value", max_digits=18, decimal_places=2
    )
    potentialRetailValue = serializers.DecimalField(
        source="potential_retail_value", max_digits=18, decimal_places=2
    )
    lowStockCount = serializers.IntegerField(source="low_stock_count")


class IntelligenceDebtSummarySerializer(serializers.Serializer):
    customerDebt = serializers.DecimalField(
        source="customer_debt", max_digits=18, decimal_places=2
    )
    supplierDebt = serializers.DecimalField(
        source="supplier_debt", max_digits=18, decimal_places=2
    )
    customersWithDebt = serializers.IntegerField(source="customers_with_debt")
    supplierPurchasesWithBalance = serializers.IntegerField(
        source="supplier_purchases_with_balance"
    )


class IntelligenceTopProductSerializer(serializers.Serializer):
    productId = serializers.UUIDField(source="product_id")
    name = serializers.CharField()
    sku = serializers.CharField()
    quantitySold = serializers.IntegerField(source="quantity_sold")
    lastSaleAt = serializers.DateTimeField(source="last_sale_at", allow_null=True)


class IntelligenceMovementCandidateSerializer(serializers.Serializer):
    productId = serializers.UUIDField(source="product_id")
    name = serializers.CharField()
    sku = serializers.CharField()
    availableStock = serializers.IntegerField(source="available_stock")
    inventoryCostValue = serializers.DecimalField(
        source="inventory_cost_value", max_digits=18, decimal_places=2
    )
    daysSinceLastSale = serializers.IntegerField(source="days_since_last_sale")
    lastSaleAt = serializers.DateTimeField(source="last_sale_at", allow_null=True)


class IntelligenceStockOutRiskSerializer(serializers.Serializer):
    productId = serializers.UUIDField(source="product_id")
    name = serializers.CharField()
    sku = serializers.CharField()
    availableStock = serializers.IntegerField(source="available_stock")
    averageDailyDemand = serializers.DecimalField(
        source="average_daily_demand", max_digits=14, decimal_places=2
    )
    estimatedDaysRemaining = serializers.DecimalField(
        source="estimated_days_remaining", max_digits=14, decimal_places=1
    )


class IntelligenceProductRulesSerializer(serializers.Serializer):
    slowMovingDays = serializers.IntegerField(source="slow_moving_days")
    deadStockDays = serializers.IntegerField(source="dead_stock_days")
    stockOutRiskDays = serializers.IntegerField(source="stock_out_risk_days")


class IntelligenceProductPerformanceSerializer(serializers.Serializer):
    topProducts = IntelligenceTopProductSerializer(source="top_products", many=True)
    slowMovingProducts = IntelligenceMovementCandidateSerializer(
        source="slow_moving_products", many=True
    )
    deadStockCandidates = IntelligenceMovementCandidateSerializer(
        source="dead_stock_candidates", many=True
    )
    stockOutRisks = IntelligenceStockOutRiskSerializer(
        source="stock_out_risks", many=True
    )
    rules = IntelligenceProductRulesSerializer()


class IntelligenceProductProfitabilityEntrySerializer(
    serializers.Serializer
):
    productId = serializers.UUIDField(
        source="product_id",
        allow_null=True,
    )
    name = serializers.CharField()
    sku = serializers.CharField()
    quantitySold = serializers.IntegerField(source="quantity_sold")
    realizedRevenue = serializers.DecimalField(
        source="realized_revenue",
        max_digits=18,
        decimal_places=2,
    )
    historicalCost = serializers.DecimalField(
        source="historical_cost",
        max_digits=18,
        decimal_places=2,
    )
    grossProfit = serializers.DecimalField(
        source="gross_profit",
        max_digits=18,
        decimal_places=2,
    )
    profitMargin = serializers.DecimalField(
        source="profit_margin",
        max_digits=10,
        decimal_places=2,
    )
    previousRealizedRevenue = serializers.DecimalField(
        source="previous_realized_revenue",
        max_digits=18,
        decimal_places=2,
    )
    previousGrossProfit = serializers.DecimalField(
        source="previous_gross_profit",
        max_digits=18,
        decimal_places=2,
    )
    previousProfitMargin = serializers.DecimalField(
        source="previous_profit_margin",
        max_digits=10,
        decimal_places=2,
        allow_null=True,
    )
    marginChangePoints = serializers.DecimalField(
        source="margin_change_points",
        max_digits=10,
        decimal_places=2,
        allow_null=True,
    )


class IntelligenceProductProfitabilitySerializer(serializers.Serializer):
    periodDays = serializers.IntegerField(source="period_days")
    comparisonPeriodDays = serializers.IntegerField(
        source="comparison_period_days"
    )
    discountAllocationMethod = serializers.CharField(
        source="discount_allocation_method"
    )
    discountRoundingMethod = serializers.CharField(
        source="discount_rounding_method"
    )
    bestPerformingProducts = (
        IntelligenceProductProfitabilityEntrySerializer(
            source="best_performing_products",
            many=True,
        )
    )
    worstPerformingProducts = (
        IntelligenceProductProfitabilityEntrySerializer(
            source="worst_performing_products",
            many=True,
        )
    )
    marginDeterioration = (
        IntelligenceProductProfitabilityEntrySerializer(
            source="margin_deterioration",
            many=True,
        )
    )


class IntelligenceOverstockCandidateSerializer(
    serializers.Serializer
):
    productId = serializers.UUIDField(source="product_id")
    name = serializers.CharField()
    sku = serializers.CharField()
    availableStock = serializers.IntegerField(source="available_stock")
    quantitySold30d = serializers.IntegerField(source="quantity_sold_30d")
    averageDailyDemand = serializers.DecimalField(
        source="average_daily_demand",
        max_digits=14,
        decimal_places=2,
    )
    estimatedDaysOfCover = serializers.DecimalField(
        source="estimated_days_of_cover",
        max_digits=14,
        decimal_places=1,
    )
    targetStockUnits = serializers.IntegerField(
        source="target_stock_units"
    )
    excessUnits = serializers.IntegerField(source="excess_units")
    currentCostPrice = serializers.DecimalField(
        source="current_cost_price",
        max_digits=18,
        decimal_places=2,
    )
    excessCostValue = serializers.DecimalField(
        source="excess_cost_value",
        max_digits=18,
        decimal_places=2,
    )
    lastStockInAt = serializers.DateTimeField(
        source="last_stock_in_at",
        allow_null=True,
    )


class IntelligenceInventoryOverstockSerializer(serializers.Serializer):
    demandLookbackDays = serializers.IntegerField(
        source="demand_lookback_days"
    )
    overstockCoverDays = serializers.IntegerField(
        source="overstock_cover_days"
    )
    candidateCount = serializers.IntegerField(source="candidate_count")
    totalExcessUnits = serializers.IntegerField(
        source="total_excess_units"
    )
    totalExcessCostValue = serializers.DecimalField(
        source="total_excess_cost_value",
        max_digits=18,
        decimal_places=2,
    )
    method = serializers.CharField()
    candidates = IntelligenceOverstockCandidateSerializer(many=True)


class IntelligenceConfidenceSerializer(serializers.Serializer):
    grade = serializers.CharField()
    historyDays = serializers.IntegerField(source="history_days")
    transactionCount60d = serializers.IntegerField(source="transaction_count_60d")
    activeSellingDays60d = serializers.IntegerField(source="active_selling_days_60d")
    lookbackDays = serializers.IntegerField(source="lookback_days")


class IntelligenceBusinessHealthSerializer(serializers.Serializer):
    status = serializers.CharField()
    attentionCount = serializers.IntegerField(source="attention_count")
    reasons = serializers.ListField(child=serializers.CharField())


class IntelligenceMethodologySerializer(serializers.Serializer):
    recognizedSaleStatuses = serializers.ListField(
        source="recognized_sale_statuses", child=serializers.CharField()
    )
    salesSummaryScope = serializers.CharField(source="sales_summary_scope")
    periodPerformanceWindows = serializers.ListField(
        source="period_performance_windows",
        child=serializers.CharField(),
    )
    todayComparisonBasis = serializers.CharField(
        source="today_comparison_basis"
    )
    salesTrendDays = serializers.IntegerField(source="sales_trend_days")
    slowMovingDays = serializers.IntegerField(source="slow_moving_days")
    deadStockDays = serializers.IntegerField(source="dead_stock_days")
    stockOutRiskDays = serializers.IntegerField(source="stock_out_risk_days")
    overstockCoverDays = serializers.IntegerField(
        source="overstock_cover_days"
    )
    overstockMethod = serializers.CharField(source="overstock_method")
    confidenceLookbackDays = serializers.IntegerField(
        source="confidence_lookback_days"
    )


class BusinessIntelligenceOverviewSerializer(serializers.Serializer):
    businessId = serializers.UUIDField(source="business_id")
    businessName = serializers.CharField(source="business_name")
    generatedAt = serializers.DateTimeField(source="generated_at")
    businessHealth = IntelligenceBusinessHealthSerializer(source="business_health")
    sales = IntelligenceSalesSummarySerializer()
    performancePeriods = IntelligencePerformancePeriodsSerializer(
        source="performance_periods"
    )
    salesTrend = IntelligenceSalesTrendSerializer(source="sales_trend")
    inventory = IntelligenceInventorySummarySerializer()
    debts = IntelligenceDebtSummarySerializer()
    products = IntelligenceProductPerformanceSerializer()
    productProfitability = IntelligenceProductProfitabilitySerializer(
        source="product_profitability"
    )
    inventoryOverstock = IntelligenceInventoryOverstockSerializer(
        source="inventory_overstock"
    )
    confidence = IntelligenceConfidenceSerializer()
    methodology = IntelligenceMethodologySerializer()
