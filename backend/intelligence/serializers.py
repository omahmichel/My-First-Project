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


class IntelligenceAnomalyBaselineSampleSerializer(
    serializers.Serializer
):
    date = serializers.DateField()
    revenue = serializers.DecimalField(
        max_digits=18,
        decimal_places=2,
    )


class IntelligenceSalesAnomalySerializer(serializers.Serializer):
    eligible = serializers.BooleanField()
    status = serializers.CharField()
    confidenceGrade = serializers.CharField(source="confidence_grade")
    evaluatedDate = serializers.DateField(source="evaluated_date")
    currentRevenue = serializers.DecimalField(
        source="current_revenue",
        max_digits=18,
        decimal_places=2,
    )
    baselineWeekday = serializers.CharField(source="baseline_weekday")
    baselineSampleCount = serializers.IntegerField(
        source="baseline_sample_count"
    )
    baselineAverageRevenue = serializers.DecimalField(
        source="baseline_average_revenue",
        max_digits=18,
        decimal_places=2,
    )
    percentageChange = serializers.DecimalField(
        source="percentage_change",
        max_digits=10,
        decimal_places=2,
        allow_null=True,
    )
    direction = serializers.CharField()
    thresholdPercent = serializers.DecimalField(
        source="threshold_percent",
        max_digits=10,
        decimal_places=2,
    )
    signalType = serializers.CharField(
        source="signal_type",
        allow_null=True,
    )
    severity = serializers.CharField(allow_null=True)
    baselineSamples = IntelligenceAnomalyBaselineSampleSerializer(
        source="baseline_samples",
        many=True,
    )


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
    anomalyBaselineOccurrences = serializers.IntegerField(
        source="anomaly_baseline_occurrences"
    )
    anomalyChangeThresholdPercent = serializers.DecimalField(
        source="anomaly_change_threshold_percent",
        max_digits=10,
        decimal_places=2,
    )
    anomalyMinActiveBaselines = serializers.IntegerField(
        source="anomaly_min_active_baselines"
    )
    anomalyComparison = serializers.CharField(
        source="anomaly_comparison"
    )
    confidenceLookbackDays = serializers.IntegerField(
        source="confidence_lookback_days"
    )



class IntelligenceForecastRequestSerializer(serializers.Serializer):
    horizonDays = serializers.ChoiceField(
        source="horizon_days",
        choices=(7, 30, 90),
    )


class IntelligenceForecastConfidenceSerializer(serializers.Serializer):
    grade = serializers.CharField()
    dataGrade = serializers.CharField(source="data_grade")
    historyDays = serializers.IntegerField(source="history_days")
    transactionCount = serializers.IntegerField(
        source="transaction_count"
    )
    activeSellingDays = serializers.IntegerField(
        source="active_selling_days"
    )
    dailyRevenueVariabilityPercent = serializers.DecimalField(
        source="daily_revenue_variability_percent",
        max_digits=10,
        decimal_places=2,
        allow_null=True,
    )
    reason = serializers.CharField()


class IntelligenceBusinessForecastSerializer(serializers.Serializer):
    expectedQuantity = serializers.DecimalField(
        source="expected_quantity",
        max_digits=18,
        decimal_places=2,
    )
    expectedRevenue = serializers.DecimalField(
        source="expected_revenue",
        max_digits=18,
        decimal_places=2,
    )
    expectedGrossProfit = serializers.DecimalField(
        source="expected_gross_profit",
        max_digits=18,
        decimal_places=2,
    )
    historicalMarginPercent = serializers.DecimalField(
        source="historical_margin_percent",
        max_digits=10,
        decimal_places=2,
    )
    dailyUnitVelocity = serializers.DecimalField(
        source="daily_unit_velocity",
        max_digits=18,
        decimal_places=2,
    )
    dailyRevenueVelocity = serializers.DecimalField(
        source="daily_revenue_velocity",
        max_digits=18,
        decimal_places=2,
    )
    revenueDirection = serializers.CharField(
        source="revenue_direction"
    )
    revenueTrendPercent = serializers.DecimalField(
        source="revenue_trend_percent",
        max_digits=10,
        decimal_places=2,
        allow_null=True,
    )
    stockOutRiskCount = serializers.IntegerField(
        source="stock_out_risk_count"
    )


class IntelligenceProductForecastSerializer(serializers.Serializer):
    productId = serializers.UUIDField(source="product_id")
    name = serializers.CharField()
    sku = serializers.CharField()
    category = serializers.CharField()
    availableStock = serializers.IntegerField(
        source="available_stock"
    )
    dailyDemand = serializers.DecimalField(
        source="daily_demand",
        max_digits=18,
        decimal_places=2,
    )
    expectedQuantity = serializers.DecimalField(
        source="expected_quantity",
        max_digits=18,
        decimal_places=2,
    )
    expectedRevenue = serializers.DecimalField(
        source="expected_revenue",
        max_digits=18,
        decimal_places=2,
    )
    expectedGrossProfit = serializers.DecimalField(
        source="expected_gross_profit",
        max_digits=18,
        decimal_places=2,
    )
    historicalMarginPercent = serializers.DecimalField(
        source="historical_margin_percent",
        max_digits=10,
        decimal_places=2,
    )
    demandDirection = serializers.CharField(
        source="demand_direction"
    )
    demandTrendPercent = serializers.DecimalField(
        source="demand_trend_percent",
        max_digits=10,
        decimal_places=2,
        allow_null=True,
    )
    activeSellingDays = serializers.IntegerField(
        source="active_selling_days"
    )
    confidenceGrade = serializers.CharField(
        source="confidence_grade"
    )
    daysOfStockRemaining = serializers.DecimalField(
        source="days_of_stock_remaining",
        max_digits=18,
        decimal_places=1,
        allow_null=True,
    )
    projectedStockOutDate = serializers.DateField(
        source="projected_stock_out_date",
        allow_null=True,
    )
    stockOutWithinHorizon = serializers.BooleanField(
        source="stock_out_within_horizon"
    )


class IntelligenceCategoryForecastSerializer(serializers.Serializer):
    category = serializers.CharField()
    productCount = serializers.IntegerField(
        source="product_count"
    )
    expectedQuantity = serializers.DecimalField(
        source="expected_quantity",
        max_digits=18,
        decimal_places=2,
    )
    expectedRevenue = serializers.DecimalField(
        source="expected_revenue",
        max_digits=18,
        decimal_places=2,
    )
    expectedGrossProfit = serializers.DecimalField(
        source="expected_gross_profit",
        max_digits=18,
        decimal_places=2,
    )
    stockOutRiskCount = serializers.IntegerField(
        source="stock_out_risk_count"
    )


class IntelligenceForecastMethodologySerializer(serializers.Serializer):
    lookbackDays = serializers.IntegerField(source="lookback_days")
    recentWindowDays = serializers.IntegerField(
        source="recent_window_days"
    )
    recentWeight = serializers.DecimalField(
        source="recent_weight",
        max_digits=4,
        decimal_places=2,
    )
    longTermWeight = serializers.DecimalField(
        source="long_term_weight",
        max_digits=4,
        decimal_places=2,
    )
    trendThresholdPercent = serializers.DecimalField(
        source="trend_threshold_percent",
        max_digits=10,
        decimal_places=2,
    )
    seasonalityStatus = serializers.CharField(
        source="seasonality_status"
    )
    recognizedSaleStatuses = serializers.ListField(
        source="recognized_sale_statuses",
        child=serializers.CharField(),
    )
    currentStockBasis = serializers.CharField(
        source="current_stock_basis"
    )
    completedDaysOnly = serializers.BooleanField(
        source="completed_days_only"
    )
    productMediumMinActiveDays = serializers.IntegerField(
        source="product_medium_min_active_days"
    )
    productHighMinActiveDays = serializers.IntegerField(
        source="product_high_min_active_days"
    )
    horizonConfidencePolicy = serializers.CharField(
        source="horizon_confidence_policy"
    )


class IntelligenceForecastRunSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    businessId = serializers.UUIDField(source="business_id")
    horizonDays = serializers.IntegerField(source="horizon_days")
    status = serializers.CharField()
    algorithm = serializers.CharField()
    algorithmVersion = serializers.CharField(
        source="algorithm_version"
    )
    historyStart = serializers.DateField(
        source="history_start",
        allow_null=True,
    )
    historyEnd = serializers.DateField(
        source="history_end",
        allow_null=True,
    )
    confidence = IntelligenceForecastConfidenceSerializer()
    businessForecast = IntelligenceBusinessForecastSerializer(
        source="results.business"
    )
    productForecasts = IntelligenceProductForecastSerializer(
        source="results.products",
        many=True,
    )
    categoryForecasts = IntelligenceCategoryForecastSerializer(
        source="results.categories",
        many=True,
    )
    methodology = IntelligenceForecastMethodologySerializer(
        source="parameters"
    )
    generatedAt = serializers.DateTimeField(source="generated_at")



class IntelligenceRecommendationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    insightType = serializers.CharField(source="insight_type")
    severity = serializers.CharField()
    confidence = serializers.CharField()
    title = serializers.CharField()
    summary = serializers.CharField()
    evidence = serializers.DictField()
    status = serializers.CharField()
    generatedAt = serializers.DateTimeField(source="generated_at")
    resolvedAt = serializers.DateTimeField(
        source="resolved_at",
        allow_null=True,
    )


class IntelligenceRecommendationCollectionSerializer(
    serializers.Serializer
):
    engine = serializers.CharField()
    forecastHorizonDays = serializers.IntegerField(
        source="forecast_horizon_days"
    )
    generatedAt = serializers.DateTimeField(source="generated_at")
    count = serializers.SerializerMethodField()
    recommendations = IntelligenceRecommendationSerializer(
        many=True
    )

    def get_count(self, obj):
        return len(obj["recommendations"])


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
    salesAnomaly = IntelligenceSalesAnomalySerializer(
        source="sales_anomaly"
    )
    confidence = IntelligenceConfidenceSerializer()
    methodology = IntelligenceMethodologySerializer()

class IntelligenceAnalystHistoryMessageSerializer(serializers.Serializer):
    role = serializers.ChoiceField(
        choices=("user", "assistant"),
    )
    content = serializers.CharField(
        max_length=1600,
        trim_whitespace=True,
    )


class IntelligenceAnalystRequestSerializer(serializers.Serializer):
    question = serializers.CharField(
        max_length=800,
        trim_whitespace=True,
    )
    history = IntelligenceAnalystHistoryMessageSerializer(
        many=True,
        required=False,
    )

    def validate_history(self, value):
        if len(value) > 6:
            raise serializers.ValidationError(
                "Only the six most recent chat messages may be sent."
            )
        return value


class IntelligenceAnalystResponseSerializer(serializers.Serializer):
    answer = serializers.CharField()
    provider = serializers.CharField()
    model = serializers.CharField()
    generatedAt = serializers.DateTimeField(source="generated_at")
    confidence = serializers.CharField()
    evidence = serializers.DictField()
    readOnly = serializers.BooleanField(source="read_only")

class IntelligenceReportRequestSerializer(serializers.Serializer):
    reportType = serializers.ChoiceField(
        source="report_type",
        choices=(
            "daily_summary",
            "weekly_management",
            "monthly_management",
            "sales_profit",
            "stock_risk_restocking",
            "supplier_balances",
            "customer_debt",
        ),
    )
    includeAiSummary = serializers.BooleanField(
        source="include_ai_summary",
        required=False,
        default=False,
    )


class IntelligenceGeneratedReportSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    businessId = serializers.UUIDField(source="business_id")
    reportType = serializers.CharField(source="report_type")
    title = serializers.CharField()
    periodStart = serializers.DateTimeField(
        source="period_start",
        allow_null=True,
    )
    periodEnd = serializers.DateTimeField(
        source="period_end",
        allow_null=True,
    )
    dataConfidence = serializers.CharField(source="data_confidence")
    payload = serializers.DictField()
    aiNarrative = serializers.CharField(source="ai_narrative")
    aiStatus = serializers.CharField(source="ai_status")
    aiProvider = serializers.CharField(source="ai_provider")
    aiModel = serializers.CharField(source="ai_model")
    generatedAt = serializers.DateTimeField(source="generated_at")
    generatedBy = serializers.SerializerMethodField()

    def get_generatedBy(self, obj):
        user = obj.generated_by
        if not user:
            return None
        return user.full_name or user.email


class IntelligenceAutomationRuleWriteSerializer(serializers.Serializer):
    ruleType = serializers.ChoiceField(
        source="rule_type",
        choices=(
            "risk_monitor",
            "daily_closing",
            "weekly_management",
        ),
        required=False,
    )
    isEnabled = serializers.BooleanField(
        source="is_enabled",
        required=False,
    )
    hourUtc = serializers.IntegerField(
        source="hour_utc",
        min_value=0,
        max_value=23,
        required=False,
    )
    weekday = serializers.IntegerField(
        min_value=0,
        max_value=6,
        required=False,
    )
    includeAiSummary = serializers.BooleanField(
        source="include_ai_summary",
        required=False,
    )
    largeDiscountPercent = serializers.IntegerField(
        source="large_discount_percent",
        min_value=1,
        max_value=100,
        required=False,
    )
    stockAdjustmentPercent = serializers.IntegerField(
        source="stock_adjustment_percent",
        min_value=1,
        max_value=1000,
        required=False,
    )
    stockAdjustmentMinUnits = serializers.IntegerField(
        source="stock_adjustment_min_units",
        min_value=1,
        max_value=1000000,
        required=False,
    )

    def validate(self, attrs):
        config = {}
        for input_key in (
            "large_discount_percent",
            "stock_adjustment_percent",
            "stock_adjustment_min_units",
        ):
            if input_key in attrs:
                config[input_key] = attrs.pop(input_key)

        if config:
            attrs["config"] = config
        return attrs


class IntelligenceAutomationRuleSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    businessId = serializers.UUIDField(source="business_id")
    ruleType = serializers.CharField(source="rule_type")
    scheduleFrequency = serializers.CharField(
        source="schedule_frequency"
    )
    isEnabled = serializers.BooleanField(source="is_enabled")
    hourUtc = serializers.IntegerField(source="hour_utc")
    weekday = serializers.IntegerField(allow_null=True)
    includeAiSummary = serializers.BooleanField(
        source="include_ai_summary"
    )
    config = serializers.DictField()
    nextRunAt = serializers.DateTimeField(
        source="next_run_at",
        allow_null=True,
    )
    lastRunAt = serializers.DateTimeField(
        source="last_run_at",
        allow_null=True,
    )
    lastStatus = serializers.CharField(
        source="last_status",
        allow_blank=True,
    )
    lastError = serializers.CharField(
        source="last_error",
        allow_blank=True,
    )
    consecutiveFailures = serializers.IntegerField(
        source="consecutive_failures"
    )
    createdAt = serializers.DateTimeField(source="created_at")
    updatedAt = serializers.DateTimeField(source="updated_at")


class IntelligenceAutomationEventSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    businessId = serializers.UUIDField(source="business_id")
    ruleId = serializers.UUIDField(source="rule_id", allow_null=True)
    eventType = serializers.CharField(source="event_type")
    severity = serializers.CharField()
    title = serializers.CharField()
    summary = serializers.CharField()
    evidence = serializers.DictField()
    generatedAt = serializers.DateTimeField(source="generated_at")


class IntelligenceAutomationRunSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    businessId = serializers.UUIDField(source="business_id")
    ruleId = serializers.UUIDField(source="rule_id", allow_null=True)
    triggerType = serializers.CharField(source="trigger_type")
    status = serializers.CharField()
    startedAt = serializers.DateTimeField(source="started_at")
    finishedAt = serializers.DateTimeField(
        source="finished_at",
        allow_null=True,
    )
    eventCount = serializers.IntegerField(source="event_count")
    result = serializers.DictField()
    errorCode = serializers.CharField(
        source="error_code",
        allow_blank=True,
    )
    errorMessage = serializers.CharField(
        source="error_message",
        allow_blank=True,
    )
