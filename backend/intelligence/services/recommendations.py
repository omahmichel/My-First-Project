from decimal import Decimal

from django.utils import timezone

from intelligence.models import BusinessInsight
from intelligence.services.business_analysis import (
    ZERO_MONEY,
    calculate_business_overview,
    money,
)
from intelligence.services.forecasting import calculate_forecast


RECOMMENDATION_ENGINE = "deterministic_recommendation_v1"
RECOMMENDATION_FORECAST_HORIZON_DAYS = 30
RESTOCK_HIGH_URGENCY_DAYS = 7
MAX_PRODUCT_RECOMMENDATIONS_PER_SIGNAL = 5

SEVERITY_RANK = {
    BusinessInsight.Severity.HIGH: 0,
    BusinessInsight.Severity.ATTENTION: 1,
    BusinessInsight.Severity.INFO: 2,
}


def _decimal(value):
    if value is None:
        return ZERO_MONEY
    return Decimal(str(value))


def _money_string(value):
    return str(money(_decimal(value)))


def _decimal_string(value, pattern="0.01"):
    if value is None:
        return None
    return str(_decimal(value).quantize(Decimal(pattern)))


def _normalize_confidence(value):
    if value in {
        BusinessInsight.Confidence.HIGH,
        BusinessInsight.Confidence.MEDIUM,
        BusinessInsight.Confidence.LOW,
    }:
        return value
    return BusinessInsight.Confidence.LOW


def _base_evidence(*, recommendation_code, source):
    return {
        "engine": RECOMMENDATION_ENGINE,
        "recommendation_code": recommendation_code,
        "source": source,
    }


def _restock_recommendations(*, forecast):
    recommendations = []

    for product in forecast["results"]["products"]:
        if not product["stock_out_within_horizon"]:
            continue

        daily_demand = _decimal(product["daily_demand"])
        if daily_demand <= ZERO_MONEY:
            continue

        days_remaining = _decimal(
            product["days_of_stock_remaining"]
        )
        severity = (
            BusinessInsight.Severity.HIGH
            if days_remaining <= Decimal(
                RESTOCK_HIGH_URGENCY_DAYS
            )
            else BusinessInsight.Severity.ATTENTION
        )

        stock_out_date = product["projected_stock_out_date"]
        recommendations.append(
            {
                "insight_type": BusinessInsight.InsightType.INVENTORY,
                "severity": severity,
                "confidence": _normalize_confidence(
                    product["confidence_grade"]
                ),
                "title": f'Restock {product["name"]} before stock-out',
                "summary": (
                    f'{product["name"]} has '
                    f'{product["available_stock"]} available unit(s) '
                    f'and is projected to run out around '
                    f'{stock_out_date}. Review and confirm a restock '
                    f'decision before the projected stock-out.'
                ),
                "evidence": {
                    **_base_evidence(
                        recommendation_code="restock_stockout_risk",
                        source="forecast_30d",
                    ),
                    "product_id": product["product_id"],
                    "name": product["name"],
                    "sku": product["sku"],
                    "available_stock": product["available_stock"],
                    "daily_demand": _decimal_string(
                        product["daily_demand"]
                    ),
                    "days_of_stock_remaining": _decimal_string(
                        product["days_of_stock_remaining"],
                        "0.1",
                    ),
                    "projected_stock_out_date": stock_out_date,
                    "forecast_horizon_days": (
                        RECOMMENDATION_FORECAST_HORIZON_DAYS
                    ),
                    "expected_quantity": _decimal_string(
                        product["expected_quantity"]
                    ),
                    "restock_high_urgency_days": (
                        RESTOCK_HIGH_URGENCY_DAYS
                    ),
                },
            }
        )

    recommendations.sort(
        key=lambda item: (
            SEVERITY_RANK[item["severity"]],
            _decimal(
                item["evidence"]["days_of_stock_remaining"]
            ),
            item["title"],
        )
    )
    return recommendations[
        :MAX_PRODUCT_RECOMMENDATIONS_PER_SIGNAL
    ]


def _overstock_recommendations(*, overview):
    recommendations = []

    for candidate in overview["inventory_overstock"]["candidates"]:
        recommendations.append(
            {
                "insight_type": BusinessInsight.InsightType.INVENTORY,
                "severity": BusinessInsight.Severity.ATTENTION,
                "confidence": _normalize_confidence(
                    overview["confidence"]["grade"]
                ),
                "title": f'Review excess stock for {candidate["name"]}',
                "summary": (
                    f'{candidate["name"]} has an estimated '
                    f'{candidate["excess_units"]} excess unit(s), '
                    f'tying up about GHS '
                    f'{_money_string(candidate["excess_cost_value"])} '
                    f'at current cost. Review purchasing, pricing, '
                    f'or promotion decisions before the next restock.'
                ),
                "evidence": {
                    **_base_evidence(
                        recommendation_code="reduce_overstock_exposure",
                        source="inventory_overstock",
                    ),
                    "product_id": str(candidate["product_id"]),
                    "name": candidate["name"],
                    "sku": candidate["sku"],
                    "available_stock": candidate["available_stock"],
                    "quantity_sold_30d": (
                        candidate["quantity_sold_30d"]
                    ),
                    "target_stock_units": (
                        candidate["target_stock_units"]
                    ),
                    "excess_units": candidate["excess_units"],
                    "estimated_days_of_cover": _decimal_string(
                        candidate["estimated_days_of_cover"],
                        "0.1",
                    ),
                    "excess_cost_value": _money_string(
                        candidate["excess_cost_value"]
                    ),
                    "overstock_cover_days": overview[
                        "inventory_overstock"
                    ]["overstock_cover_days"],
                },
            }
        )

    return recommendations[
        :MAX_PRODUCT_RECOMMENDATIONS_PER_SIGNAL
    ]


def _margin_recommendations(*, overview):
    recommendations = []

    for product in overview["product_profitability"][
        "margin_deterioration"
    ]:
        recommendations.append(
            {
                "insight_type": BusinessInsight.InsightType.MARGIN,
                "severity": BusinessInsight.Severity.ATTENTION,
                "confidence": _normalize_confidence(
                    overview["confidence"]["grade"]
                ),
                "title": f'Review margin decline for {product["name"]}',
                "summary": (
                    f'{product["name"]} margin moved from '
                    f'{_decimal_string(product["previous_profit_margin"])}% '
                    f'to {_decimal_string(product["profit_margin"])}%, '
                    f'a change of '
                    f'{_decimal_string(product["margin_change_points"])} '
                    f'percentage points. Review current selling price, '
                    f'cost changes, and discounting before taking action.'
                ),
                "evidence": {
                    **_base_evidence(
                        recommendation_code="review_margin_deterioration",
                        source="product_profitability",
                    ),
                    "product_id": str(product["product_id"]),
                    "name": product["name"],
                    "sku": product["sku"],
                    "profit_margin": _decimal_string(
                        product["profit_margin"]
                    ),
                    "previous_profit_margin": _decimal_string(
                        product["previous_profit_margin"]
                    ),
                    "margin_change_points": _decimal_string(
                        product["margin_change_points"]
                    ),
                    "realized_revenue": _money_string(
                        product["realized_revenue"]
                    ),
                    "gross_profit": _money_string(
                        product["gross_profit"]
                    ),
                    "comparison_period_days": overview[
                        "product_profitability"
                    ]["comparison_period_days"],
                },
            }
        )

    return recommendations[
        :MAX_PRODUCT_RECOMMENDATIONS_PER_SIGNAL
    ]


def _anomaly_recommendations(*, overview):
    anomaly = overview["sales_anomaly"]

    if anomaly["status"] != "anomaly":
        return []

    signal_type = anomaly["signal_type"]
    direction_word = (
        "spike" if signal_type == "revenue_spike" else "drop"
    )

    return [
        {
            "insight_type": BusinessInsight.InsightType.ANOMALY,
            "severity": (
                anomaly["severity"]
                or BusinessInsight.Severity.ATTENTION
            ),
            "confidence": _normalize_confidence(
                anomaly["confidence_grade"]
            ),
            "title": f"Investigate unusual revenue {direction_word}",
            "summary": (
                f'Recognized revenue on '
                f'{anomaly["evaluated_date"]} was GHS '
                f'{_money_string(anomaly["current_revenue"])} versus '
                f'a same-weekday baseline of GHS '
                f'{_money_string(anomaly["baseline_average_revenue"])}. '
                f'Review the underlying sales before treating the '
                f'change as a lasting business trend.'
            ),
            "evidence": {
                **_base_evidence(
                    recommendation_code="investigate_sales_anomaly",
                    source="sales_anomaly",
                ),
                "evaluated_date": str(anomaly["evaluated_date"]),
                "signal_type": signal_type,
                "current_revenue": _money_string(
                    anomaly["current_revenue"]
                ),
                "baseline_average_revenue": _money_string(
                    anomaly["baseline_average_revenue"]
                ),
                "percentage_change": _decimal_string(
                    anomaly["percentage_change"]
                ),
                "baseline_sample_count": (
                    anomaly["baseline_sample_count"]
                ),
                "threshold_percent": _decimal_string(
                    anomaly["threshold_percent"]
                ),
            },
        }
    ]


def _debt_recommendations(*, overview):
    recommendations = []
    confidence = _normalize_confidence(
        overview["confidence"]["grade"]
    )
    debts = overview["debts"]

    if debts["customer_debt"] > ZERO_MONEY:
        recommendations.append(
            {
                "insight_type": BusinessInsight.InsightType.DEBT,
                "severity": BusinessInsight.Severity.ATTENTION,
                "confidence": confidence,
                "title": "Follow up outstanding customer debt",
                "summary": (
                    f'Outstanding customer debt is GHS '
                    f'{_money_string(debts["customer_debt"])} across '
                    f'{debts["customers_with_debt"]} customer(s). '
                    f'Review the debt ledger and follow up due balances '
                    f'without altering any payment records automatically.'
                ),
                "evidence": {
                    **_base_evidence(
                        recommendation_code="collect_customer_debt",
                        source="debt_summary",
                    ),
                    "customer_debt": _money_string(
                        debts["customer_debt"]
                    ),
                    "customers_with_debt": (
                        debts["customers_with_debt"]
                    ),
                },
            }
        )

    if debts["supplier_debt"] > ZERO_MONEY:
        recommendations.append(
            {
                "insight_type": BusinessInsight.InsightType.DEBT,
                "severity": BusinessInsight.Severity.ATTENTION,
                "confidence": confidence,
                "title": "Review outstanding supplier balances",
                "summary": (
                    f'Outstanding supplier debt is GHS '
                    f'{_money_string(debts["supplier_debt"])} across '
                    f'{debts["supplier_purchases_with_balance"]} '
                    f'purchase(s). Review due balances and cash '
                    f'capacity before confirming supplier payments.'
                ),
                "evidence": {
                    **_base_evidence(
                        recommendation_code="review_supplier_debt",
                        source="debt_summary",
                    ),
                    "supplier_debt": _money_string(
                        debts["supplier_debt"]
                    ),
                    "supplier_purchases_with_balance": (
                        debts["supplier_purchases_with_balance"]
                    ),
                },
            }
        )

    return recommendations


def _performance_recommendations(*, overview):
    trend = overview["sales_trend"]

    if (
        trend["direction"] != "down"
        or trend["previous_revenue"] <= ZERO_MONEY
    ):
        return []

    return [
        {
            "insight_type": BusinessInsight.InsightType.PERFORMANCE,
            "severity": BusinessInsight.Severity.ATTENTION,
            "confidence": _normalize_confidence(
                overview["confidence"]["grade"]
            ),
            "title": "Review the 30-day revenue decline",
            "summary": (
                f'Recognized revenue for the current '
                f'{trend["period_days"]}-day period is GHS '
                f'{_money_string(trend["current_revenue"])} versus '
                f'GHS {_money_string(trend["previous_revenue"])} in '
                f'the previous period. Review product mix, demand, '
                f'pricing, and sales activity before changing strategy.'
            ),
            "evidence": {
                **_base_evidence(
                    recommendation_code="review_revenue_decline",
                    source="sales_trend",
                ),
                "period_days": trend["period_days"],
                "current_revenue": _money_string(
                    trend["current_revenue"]
                ),
                "previous_revenue": _money_string(
                    trend["previous_revenue"]
                ),
                "absolute_change": _money_string(
                    trend["absolute_change"]
                ),
                "percentage_change": _decimal_string(
                    trend["percentage_change"]
                ),
            },
        }
    ]


def build_recommendations(business, *, as_of=None):
    now = as_of or timezone.now()
    overview = calculate_business_overview(
        business,
        as_of=now,
    )
    forecast = calculate_forecast(
        business,
        horizon_days=RECOMMENDATION_FORECAST_HORIZON_DAYS,
        as_of=now,
    )

    recommendations = []
    recommendations.extend(
        _restock_recommendations(forecast=forecast)
    )
    recommendations.extend(
        _overstock_recommendations(overview=overview)
    )
    recommendations.extend(
        _margin_recommendations(overview=overview)
    )
    recommendations.extend(
        _anomaly_recommendations(overview=overview)
    )
    recommendations.extend(
        _debt_recommendations(overview=overview)
    )
    recommendations.extend(
        _performance_recommendations(overview=overview)
    )

    recommendations.sort(
        key=lambda item: (
            SEVERITY_RANK[item["severity"]],
            item["insight_type"],
            item["title"],
        )
    )

    return {
        "engine": RECOMMENDATION_ENGINE,
        "forecast_horizon_days": (
            RECOMMENDATION_FORECAST_HORIZON_DAYS
        ),
        "generated_at": now,
        "recommendations": recommendations,
    }


def _engine_active_insights(business):
    return [
        insight
        for insight in BusinessInsight.objects.filter(
            business=business,
            status=BusinessInsight.Status.ACTIVE,
        ).order_by("-generated_at")
        if (
            isinstance(insight.evidence, dict)
            and insight.evidence.get("engine")
            == RECOMMENDATION_ENGINE
        )
    ]


def get_active_recommendations(business):
    return _engine_active_insights(business)


def generate_and_store_recommendations(
    business,
    *,
    as_of=None,
):
    built = build_recommendations(
        business,
        as_of=as_of,
    )
    generated_at = built["generated_at"]

    previous = _engine_active_insights(business)
    if previous:
        BusinessInsight.objects.filter(
            id__in=[insight.id for insight in previous]
        ).update(
            status=BusinessInsight.Status.RESOLVED,
            resolved_at=generated_at,
        )

    created = []
    for recommendation in built["recommendations"]:
        created.append(
            BusinessInsight.objects.create(
                business=business,
                insight_type=recommendation["insight_type"],
                severity=recommendation["severity"],
                confidence=recommendation["confidence"],
                title=recommendation["title"],
                summary=recommendation["summary"],
                evidence=recommendation["evidence"],
                status=BusinessInsight.Status.ACTIVE,
            )
        )

    return {
        "engine": built["engine"],
        "forecast_horizon_days": built[
            "forecast_horizon_days"
        ],
        "generated_at": generated_at,
        "recommendations": created,
    }
