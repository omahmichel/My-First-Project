from collections import defaultdict
from datetime import timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP

from inventory.models import Product, StockMovement
from inventory.restock_models import RestockPurchase
from django.db.models import Max
from sales.models import Sale, SaleItem
from sales.services import debt_snapshot

from django.utils import timezone


ZERO_MONEY = Decimal("0.00")

RECOGNIZED_SALE_STATUSES = (
    Sale.Status.COMPLETED,
    Sale.Status.PARTIALLY_PAID,
)


SLOW_MOVING_DAYS = 30
DEAD_STOCK_DAYS = 60
STOCK_OUT_RISK_DAYS = 14
CONFIDENCE_LOOKBACK_DAYS = 60
OVERSTOCK_COVER_DAYS = 60
ANOMALY_BASELINE_OCCURRENCES = 4
ANOMALY_CHANGE_THRESHOLD_PERCENT = Decimal("75.00")
ANOMALY_MIN_ACTIVE_BASELINES = 2


def get_recognized_sales(business):
    """Return sales that represent completed business activity."""
    return (
        Sale.objects.filter(
            business=business,
            status__in=RECOGNIZED_SALE_STATUSES,
        )
        .prefetch_related("items")
        .order_by("-completed_at", "-created_at")
    )


def money(value):
    """Normalize nullable monetary values to Decimal."""
    return value if value is not None else ZERO_MONEY



def _summarize_sales_collection(sales):
    'Summarize one verified collection of recognized sales.'
    revenue = sum(
        (money(sale.total) for sale in sales),
        ZERO_MONEY,
    )
    historical_cost = sum(
        (
            money(item.cost_price) * item.quantity
            for sale in sales
            for item in sale.items.all()
        ),
        ZERO_MONEY,
    )
    units_sold = sum(
        item.quantity
        for sale in sales
        for item in sale.items.all()
    )

    gross_profit = revenue - historical_cost
    profit_margin = (
        (gross_profit / revenue) * Decimal("100")
        if revenue > ZERO_MONEY
        else ZERO_MONEY
    ).quantize(Decimal("0.01"))

    return {
        "sale_count": len(sales),
        "units_sold": units_sold,
        "revenue": revenue,
        "historical_cost": historical_cost,
        "gross_profit": gross_profit,
        "profit_margin": profit_margin,
    }


def calculate_sales_summary(business):
    'Calculate authoritative performance from recognized sales.'
    return _summarize_sales_collection(
        list(get_recognized_sales(business))
    )

def calculate_inventory_summary(business):
    """Calculate current inventory exposure and stock risk."""
    products = list(
        Product.objects.filter(
            business=business,
            is_active=True,
        )
    )

    total_stock_units = sum(product.stock for product in products)
    reserved_stock_units = sum(
        product.reserved_stock for product in products
    )
    available_stock_units = sum(
        max(0, product.stock - product.reserved_stock)
        for product in products
    )

    inventory_cost_value = sum(
        (product.cost_price * product.stock for product in products),
        ZERO_MONEY,
    )
    available_inventory_cost_value = sum(
        (
            product.cost_price
            * max(0, product.stock - product.reserved_stock)
            for product in products
        ),
        ZERO_MONEY,
    )
    potential_retail_value = sum(
        (product.selling_price * product.stock for product in products),
        ZERO_MONEY,
    )

    low_stock_products = [
        product
        for product in products
        if max(0, product.stock - product.reserved_stock)
        <= product.low_stock_level
    ]

    return {
        "active_product_count": len(products),
        "total_stock_units": total_stock_units,
        "reserved_stock_units": reserved_stock_units,
        "available_stock_units": available_stock_units,
        "inventory_cost_value": inventory_cost_value,
        "available_inventory_cost_value": available_inventory_cost_value,
        "potential_retail_value": potential_retail_value,
        "low_stock_count": len(low_stock_products),
    }



def calculate_debt_summary(business):
    """Calculate current customer receivables and supplier payables."""
    debt_sales = list(
        Sale.objects.filter(
            business=business,
            customer__isnull=False,
            outstanding_balance__gt=ZERO_MONEY,
            status__in=RECOGNIZED_SALE_STATUSES,
        ).select_related("customer")
    )
    restock_purchases = list(
        RestockPurchase.objects.filter(business=business)
    )

    customer_debt = ZERO_MONEY
    customer_ids_with_debt = set()

    for sale in debt_sales:
        snapshot = debt_snapshot(sale=sale)
        total_debt_payable = money(snapshot["total_debt_payable"])

        if total_debt_payable > ZERO_MONEY:
            customer_debt += total_debt_payable
            customer_ids_with_debt.add(sale.customer_id)

    supplier_debt = sum(
        (
            max(
                ZERO_MONEY,
                money(purchase.total_amount) - money(purchase.amount_paid),
            )
            for purchase in restock_purchases
        ),
        ZERO_MONEY,
    )
    supplier_purchases_with_balance = sum(
        1
        for purchase in restock_purchases
        if (
            money(purchase.total_amount) - money(purchase.amount_paid)
            > ZERO_MONEY
        )
    )

    return {
        "customer_debt": customer_debt,
        "supplier_debt": supplier_debt,
        "customers_with_debt": len(customer_ids_with_debt),
        "supplier_purchases_with_balance": (
            supplier_purchases_with_balance
        ),
    }

def _recognized_sales_between(*, business, start, end):
    """Return recognized sales completed inside one half-open time window."""
    return list(
        Sale.objects.filter(
            business=business,
            status__in=RECOGNIZED_SALE_STATUSES,
            completed_at__gte=start,
            completed_at__lt=end,
        )
        .prefetch_related("items")
        .order_by("-completed_at")
    )


def _sales_revenue(sales):
    return sum(
        (money(sale.total) for sale in sales),
        ZERO_MONEY,
    )


def _percentage_change(*, current, previous):
    if previous <= ZERO_MONEY:
        return None

    return (
        ((current - previous) / previous) * Decimal("100")
    ).quantize(Decimal("0.01"))


def _movement_direction(change):
    if change > ZERO_MONEY:
        return "up"
    if change < ZERO_MONEY:
        return "down"
    return "flat"


def _sales_inside_window(sales, *, start, end):
    return [
        sale
        for sale in sales
        if (
            sale.completed_at is not None
            and start <= sale.completed_at < end
        )
    ]


def _build_period_performance(
    *,
    sales,
    current_start,
    current_end,
    previous_start,
    previous_end,
):
    current = _summarize_sales_collection(
        _sales_inside_window(
            sales,
            start=current_start,
            end=current_end,
        )
    )
    previous = _summarize_sales_collection(
        _sales_inside_window(
            sales,
            start=previous_start,
            end=previous_end,
        )
    )

    revenue_change = current["revenue"] - previous["revenue"]
    gross_profit_change = (
        current["gross_profit"] - previous["gross_profit"]
    )

    return {
        **current,
        "period_start": current_start,
        "period_end": current_end,
        "previous_period_start": previous_start,
        "previous_period_end": previous_end,
        "previous_sale_count": previous["sale_count"],
        "previous_units_sold": previous["units_sold"],
        "previous_revenue": previous["revenue"],
        "previous_gross_profit": previous["gross_profit"],
        "revenue_change": revenue_change,
        "revenue_change_percentage": _percentage_change(
            current=current["revenue"],
            previous=previous["revenue"],
        ),
        "revenue_direction": _movement_direction(revenue_change),
        "gross_profit_change": gross_profit_change,
        "gross_profit_change_percentage": _percentage_change(
            current=current["gross_profit"],
            previous=previous["gross_profit"],
        ),
        "gross_profit_direction": _movement_direction(
            gross_profit_change
        ),
    }


def calculate_period_performance(business, *, as_of=None):
    'Calculate today, rolling 7-day and rolling 30-day performance.'
    now = as_of or timezone.now()

    if timezone.is_naive(now):
        now = timezone.make_aware(
            now,
            timezone.get_current_timezone(),
        )

    local_now = timezone.localtime(
        now,
        timezone.get_current_timezone(),
    )
    today_start = local_now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    previous_today_start = today_start - timedelta(days=1)
    previous_today_end = now - timedelta(days=1)

    last_7_start = now - timedelta(days=7)
    previous_7_start = now - timedelta(days=14)

    last_30_start = now - timedelta(days=30)
    previous_30_start = now - timedelta(days=60)

    sales = _recognized_sales_between(
        business=business,
        start=previous_30_start,
        end=now,
    )

    return {
        "today": _build_period_performance(
            sales=sales,
            current_start=today_start,
            current_end=now,
            previous_start=previous_today_start,
            previous_end=previous_today_end,
        ),
        "last_7_days": _build_period_performance(
            sales=sales,
            current_start=last_7_start,
            current_end=now,
            previous_start=previous_7_start,
            previous_end=last_7_start,
        ),
        "last_30_days": _build_period_performance(
            sales=sales,
            current_start=last_30_start,
            current_end=now,
            previous_start=previous_30_start,
            previous_end=last_30_start,
        ),
    }


def calculate_sales_trend(business, *, days=30, as_of=None):
    """Compare recognized revenue for the current and previous period."""
    now = as_of or timezone.now()
    current_start = now - timedelta(days=days)
    previous_start = current_start - timedelta(days=days)

    current_sales = _recognized_sales_between(
        business=business,
        start=current_start,
        end=now,
    )
    previous_sales = _recognized_sales_between(
        business=business,
        start=previous_start,
        end=current_start,
    )

    current_revenue = _sales_revenue(current_sales)
    previous_revenue = _sales_revenue(previous_sales)
    absolute_change = current_revenue - previous_revenue

    if previous_revenue > ZERO_MONEY:
        percentage_change = (
            (absolute_change / previous_revenue) * Decimal("100")
        ).quantize(Decimal("0.01"))
    else:
        percentage_change = None

    if absolute_change > ZERO_MONEY:
        direction = "up"
    elif absolute_change < ZERO_MONEY:
        direction = "down"
    else:
        direction = "flat"

    return {
        "period_days": days,
        "current_revenue": current_revenue,
        "previous_revenue": previous_revenue,
        "absolute_change": absolute_change,
        "percentage_change": percentage_change,
        "direction": direction,
        "current_sale_count": len(current_sales),
        "previous_sale_count": len(previous_sales),
        "period_start": current_start,
        "period_end": now,
    }


def calculate_product_performance(business, *, as_of=None):
    """Calculate explainable product movement and stock-risk signals."""
    now = as_of or timezone.now()
    recent_start = now - timedelta(days=SLOW_MOVING_DAYS)
    dead_start = now - timedelta(days=DEAD_STOCK_DAYS)

    products = list(
        Product.objects.filter(
            business=business,
            is_active=True,
        ).order_by("name")
    )

    recent_sales = _recognized_sales_between(
        business=business,
        start=dead_start,
        end=now,
    )

    last_sale_by_product = {
        row["product_id"]: row["last_sale_at"]
        for row in (
            SaleItem.objects.filter(
                sale__business=business,
                sale__status__in=RECOGNIZED_SALE_STATUSES,
                sale__completed_at__isnull=False,
            )
            .values("product_id")
            .annotate(last_sale_at=Max("sale__completed_at"))
        )
    }

    stats = defaultdict(
        lambda: {
            "quantity_30d": 0,
            "quantity_60d": 0,
        }
    )

    for sale in recent_sales:
        sale_at = sale.completed_at or sale.created_at

        for item in sale.items.all():
            product_stats = stats[item.product_id]
            product_stats["quantity_60d"] += item.quantity

            if sale_at >= recent_start:
                product_stats["quantity_30d"] += item.quantity

    top_products = []
    slow_moving = []
    dead_stock = []
    stock_out_risks = []

    for product in products:
        product_stats = stats[product.id]
        available_stock = max(
            0,
            product.stock - product.reserved_stock,
        )
        product_age_days = max(
            0,
            (now.date() - product.created_at.date()).days,
        )
        last_sale_at = last_sale_by_product.get(product.id)

        days_since_last_sale = (
            max(0, (now.date() - last_sale_at.date()).days)
            if last_sale_at
            else product_age_days
        )

        if product_stats["quantity_30d"] > 0:
            top_products.append(
                {
                    "product_id": product.id,
                    "name": product.name,
                    "sku": product.sku,
                    "quantity_sold": product_stats["quantity_30d"],
                    "last_sale_at": last_sale_at,
                }
            )

        is_dead = (
            available_stock > 0
            and product_age_days >= DEAD_STOCK_DAYS
            and product_stats["quantity_60d"] == 0
        )

        is_slow = (
            available_stock > 0
            and not is_dead
            and product_age_days >= SLOW_MOVING_DAYS
            and product_stats["quantity_30d"] == 0
        )

        candidate = {
            "product_id": product.id,
            "name": product.name,
            "sku": product.sku,
            "available_stock": available_stock,
            "inventory_cost_value": (
                money(product.cost_price) * available_stock
            ),
            "days_since_last_sale": days_since_last_sale,
            "last_sale_at": last_sale_at,
        }

        if is_dead:
            dead_stock.append(candidate)
        elif is_slow:
            slow_moving.append(candidate)

        average_daily_demand = (
            Decimal(product_stats["quantity_30d"])
            / Decimal(SLOW_MOVING_DAYS)
        )

        if average_daily_demand > 0:
            days_remaining = (
                Decimal(available_stock) / average_daily_demand
            ).quantize(Decimal("0.1"))

            if (
                available_stock == 0
                or days_remaining <= Decimal(str(STOCK_OUT_RISK_DAYS))
            ):
                stock_out_risks.append(
                    {
                        "product_id": product.id,
                        "name": product.name,
                        "sku": product.sku,
                        "available_stock": available_stock,
                        "average_daily_demand": (
                            average_daily_demand.quantize(
                                Decimal("0.01")
                            )
                        ),
                        "estimated_days_remaining": days_remaining,
                    }
                )

    top_products.sort(
        key=lambda item: item["quantity_sold"],
        reverse=True,
    )
    slow_moving.sort(
        key=lambda item: item["inventory_cost_value"],
        reverse=True,
    )
    dead_stock.sort(
        key=lambda item: item["inventory_cost_value"],
        reverse=True,
    )
    stock_out_risks.sort(
        key=lambda item: item["estimated_days_remaining"]
    )

    return {
        "top_products": top_products[:5],
        "slow_moving_products": slow_moving[:10],
        "dead_stock_candidates": dead_stock[:10],
        "stock_out_risks": stock_out_risks[:10],
        "rules": {
            "slow_moving_days": SLOW_MOVING_DAYS,
            "dead_stock_days": DEAD_STOCK_DAYS,
            "stock_out_risk_days": STOCK_OUT_RISK_DAYS,
        },
    }


def _sale_item_realized_revenues(sale):
    'Allocate sale-level discount proportionally across sale items.'
    items = list(sale.items.all())

    if not items:
        return []

    subtotal = money(sale.subtotal)
    total = money(sale.total)
    discount = money(sale.discount)

    if discount <= ZERO_MONEY or subtotal <= ZERO_MONEY:
        return [
            (item, money(item.line_total))
            for item in items
        ]

    # Smaller lines are rounded first; the largest line receives the
    # final cent reconciliation so allocated revenue equals Sale.total.
    ordered_items = sorted(
        items,
        key=lambda item: (
            money(item.line_total),
            str(item.pk),
        ),
    )

    allocations = []
    allocated_revenue = ZERO_MONEY

    for item in ordered_items[:-1]:
        realized_revenue = (
            (money(item.line_total) * total) / subtotal
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
        allocations.append((item, realized_revenue))
        allocated_revenue += realized_revenue

    last_item = ordered_items[-1]
    allocations.append(
        (
            last_item,
            total - allocated_revenue,
        )
    )

    return allocations


def _aggregate_product_profitability(sales):
    'Aggregate realized revenue and historical cost by product.'
    products = {}

    for sale in sales:
        for item, realized_revenue in _sale_item_realized_revenues(sale):
            product_key = (
                item.product_id,
                item.sku,
                item.product_name,
            )
            entry = products.setdefault(
                product_key,
                {
                    "product_id": item.product_id,
                    "name": item.product_name,
                    "sku": item.sku,
                    "quantity_sold": 0,
                    "realized_revenue": ZERO_MONEY,
                    "historical_cost": ZERO_MONEY,
                },
            )

            entry["quantity_sold"] += item.quantity
            entry["realized_revenue"] += realized_revenue
            entry["historical_cost"] += (
                money(item.cost_price) * item.quantity
            )

    for entry in products.values():
        gross_profit = (
            entry["realized_revenue"] - entry["historical_cost"]
        )
        profit_margin = (
            (
                gross_profit
                / entry["realized_revenue"]
                * Decimal("100")
            )
            if entry["realized_revenue"] > ZERO_MONEY
            else ZERO_MONEY
        ).quantize(Decimal("0.01"))

        entry["gross_profit"] = gross_profit
        entry["profit_margin"] = profit_margin

    return products


def calculate_product_profitability(
    business,
    *,
    days=30,
    as_of=None,
):
    'Rank product profitability using discount-adjusted realized revenue.'
    now = as_of or timezone.now()
    current_start = now - timedelta(days=days)
    previous_start = current_start - timedelta(days=days)

    current_sales = _recognized_sales_between(
        business=business,
        start=current_start,
        end=now,
    )
    previous_sales = _recognized_sales_between(
        business=business,
        start=previous_start,
        end=current_start,
    )

    current = _aggregate_product_profitability(current_sales)
    previous = _aggregate_product_profitability(previous_sales)

    results = []

    for product_key, entry in current.items():
        previous_entry = previous.get(product_key)
        previous_profit_margin = (
            previous_entry["profit_margin"]
            if previous_entry is not None
            else None
        )
        margin_change_points = (
            (
                entry["profit_margin"]
                - previous_profit_margin
            ).quantize(Decimal("0.01"))
            if previous_profit_margin is not None
            else None
        )

        results.append(
            {
                **entry,
                "previous_realized_revenue": (
                    previous_entry["realized_revenue"]
                    if previous_entry is not None
                    else ZERO_MONEY
                ),
                "previous_gross_profit": (
                    previous_entry["gross_profit"]
                    if previous_entry is not None
                    else ZERO_MONEY
                ),
                "previous_profit_margin": previous_profit_margin,
                "margin_change_points": margin_change_points,
            }
        )

    best = sorted(
        results,
        key=lambda item: (
            item["gross_profit"],
            item["realized_revenue"],
            item["name"],
        ),
        reverse=True,
    )
    worst = sorted(
        results,
        key=lambda item: (
            item["gross_profit"],
            item["realized_revenue"],
            item["name"],
        ),
    )
    margin_deterioration = sorted(
        (
            item
            for item in results
            if (
                item["margin_change_points"] is not None
                and item["margin_change_points"] < ZERO_MONEY
            )
        ),
        key=lambda item: item["margin_change_points"],
    )

    return {
        "period_days": days,
        "comparison_period_days": days,
        "discount_allocation_method": (
            "proportional_by_line_subtotal"
        ),
        "discount_rounding_method": (
            "cent_reconciliation_to_largest_line"
        ),
        "best_performing_products": best[:5],
        "worst_performing_products": worst[:5],
        "margin_deterioration": margin_deterioration[:10],
    }


def calculate_inventory_overstock(business, *, as_of=None):
    now = as_of or timezone.now()
    demand_start = now - timedelta(days=SLOW_MOVING_DAYS)

    products = list(
        Product.objects.filter(
            business=business,
            is_active=True,
        ).order_by("name")
    )
    recent_sales = _recognized_sales_between(
        business=business,
        start=demand_start,
        end=now,
    )

    quantity_sold = defaultdict(int)
    for sale in recent_sales:
        for item in sale.items.all():
            quantity_sold[item.product_id] += item.quantity

    last_stock_in_by_product = {
        row["product_id"]: row["last_stock_in_at"]
        for row in (
            StockMovement.objects.filter(
                business=business,
                movement_type=StockMovement.MovementType.STOCK_IN,
            )
            .values("product_id")
            .annotate(last_stock_in_at=Max("created_at"))
        )
    }

    candidates = []
    total_excess_units = 0
    total_excess_cost_value = ZERO_MONEY

    for product in products:
        sold_30d = quantity_sold[product.id]

        # No-demand stock is already covered by slow/dead-stock signals.
        if sold_30d <= 0:
            continue

        available_stock = max(
            0,
            product.stock - product.reserved_stock,
        )
        average_daily_demand = (
            Decimal(sold_30d) / Decimal(SLOW_MOVING_DAYS)
        )

        target_stock_units = int(
            (
                average_daily_demand
                * Decimal(OVERSTOCK_COVER_DAYS)
            ).to_integral_value(rounding=ROUND_CEILING)
        )

        excess_units = max(
            0,
            available_stock - target_stock_units,
        )
        if excess_units <= 0:
            continue

        estimated_days_of_cover = (
            Decimal(available_stock) / average_daily_demand
        ).quantize(Decimal("0.1"))
        excess_cost_value = (
            money(product.cost_price) * excess_units
        )

        candidates.append(
            {
                "product_id": product.id,
                "name": product.name,
                "sku": product.sku,
                "available_stock": available_stock,
                "quantity_sold_30d": sold_30d,
                "average_daily_demand": (
                    average_daily_demand.quantize(
                        Decimal("0.01")
                    )
                ),
                "estimated_days_of_cover": estimated_days_of_cover,
                "target_stock_units": target_stock_units,
                "excess_units": excess_units,
                "current_cost_price": money(product.cost_price),
                "excess_cost_value": excess_cost_value,
                "last_stock_in_at": last_stock_in_by_product.get(
                    product.id
                ),
            }
        )

        total_excess_units += excess_units
        total_excess_cost_value += excess_cost_value

    candidates.sort(
        key=lambda item: (
            item["excess_cost_value"],
            item["excess_units"],
            item["name"],
        ),
        reverse=True,
    )

    return {
        "demand_lookback_days": SLOW_MOVING_DAYS,
        "overstock_cover_days": OVERSTOCK_COVER_DAYS,
        "candidate_count": len(candidates),
        "total_excess_units": total_excess_units,
        "total_excess_cost_value": total_excess_cost_value,
        "candidates": candidates[:10],
        "method": "recent_demand_days_of_cover",
    }


def calculate_data_confidence(business, *, as_of=None):
    """Grade overview confidence from verified transaction history depth."""
    now = as_of or timezone.now()
    history_start = now - timedelta(days=CONFIDENCE_LOOKBACK_DAYS)

    sales = list(
        Sale.objects.filter(
            business=business,
            status__in=RECOGNIZED_SALE_STATUSES,
            completed_at__gte=history_start,
            completed_at__lt=now,
        ).only("id", "completed_at")
    )

    active_selling_days = len(
        {
            sale.completed_at.date()
            for sale in sales
            if sale.completed_at is not None
        }
    )

    first_sale = (
        Sale.objects.filter(
            business=business,
            status__in=RECOGNIZED_SALE_STATUSES,
            completed_at__isnull=False,
        )
        .order_by("completed_at")
        .values_list("completed_at", flat=True)
        .first()
    )

    history_days = (
        max(0, (now.date() - first_sale.date()).days)
        if first_sale
        else 0
    )
    transaction_count = len(sales)

    if (
        history_days >= 60
        and transaction_count >= 30
        and active_selling_days >= 15
    ):
        grade = "high"
    elif (
        history_days >= 30
        and transaction_count >= 10
        and active_selling_days >= 5
    ):
        grade = "medium"
    else:
        grade = "low"

    return {
        "grade": grade,
        "history_days": history_days,
        "transaction_count_60d": transaction_count,
        "active_selling_days_60d": active_selling_days,
        "lookback_days": CONFIDENCE_LOOKBACK_DAYS,
    }


def calculate_sales_anomaly(
    business,
    *,
    confidence,
    as_of=None,
):
    """Evaluate the latest completed day against prior same-weekday history."""
    now = as_of or timezone.now()

    if timezone.is_naive(now):
        now = timezone.make_aware(
            now,
            timezone.get_current_timezone(),
        )

    local_now = timezone.localtime(
        now,
        timezone.get_current_timezone(),
    )
    latest_complete_day_end = local_now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    evaluated_start = latest_complete_day_end - timedelta(days=1)
    evaluated_date = evaluated_start.date()

    result = {
        "eligible": False,
        "status": "insufficient_history",
        "confidence_grade": confidence["grade"],
        "evaluated_date": evaluated_date,
        "current_revenue": ZERO_MONEY,
        "baseline_weekday": evaluated_start.strftime("%A"),
        "baseline_sample_count": 0,
        "baseline_average_revenue": ZERO_MONEY,
        "percentage_change": None,
        "direction": "flat",
        "threshold_percent": ANOMALY_CHANGE_THRESHOLD_PERCENT,
        "signal_type": None,
        "severity": None,
        "baseline_samples": [],
    }

    if confidence["grade"] == "low":
        return result

    baseline_dates = [
        evaluated_date - timedelta(days=7 * occurrence)
        for occurrence in range(1, ANOMALY_BASELINE_OCCURRENCES + 1)
    ]
    history_start = evaluated_start - timedelta(
        days=7 * ANOMALY_BASELINE_OCCURRENCES
    )

    sales = _recognized_sales_between(
        business=business,
        start=history_start,
        end=latest_complete_day_end,
    )

    revenue_by_date = defaultdict(lambda: ZERO_MONEY)
    for sale in sales:
        sale_date = timezone.localtime(
            sale.completed_at,
            timezone.get_current_timezone(),
        ).date()
        revenue_by_date[sale_date] += money(sale.total)

    current_revenue = revenue_by_date[evaluated_date]
    baseline_samples = [
        {
            "date": baseline_date,
            "revenue": revenue_by_date[baseline_date],
        }
        for baseline_date in baseline_dates
    ]
    active_baselines = [
        sample
        for sample in baseline_samples
        if sample["revenue"] > ZERO_MONEY
    ]

    result["current_revenue"] = current_revenue
    result["baseline_sample_count"] = len(active_baselines)
    result["baseline_samples"] = baseline_samples

    if len(active_baselines) < ANOMALY_MIN_ACTIVE_BASELINES:
        result["status"] = "insufficient_baseline"
        return result

    baseline_average = (
        sum(
            (sample["revenue"] for sample in active_baselines),
            ZERO_MONEY,
        )
        / Decimal(len(active_baselines))
    ).quantize(Decimal("0.01"))

    percentage_change = (
        ((current_revenue - baseline_average) / baseline_average)
        * Decimal("100")
    ).quantize(Decimal("0.01"))

    direction = _movement_direction(
        current_revenue - baseline_average
    )

    result.update(
        {
            "eligible": True,
            "status": "normal",
            "baseline_average_revenue": baseline_average,
            "percentage_change": percentage_change,
            "direction": direction,
        }
    )

    if abs(percentage_change) < ANOMALY_CHANGE_THRESHOLD_PERCENT:
        return result

    result.update(
        {
            "status": "anomaly",
            "signal_type": (
                "revenue_spike"
                if percentage_change > ZERO_MONEY
                else "revenue_drop"
            ),
            "severity": (
                "high"
                if (
                    percentage_change >= Decimal("150.00")
                    or percentage_change <= Decimal("-90.00")
                )
                else "attention"
            ),
        }
    )
    return result


def calculate_business_health(
    *,
    sales_trend,
    inventory,
    debts,
    product_performance,
):
    """Summarize verified attention signals without hiding the evidence."""
    reasons = []

    stock_out_count = len(product_performance["stock_out_risks"])
    if stock_out_count:
        reasons.append(
            f"{stock_out_count} product(s) may run out within "
            f"{STOCK_OUT_RISK_DAYS} days."
        )

    if inventory["low_stock_count"]:
        reasons.append(
            f'{inventory["low_stock_count"]} active product(s) are at '
            "or below their low-stock level."
        )

    if sales_trend["direction"] == "down":
        reasons.append(
            "Recognized revenue is down versus the previous "
            f'{sales_trend["period_days"]}-day period.'
        )

    if debts["customer_debt"] > ZERO_MONEY:
        reasons.append("The business has outstanding customer debt.")

    if debts["supplier_debt"] > ZERO_MONEY:
        reasons.append("The business has outstanding supplier debt.")

    if stock_out_count:
        status = "attention"
    elif reasons:
        status = "watch"
    else:
        status = "stable"

    return {
        "status": status,
        "attention_count": len(reasons),
        "reasons": reasons,
    }


def calculate_business_overview(business, *, as_of=None):
    """Compose the first verified StockFlow Intelligence overview."""
    now = as_of or timezone.now()

    sales = calculate_sales_summary(business)
    period_performance = calculate_period_performance(
        business,
        as_of=now,
    )
    sales_trend = calculate_sales_trend(
        business,
        days=30,
        as_of=now,
    )
    inventory = calculate_inventory_summary(business)
    debts = calculate_debt_summary(business)
    product_performance = calculate_product_performance(
        business,
        as_of=now,
    )
    product_profitability = calculate_product_profitability(
        business,
        days=30,
        as_of=now,
    )
    inventory_overstock = calculate_inventory_overstock(
        business,
        as_of=now,
    )
    confidence = calculate_data_confidence(
        business,
        as_of=now,
    )
    sales_anomaly = calculate_sales_anomaly(
        business,
        confidence=confidence,
        as_of=now,
    )
    business_health = calculate_business_health(
        sales_trend=sales_trend,
        inventory=inventory,
        debts=debts,
        product_performance=product_performance,
    )

    return {
        "business_id": business.id,
        "business_name": business.name,
        "generated_at": now,
        "sales": sales,
        "performance_periods": period_performance,
        "sales_trend": sales_trend,
        "inventory": inventory,
        "debts": debts,
        "products": product_performance,
        "product_profitability": product_profitability,
        "inventory_overstock": inventory_overstock,
        "sales_anomaly": sales_anomaly,
        "confidence": confidence,
        "business_health": business_health,
        "methodology": {
            "recognized_sale_statuses": list(RECOGNIZED_SALE_STATUSES),
            "sales_summary_scope": "all_time",
            "period_performance_windows": [
                "today",
                "rolling_7_days",
                "rolling_30_days",
            ],
            "today_comparison_basis": (
                "previous_day_same_elapsed_time"
            ),
            "sales_trend_days": 30,
            "slow_moving_days": SLOW_MOVING_DAYS,
            "dead_stock_days": DEAD_STOCK_DAYS,
            "stock_out_risk_days": STOCK_OUT_RISK_DAYS,
            "overstock_cover_days": OVERSTOCK_COVER_DAYS,
            "overstock_method": "recent_demand_days_of_cover",
            "anomaly_baseline_occurrences": ANOMALY_BASELINE_OCCURRENCES,
            "anomaly_change_threshold_percent": (
                ANOMALY_CHANGE_THRESHOLD_PERCENT
            ),
            "anomaly_min_active_baselines": ANOMALY_MIN_ACTIVE_BASELINES,
            "anomaly_comparison": "same_weekday_prior_4_occurrences",
            "confidence_lookback_days": CONFIDENCE_LOOKBACK_DAYS,
        },
    }
