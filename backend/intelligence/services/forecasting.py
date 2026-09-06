from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal, ROUND_CEILING

from django.utils import timezone

from inventory.models import Product
from sales.models import Sale

from intelligence.models import ForecastRun
from intelligence.services.business_analysis import (
    RECOGNIZED_SALE_STATUSES,
    ZERO_MONEY,
    _sale_item_realized_revenues,
    money,
)


FORECAST_LOOKBACK_DAYS = 60
FORECAST_RECENT_DAYS = 14
FORECAST_RECENT_WEIGHT = Decimal("0.65")
FORECAST_LONG_TERM_WEIGHT = Decimal("0.35")
FORECAST_TREND_THRESHOLD_PERCENT = Decimal("10.00")
PRODUCT_MEDIUM_MIN_ACTIVE_DAYS = 5
PRODUCT_HIGH_MIN_ACTIVE_DAYS = 10
SUPPORTED_FORECAST_HORIZONS = {
    ForecastRun.Horizon.SEVEN_DAYS,
    ForecastRun.Horizon.THIRTY_DAYS,
    ForecastRun.Horizon.NINETY_DAYS,
}


def _mean(values):
    if not values:
        return ZERO_MONEY
    return sum(values, ZERO_MONEY) / Decimal(len(values))


def _weighted_velocity(values):
    if not values:
        return ZERO_MONEY

    recent_values = values[-min(FORECAST_RECENT_DAYS, len(values)):]
    recent_average = _mean(recent_values)
    long_term_average = _mean(values)

    return (
        recent_average * FORECAST_RECENT_WEIGHT
        + long_term_average * FORECAST_LONG_TERM_WEIGHT
    )


def _trend(values):
    if not values:
        return "flat", None

    recent_values = values[-min(FORECAST_RECENT_DAYS, len(values)):]
    recent_average = _mean(recent_values)

    prior_end = len(values) - len(recent_values)
    prior_start = max(0, prior_end - FORECAST_RECENT_DAYS)
    prior_values = values[prior_start:prior_end]

    if not prior_values:
        return "flat", None

    prior_average = _mean(prior_values)

    if prior_average <= ZERO_MONEY:
        if recent_average > ZERO_MONEY:
            return "up", None
        return "flat", None

    change_percent = (
        ((recent_average - prior_average) / prior_average)
        * Decimal("100")
    ).quantize(Decimal("0.01"))

    if change_percent >= FORECAST_TREND_THRESHOLD_PERCENT:
        direction = "up"
    elif change_percent <= -FORECAST_TREND_THRESHOLD_PERCENT:
        direction = "down"
    else:
        direction = "flat"

    return direction, change_percent


def _variability_percent(values):
    if not values:
        return None

    average = _mean(values)
    if average <= ZERO_MONEY:
        return None

    variance = (
        sum(
            ((value - average) ** 2 for value in values),
            ZERO_MONEY,
        )
        / Decimal(len(values))
    )
    standard_deviation = variance.sqrt()

    return (
        (standard_deviation / average) * Decimal("100")
    ).quantize(Decimal("0.01"))


def _confidence_grade(
    *,
    history_days,
    transaction_count,
    active_selling_days,
):
    if (
        history_days >= 60
        and transaction_count >= 30
        and active_selling_days >= 15
    ):
        return "high"

    if (
        history_days >= 30
        and transaction_count >= 10
        and active_selling_days >= 5
    ):
        return "medium"

    return "low"


def _forecast_confidence_grade(*, data_grade, horizon_days):
    if horizon_days == ForecastRun.Horizon.NINETY_DAYS:
        return {
            "high": "medium",
            "medium": "low",
            "low": "low",
        }[data_grade]

    return data_grade


def _product_confidence_grade(
    *,
    business_grade,
    active_selling_days,
):
    if (
        business_grade == "high"
        and active_selling_days >= PRODUCT_HIGH_MIN_ACTIVE_DAYS
    ):
        return "high"

    if (
        business_grade in {"high", "medium"}
        and active_selling_days >= PRODUCT_MEDIUM_MIN_ACTIVE_DAYS
    ):
        return "medium"

    return "low"


def _decimal_string(value, pattern="0.01"):
    return str(Decimal(value).quantize(Decimal(pattern)))


def _history_window(*, business, now):
    current_timezone = timezone.get_current_timezone()
    local_now = timezone.localtime(now, current_timezone)
    history_end_date = local_now.date()
    history_end_at = timezone.make_aware(
        datetime.combine(history_end_date, time.min),
        current_timezone,
    )

    first_sale_at = (
        Sale.objects.filter(
            business=business,
            status__in=RECOGNIZED_SALE_STATUSES,
            completed_at__isnull=False,
            completed_at__lt=history_end_at,
        )
        .order_by("completed_at")
        .values_list("completed_at", flat=True)
        .first()
    )

    if first_sale_at is None:
        return {
            "history_start_date": None,
            "history_end_date": history_end_date,
            "history_start_at": history_end_at,
            "history_end_at": history_end_at,
            "history_days": 0,
        }

    first_sale_date = timezone.localtime(
        first_sale_at,
        current_timezone,
    ).date()
    maximum_start_date = history_end_date - timedelta(
        days=FORECAST_LOOKBACK_DAYS
    )
    history_start_date = max(
        first_sale_date,
        maximum_start_date,
    )
    history_start_at = timezone.make_aware(
        datetime.combine(history_start_date, time.min),
        current_timezone,
    )
    history_days = max(
        1,
        (history_end_date - history_start_date).days,
    )

    return {
        "history_start_date": history_start_date,
        "history_end_date": history_end_date,
        "history_start_at": history_start_at,
        "history_end_at": history_end_at,
        "history_days": history_days,
    }


def _completed_history_sales(*, business, history_window):
    if history_window["history_days"] <= 0:
        return []

    return list(
        Sale.objects.filter(
            business=business,
            status__in=RECOGNIZED_SALE_STATUSES,
            completed_at__gte=history_window["history_start_at"],
            completed_at__lt=history_window["history_end_at"],
        )
        .prefetch_related("items")
        .order_by("completed_at")
    )


def calculate_forecast(
    business,
    *,
    horizon_days,
    as_of=None,
):
    if horizon_days not in SUPPORTED_FORECAST_HORIZONS:
        raise ValueError(
            "horizon_days must be one of 7, 30, or 90."
        )

    now = as_of or timezone.now()
    if timezone.is_naive(now):
        now = timezone.make_aware(
            now,
            timezone.get_current_timezone(),
        )

    current_timezone = timezone.get_current_timezone()
    window = _history_window(
        business=business,
        now=now,
    )
    sales = _completed_history_sales(
        business=business,
        history_window=window,
    )

    products = list(
        Product.objects.filter(
            business=business,
            is_active=True,
        ).order_by("name")
    )
    product_by_id = {
        product.id: product
        for product in products
    }

    business_daily = defaultdict(
        lambda: {
            "quantity": ZERO_MONEY,
            "revenue": ZERO_MONEY,
            "gross_profit": ZERO_MONEY,
        }
    )
    product_daily = defaultdict(
        lambda: defaultdict(
            lambda: {
                "quantity": ZERO_MONEY,
                "revenue": ZERO_MONEY,
                "gross_profit": ZERO_MONEY,
            }
        )
    )

    active_selling_dates = set()

    for sale in sales:
        sale_date = timezone.localtime(
            sale.completed_at,
            current_timezone,
        ).date()
        active_selling_dates.add(sale_date)

        sale_cost = sum(
            (
                money(item.cost_price) * Decimal(item.quantity)
                for item in sale.items.all()
            ),
            ZERO_MONEY,
        )
        sale_quantity = sum(
            (
                Decimal(item.quantity)
                for item in sale.items.all()
            ),
            ZERO_MONEY,
        )
        sale_revenue = money(sale.total)
        sale_gross_profit = sale_revenue - sale_cost

        business_daily[sale_date]["quantity"] += sale_quantity
        business_daily[sale_date]["revenue"] += sale_revenue
        business_daily[sale_date]["gross_profit"] += (
            sale_gross_profit
        )

        for item, realized_revenue in _sale_item_realized_revenues(
            sale
        ):
            if item.product_id not in product_by_id:
                continue

            item_cost = (
                money(item.cost_price) * Decimal(item.quantity)
            )
            item_gross_profit = realized_revenue - item_cost
            stats = product_daily[item.product_id][sale_date]
            stats["quantity"] += Decimal(item.quantity)
            stats["revenue"] += realized_revenue
            stats["gross_profit"] += item_gross_profit

    history_dates = []
    if window["history_days"] > 0:
        history_dates = [
            window["history_start_date"] + timedelta(days=offset)
            for offset in range(window["history_days"])
        ]

    business_quantity_values = [
        business_daily[day]["quantity"]
        for day in history_dates
    ]
    business_revenue_values = [
        business_daily[day]["revenue"]
        for day in history_dates
    ]
    business_profit_values = [
        business_daily[day]["gross_profit"]
        for day in history_dates
    ]

    business_quantity_velocity = _weighted_velocity(
        business_quantity_values
    )
    business_revenue_velocity = _weighted_velocity(
        business_revenue_values
    )
    business_profit_velocity = _weighted_velocity(
        business_profit_values
    )
    revenue_direction, revenue_trend_percent = _trend(
        business_revenue_values
    )

    total_history_revenue = sum(
        business_revenue_values,
        ZERO_MONEY,
    )
    total_history_profit = sum(
        business_profit_values,
        ZERO_MONEY,
    )
    historical_margin_percent = (
        (
            total_history_profit
            / total_history_revenue
            * Decimal("100")
        ).quantize(Decimal("0.01"))
        if total_history_revenue > ZERO_MONEY
        else ZERO_MONEY
    )

    transaction_count = len(sales)
    active_selling_days = len(active_selling_dates)
    data_grade = _confidence_grade(
        history_days=window["history_days"],
        transaction_count=transaction_count,
        active_selling_days=active_selling_days,
    )
    business_grade = _forecast_confidence_grade(
        data_grade=data_grade,
        horizon_days=horizon_days,
    )
    variability_percent = _variability_percent(
        business_revenue_values
    )

    variability_text = (
        f" Daily revenue variability was "
        f"{variability_percent}%."
        if variability_percent is not None
        else ""
    )
    confidence_reason = (
        f"{business_grade.capitalize()} forecast confidence for a "
        f"{horizon_days}-day horizon - underlying data confidence is "
        f"{data_grade}. Based on {transaction_count} recognized "
        f"sale(s) across {active_selling_days} active selling day(s) "
        f"within {window['history_days']} completed day(s) of usable "
        f"history.{variability_text}"
    )

    product_forecasts = []

    for product in products:
        daily_stats = product_daily[product.id]
        quantity_values = [
            daily_stats[day]["quantity"]
            for day in history_dates
        ]
        revenue_values = [
            daily_stats[day]["revenue"]
            for day in history_dates
        ]
        profit_values = [
            daily_stats[day]["gross_profit"]
            for day in history_dates
        ]

        quantity_velocity = _weighted_velocity(quantity_values)
        revenue_velocity = _weighted_velocity(revenue_values)
        profit_velocity = _weighted_velocity(profit_values)
        demand_direction, demand_trend_percent = _trend(
            quantity_values
        )

        expected_quantity = (
            quantity_velocity * Decimal(horizon_days)
        ).quantize(Decimal("0.01"))
        expected_revenue = money(
            revenue_velocity * Decimal(horizon_days)
        )
        expected_gross_profit = money(
            profit_velocity * Decimal(horizon_days)
        )

        total_product_revenue = sum(
            revenue_values,
            ZERO_MONEY,
        )
        total_product_profit = sum(
            profit_values,
            ZERO_MONEY,
        )
        product_margin_percent = (
            (
                total_product_profit
                / total_product_revenue
                * Decimal("100")
            ).quantize(Decimal("0.01"))
            if total_product_revenue > ZERO_MONEY
            else ZERO_MONEY
        )

        product_active_days = sum(
            1
            for value in quantity_values
            if value > ZERO_MONEY
        )
        product_grade = _product_confidence_grade(
            business_grade=business_grade,
            active_selling_days=product_active_days,
        )

        available_stock = max(
            0,
            product.stock - product.reserved_stock,
        )
        days_remaining = None
        projected_stock_out_date = None
        stock_out_within_horizon = False

        if quantity_velocity > ZERO_MONEY:
            days_remaining_decimal = (
                Decimal(available_stock) / quantity_velocity
            )
            days_remaining = days_remaining_decimal.quantize(
                Decimal("0.1")
            )
            stock_out_after_days = int(
                days_remaining_decimal.to_integral_value(
                    rounding=ROUND_CEILING
                )
            )
            projected_stock_out_date = (
                window["history_end_date"]
                + timedelta(days=stock_out_after_days)
            )
            stock_out_within_horizon = (
                days_remaining_decimal
                <= Decimal(horizon_days)
            )

        product_forecasts.append(
            {
                "product_id": str(product.id),
                "name": product.name,
                "sku": product.sku,
                "category": product.category or "Uncategorized",
                "available_stock": available_stock,
                "daily_demand": _decimal_string(
                    quantity_velocity
                ),
                "expected_quantity": _decimal_string(
                    expected_quantity
                ),
                "expected_revenue": _decimal_string(
                    expected_revenue
                ),
                "expected_gross_profit": _decimal_string(
                    expected_gross_profit
                ),
                "historical_margin_percent": _decimal_string(
                    product_margin_percent
                ),
                "demand_direction": demand_direction,
                "demand_trend_percent": (
                    _decimal_string(demand_trend_percent)
                    if demand_trend_percent is not None
                    else None
                ),
                "active_selling_days": product_active_days,
                "confidence_grade": product_grade,
                "days_of_stock_remaining": (
                    _decimal_string(days_remaining, "0.1")
                    if days_remaining is not None
                    else None
                ),
                "projected_stock_out_date": (
                    projected_stock_out_date.isoformat()
                    if projected_stock_out_date is not None
                    else None
                ),
                "stock_out_within_horizon": (
                    stock_out_within_horizon
                ),
            }
        )

    product_forecasts.sort(
        key=lambda item: (
            item["stock_out_within_horizon"],
            Decimal(item["expected_revenue"]),
        ),
        reverse=True,
    )

    category_totals = defaultdict(
        lambda: {
            "product_count": 0,
            "expected_quantity": ZERO_MONEY,
            "expected_revenue": ZERO_MONEY,
            "expected_gross_profit": ZERO_MONEY,
            "stock_out_risk_count": 0,
        }
    )

    for product_forecast in product_forecasts:
        category = product_forecast["category"]
        totals = category_totals[category]
        totals["product_count"] += 1
        totals["expected_quantity"] += Decimal(
            product_forecast["expected_quantity"]
        )
        totals["expected_revenue"] += Decimal(
            product_forecast["expected_revenue"]
        )
        totals["expected_gross_profit"] += Decimal(
            product_forecast["expected_gross_profit"]
        )
        if product_forecast["stock_out_within_horizon"]:
            totals["stock_out_risk_count"] += 1

    category_forecasts = [
        {
            "category": category,
            "product_count": totals["product_count"],
            "expected_quantity": _decimal_string(
                totals["expected_quantity"]
            ),
            "expected_revenue": _decimal_string(
                totals["expected_revenue"]
            ),
            "expected_gross_profit": _decimal_string(
                totals["expected_gross_profit"]
            ),
            "stock_out_risk_count": (
                totals["stock_out_risk_count"]
            ),
        }
        for category, totals in category_totals.items()
    ]
    category_forecasts.sort(
        key=lambda item: Decimal(item["expected_revenue"]),
        reverse=True,
    )

    stock_out_risk_count = sum(
        1
        for product_forecast in product_forecasts
        if product_forecast["stock_out_within_horizon"]
    )

    results = {
        "business": {
            "expected_quantity": _decimal_string(
                business_quantity_velocity * Decimal(horizon_days)
            ),
            "expected_revenue": _decimal_string(
                money(
                    business_revenue_velocity
                    * Decimal(horizon_days)
                )
            ),
            "expected_gross_profit": _decimal_string(
                money(
                    business_profit_velocity
                    * Decimal(horizon_days)
                )
            ),
            "historical_margin_percent": _decimal_string(
                historical_margin_percent
            ),
            "daily_unit_velocity": _decimal_string(
                business_quantity_velocity
            ),
            "daily_revenue_velocity": _decimal_string(
                business_revenue_velocity
            ),
            "revenue_direction": revenue_direction,
            "revenue_trend_percent": (
                _decimal_string(revenue_trend_percent)
                if revenue_trend_percent is not None
                else None
            ),
            "stock_out_risk_count": stock_out_risk_count,
        },
        "products": product_forecasts,
        "categories": category_forecasts,
    }

    confidence = {
        "grade": business_grade,
        "data_grade": data_grade,
        "history_days": window["history_days"],
        "transaction_count": transaction_count,
        "active_selling_days": active_selling_days,
        "daily_revenue_variability_percent": (
            _decimal_string(variability_percent)
            if variability_percent is not None
            else None
        ),
        "reason": confidence_reason,
    }

    parameters = {
        "lookback_days": FORECAST_LOOKBACK_DAYS,
        "recent_window_days": FORECAST_RECENT_DAYS,
        "recent_weight": _decimal_string(
            FORECAST_RECENT_WEIGHT
        ),
        "long_term_weight": _decimal_string(
            FORECAST_LONG_TERM_WEIGHT
        ),
        "trend_threshold_percent": _decimal_string(
            FORECAST_TREND_THRESHOLD_PERCENT
        ),
        "seasonality_status": "not_applied_v1",
        "recognized_sale_statuses": list(
            RECOGNIZED_SALE_STATUSES
        ),
        "current_stock_basis": "max(0, stock - reserved_stock)",
        "completed_days_only": True,
        "product_medium_min_active_days": (
            PRODUCT_MEDIUM_MIN_ACTIVE_DAYS
        ),
        "product_high_min_active_days": (
            PRODUCT_HIGH_MIN_ACTIVE_DAYS
        ),
        "horizon_confidence_policy": (
            "90_day_downgrades_one_level"
        ),
    }

    history_end_for_record = (
        window["history_end_date"] - timedelta(days=1)
        if window["history_days"] > 0
        else None
    )

    return {
        "horizon_days": horizon_days,
        "history_start": window["history_start_date"],
        "history_end": history_end_for_record,
        "parameters": parameters,
        "results": results,
        "confidence": confidence,
    }


def generate_and_store_forecast(
    business,
    *,
    horizon_days,
    as_of=None,
):
    forecast = calculate_forecast(
        business,
        horizon_days=horizon_days,
        as_of=as_of,
    )

    return ForecastRun.objects.create(
        business=business,
        horizon_days=horizon_days,
        status=ForecastRun.Status.COMPLETED,
        algorithm="weighted_daily_velocity",
        algorithm_version="1.0",
        history_start=forecast["history_start"],
        history_end=forecast["history_end"],
        parameters=forecast["parameters"],
        results=forecast["results"],
        confidence=forecast["confidence"],
    )
