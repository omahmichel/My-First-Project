import json

from ..models import ForecastRun
from ..serializers import (
    BusinessIntelligenceOverviewSerializer,
    IntelligenceRecommendationSerializer,
)
from ..services.business_analysis import calculate_business_overview
from ..services.recommendations import get_active_recommendations


FORECAST_HORIZONS = (7, 30, 90)
MAX_FORECAST_PRODUCTS = 8
MAX_FORECAST_CATEGORIES = 8


def _json_safe(value):
    return json.loads(
        json.dumps(
            value,
            default=str,
            ensure_ascii=False,
        )
    )


def _compact_forecast(run):
    results = run.results or {}
    products = list(results.get("products", []))
    categories = list(results.get("categories", []))

    products.sort(
        key=lambda item: (
            not bool(item.get("stock_out_within_horizon")),
            -float(item.get("expected_revenue") or 0),
            str(item.get("name") or ""),
        )
    )
    categories.sort(
        key=lambda item: (
            -float(item.get("expected_revenue") or 0),
            str(item.get("category") or ""),
        )
    )

    return {
        "horizon_days": run.horizon_days,
        "generated_at": run.generated_at,
        "history_start": run.history_start,
        "history_end": run.history_end,
        "confidence": run.confidence,
        "business": results.get("business", {}),
        "products": products[:MAX_FORECAST_PRODUCTS],
        "categories": categories[:MAX_FORECAST_CATEGORIES],
        "methodology": run.parameters,
    }


def _latest_forecasts(business):
    runs = ForecastRun.objects.filter(
        business=business,
        status=ForecastRun.Status.COMPLETED,
        horizon_days__in=FORECAST_HORIZONS,
    ).order_by("-generated_at")

    latest = {}
    for run in runs:
        if run.horizon_days in latest:
            continue
        latest[run.horizon_days] = _compact_forecast(run)
        if len(latest) == len(FORECAST_HORIZONS):
            break

    return {
        str(horizon): latest[horizon]
        for horizon in FORECAST_HORIZONS
        if horizon in latest
    }


def build_verified_intelligence_context(business):
    overview = calculate_business_overview(business)
    overview_data = BusinessIntelligenceOverviewSerializer(
        instance=overview
    ).data

    recommendations = IntelligenceRecommendationSerializer(
        instance=get_active_recommendations(business),
        many=True,
    ).data

    context = {
        "business": {
            "id": str(business.id),
            "name": business.name,
            "business_type": business.business_type,
        },
        "overview": {
            "generated_at": overview_data.get("generatedAt"),
            "business_health": overview_data.get("businessHealth"),
            "sales": overview_data.get("sales"),
            "performance_periods": overview_data.get(
                "performancePeriods"
            ),
            "sales_trend": overview_data.get("salesTrend"),
            "inventory": overview_data.get("inventory"),
            "debts": overview_data.get("debts"),
            "products": overview_data.get("products"),
            "product_profitability": overview_data.get(
                "productProfitability"
            ),
            "inventory_overstock": overview_data.get(
                "inventoryOverstock"
            ),
            "sales_anomaly": overview_data.get("salesAnomaly"),
            "confidence": overview_data.get("confidence"),
            "methodology": overview_data.get("methodology"),
        },
        "stored_forecasts": _latest_forecasts(business),
        "active_recommendations": recommendations,
    }
    return _json_safe(context)


def build_context_evidence(context):
    overview = context.get("overview", {})
    forecasts = context.get("stored_forecasts", {})
    recommendations = context.get("active_recommendations", [])
    confidence = overview.get("confidence") or {}

    return {
        "overallConfidence": confidence.get("grade", "low"),
        "overviewGeneratedAt": overview.get("generated_at"),
        "availableForecastHorizons": [
            int(horizon)
            for horizon in forecasts.keys()
        ],
        "activeRecommendationCount": len(recommendations),
        "sources": [
            "verified_intelligence_overview",
            "stored_forecasts",
            "active_recommendations",
        ],
    }
