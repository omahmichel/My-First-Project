from decimal import Decimal

from django.db.models import F, Sum
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from inventory.restock_models import RestockPurchase
from sales.models import Sale, SaleItem

from ..ai.context import build_verified_intelligence_context
from ..ai.reporting import generate_report_narrative
from ..models import GeneratedReport
from .business_analysis import RECOGNIZED_SALE_STATUSES


REPORT_DEFINITIONS = {
    "daily_summary": {
        "title": "Daily Business Summary",
        "period_key": "today",
        "period_label": "Today",
    },
    "weekly_management": {
        "title": "Weekly Management Report",
        "period_key": "last7Days",
        "period_label": "Last 7 days",
    },
    "monthly_management": {
        "title": "Monthly Management Report",
        "period_key": "last30Days",
        "period_label": "Last 30 days",
    },
    "sales_profit": {
        "title": "Sales & Profit Report",
        "period_key": "last30Days",
        "period_label": "Last 30 days",
    },
    "stock_risk_restocking": {
        "title": "Stock Risk & Restocking Report",
        "period_key": None,
        "period_label": "Current stock position",
    },
    "supplier_balances": {
        "title": "Supplier Balances Report",
        "period_key": None,
        "period_label": "Current balances",
    },
    "customer_debt": {
        "title": "Customer Debt Report",
        "period_key": None,
        "period_label": "Current balances",
    },
}


def _number(value):
    if value in (None, ""):
        return Decimal("0")
    return Decimal(str(value))


def _money(value):
    return f"₵{_number(value):,.2f}"


def _percent(value):
    return f"{_number(value):,.2f}%"


def _metric(key, label, value, value_format):
    return {
        "key": key,
        "label": label,
        "value": str(value),
        "format": value_format,
    }


def _period_from_entry(entry, label):
    return {
        "label": label,
        "start": entry.get("periodStart"),
        "end": entry.get("periodEnd"),
    }


def _business_health_attention(context):
    health = context["overview"].get("business_health") or {}
    reasons = list(health.get("reasons") or [])

    if reasons:
        return reasons[:4]

    return [
        "No verified business-health attention signal is currently active."
    ]


def _active_recommendation_actions(context):
    recommendations = context.get("active_recommendations") or []
    actions = []

    for item in recommendations[:4]:
        summary = str(item.get("summary") or "").strip()
        if summary:
            actions.append(summary)

    if actions:
        return actions

    return [
        "Continue recording sales, stock movements, restocks and payments "
        "accurately so future reports remain reliable."
    ]


def _period_top_products(*, business, entry):
    """Rank sale-item snapshots inside the report's own time window."""
    start = _period_datetime(entry.get("periodStart"))
    end = _period_datetime(entry.get("periodEnd"))

    if not start or not end:
        return []

    rows = (
        SaleItem.objects.filter(
            sale__business=business,
            sale__status__in=RECOGNIZED_SALE_STATUSES,
            sale__completed_at__gte=start,
            sale__completed_at__lt=end,
        )
        .values("product_name", "sku")
        .annotate(quantity_sold=Sum("quantity"))
        .order_by("-quantity_sold", "product_name", "sku")[:5]
    )

    return [
        {
            "name": row["product_name"],
            "sku": row["sku"],
            "quantitySold": str(row["quantity_sold"]),
        }
        for row in rows
    ]


def _performance_report(context, definition, business):
    overview = context["overview"]
    periods = overview.get("performance_periods") or {}
    entry = periods.get(definition["period_key"]) or {}

    revenue = entry.get("revenue", "0")
    gross_profit = entry.get("grossProfit", "0")
    margin = entry.get("profitMargin", "0")
    sale_count = entry.get("saleCount", 0)
    units_sold = entry.get("unitsSold", 0)
    historical_cost = entry.get("historicalCost", "0")

    previous_revenue = entry.get("previousRevenue", "0")
    direction = entry.get("revenueDirection", "flat")
    change_percent = entry.get("revenueChangePercentage")

    if change_percent is None:
        why = [
            (
                f"Revenue is {direction}, but the previous comparable period "
                f"recorded {_money(previous_revenue)}, so a percentage change "
                "is not available."
            )
        ]
    else:
        why = [
            (
                f"Revenue is {direction} by "
                f"{abs(_number(change_percent)):,.2f}% compared with the "
                "previous comparable period."
            )
        ]

    top_products = _period_top_products(
        business=business,
        entry=entry,
    )
    sections = []

    if top_products:
        sections.append(
            {
                "key": "top_products",
                "title": "Top-selling products",
                "columns": [
                    {"key": "name", "label": "Product", "format": "text"},
                    {"key": "sku", "label": "SKU", "format": "text"},
                    {
                        "key": "quantitySold",
                        "label": "Qty sold",
                        "format": "number",
                    },
                ],
                "rows": [
                    {
                        "name": item.get("name"),
                        "sku": item.get("sku"),
                        "quantitySold": item.get("quantitySold", 0),
                    }
                    for item in top_products[:5]
                ],
            }
        )

    return {
        "period": _period_from_entry(entry, definition["period_label"]),
        "metrics": [
            _metric("revenue", "Revenue", revenue, "currency"),
            _metric(
                "gross_profit",
                "Gross profit",
                gross_profit,
                "currency",
            ),
            _metric(
                "historical_cost",
                "Historical cost",
                historical_cost,
                "currency",
            ),
            _metric("profit_margin", "Profit margin", margin, "percent"),
            _metric("sales", "Sales", sale_count, "number"),
            _metric("units", "Units sold", units_sold, "number"),
        ],
        "managementQuestions": {
            "whatHappened": [
                (
                    f"{sale_count} recognized sale(s) covering "
                    f"{units_sold} unit(s) generated {_money(revenue)}."
                ),
                (
                    f"Historical cost was {_money(historical_cost)}, producing "
                    f"{_money(gross_profit)} gross profit at "
                    f"{_percent(margin)} margin."
                ),
            ],
            "why": why,
            "attention": _business_health_attention(context),
            "nextActions": _active_recommendation_actions(context),
        },
        "sections": sections,
    }


def _stock_report(context, definition):
    overview = context["overview"]
    inventory = overview.get("inventory") or {}
    products = overview.get("products") or {}

    stock_out = products.get("stockOutRisks") or []
    slow = products.get("slowMovingProducts") or []
    dead = products.get("deadStockCandidates") or []

    sections = []

    if stock_out:
        sections.append(
            {
                "key": "stock_out_risks",
                "title": "Stock-out risks",
                "columns": [
                    {"key": "name", "label": "Product", "format": "text"},
                    {"key": "sku", "label": "SKU", "format": "text"},
                    {
                        "key": "availableStock",
                        "label": "Available",
                        "format": "number",
                    },
                    {
                        "key": "estimatedDaysRemaining",
                        "label": "Days left",
                        "format": "number",
                    },
                ],
                "rows": stock_out[:10],
            }
        )

    if slow:
        sections.append(
            {
                "key": "slow_moving",
                "title": "Slow-moving stock",
                "columns": [
                    {"key": "name", "label": "Product", "format": "text"},
                    {"key": "sku", "label": "SKU", "format": "text"},
                    {
                        "key": "availableStock",
                        "label": "Available",
                        "format": "number",
                    },
                    {
                        "key": "inventoryCostValue",
                        "label": "Cost value",
                        "format": "currency",
                    },
                ],
                "rows": slow[:10],
            }
        )

    if dead:
        sections.append(
            {
                "key": "dead_stock",
                "title": "Dead-stock candidates",
                "columns": [
                    {"key": "name", "label": "Product", "format": "text"},
                    {"key": "sku", "label": "SKU", "format": "text"},
                    {
                        "key": "availableStock",
                        "label": "Available",
                        "format": "number",
                    },
                    {
                        "key": "inventoryCostValue",
                        "label": "Cost value",
                        "format": "currency",
                    },
                ],
                "rows": dead[:10],
            }
        )

    attention = []
    if stock_out:
        attention.append(
            f"{len(stock_out)} product(s) are inside the verified stock-out "
            "risk window."
        )
    if slow:
        attention.append(
            f"{len(slow)} product(s) are currently slow-moving."
        )
    if dead:
        attention.append(
            f"{len(dead)} product(s) meet the dead-stock candidate rule."
        )
    if not attention:
        attention.append(
            "No stock-out, slow-moving or dead-stock candidate is currently "
            "active under the verified rules."
        )

    return {
        "period": {
            "label": definition["period_label"],
            "start": None,
            "end": context["overview"].get("generated_at"),
        },
        "metrics": [
            _metric(
                "inventory_cost",
                "Inventory cost",
                inventory.get("inventoryCostValue", "0"),
                "currency",
            ),
            _metric(
                "potential_retail",
                "Potential retail value",
                inventory.get("potentialRetailValue", "0"),
                "currency",
            ),
            _metric(
                "available_units",
                "Available units",
                inventory.get("availableStockUnits", 0),
                "number",
            ),
            _metric(
                "low_stock",
                "Low-stock products",
                inventory.get("lowStockCount", 0),
                "number",
            ),
            _metric(
                "stock_out",
                "Stock-out risks",
                len(stock_out),
                "number",
            ),
            _metric(
                "dead_stock",
                "Dead-stock candidates",
                len(dead),
                "number",
            ),
        ],
        "managementQuestions": {
            "whatHappened": [
                (
                    f"Current physical inventory cost is "
                    f"{_money(inventory.get('inventoryCostValue'))}, with "
                    f"{inventory.get('availableStockUnits', 0)} available "
                    "unit(s)."
                )
            ],
            "why": [
                (
                    "StockFlow applies verified available-stock, recent-demand "
                    "and stock-movement rules to identify stock-out, slow-moving "
                    "and dead-stock signals."
                )
            ],
            "attention": attention,
            "nextActions": [
                (
                    "Review stock-out candidates before the next purchase. "
                    "Confirm supplier lead time and safety stock manually before "
                    "choosing an order quantity."
                ),
                (
                    "Review slow-moving and dead-stock items before tying up "
                    "additional cash in the same products."
                ),
            ],
        },
        "sections": sections,
    }


def _supplier_rows(business):
    purchases = (
        RestockPurchase.objects.filter(
            business=business,
            total_amount__gt=F("amount_paid"),
        )
        .select_related("supplier")
        .order_by("-purchase_date", "-created_at")[:25]
    )

    return [
        {
            "supplier": purchase.supplier.name,
            "purchaseNumber": purchase.purchase_number,
            "purchaseDate": purchase.purchase_date.isoformat(),
            "totalAmount": str(purchase.total_amount),
            "amountPaid": str(purchase.amount_paid),
            "balance": str(purchase.outstanding_balance),
        }
        for purchase in purchases
    ]


def _supplier_report(context, definition, business):
    overview = context["overview"]
    debts = overview.get("debts") or {}
    rows = _supplier_rows(business)

    return {
        "period": {
            "label": definition["period_label"],
            "start": None,
            "end": overview.get("generated_at"),
        },
        "metrics": [
            _metric(
                "supplier_debt",
                "Supplier debt",
                debts.get("supplierDebt", "0"),
                "currency",
            ),
            _metric(
                "open_purchases",
                "Purchases with balance",
                debts.get("supplierPurchasesWithBalance", 0),
                "number",
            ),
        ],
        "managementQuestions": {
            "whatHappened": [
                (
                    f"Verified supplier payables total "
                    f"{_money(debts.get('supplierDebt'))} across "
                    f"{debts.get('supplierPurchasesWithBalance', 0)} "
                    "purchase balance(s)."
                )
            ],
            "why": [
                (
                    "These balances remain because the recorded purchase total "
                    "is greater than the amount paid."
                )
            ],
            "attention": (
                [
                    f"{len(rows)} open purchase balance(s) are listed for review."
                ]
                if rows
                else ["No supplier purchase balance is currently outstanding."]
            ),
            "nextActions": [
                (
                    "Reconcile each balance with the supplier statement before "
                    "recording or making a payment."
                )
            ],
        },
        "sections": [
            {
                "key": "supplier_balances",
                "title": "Open supplier purchases",
                "columns": [
                    {
                        "key": "supplier",
                        "label": "Supplier",
                        "format": "text",
                    },
                    {
                        "key": "purchaseNumber",
                        "label": "Purchase",
                        "format": "text",
                    },
                    {
                        "key": "purchaseDate",
                        "label": "Date",
                        "format": "date",
                    },
                    {
                        "key": "totalAmount",
                        "label": "Total",
                        "format": "currency",
                    },
                    {
                        "key": "amountPaid",
                        "label": "Paid",
                        "format": "currency",
                    },
                    {
                        "key": "balance",
                        "label": "Balance",
                        "format": "currency",
                    },
                ],
                "rows": rows,
            }
        ],
    }


def _customer_rows(business):
    sales = (
        Sale.objects.filter(
            business=business,
            customer__isnull=False,
            outstanding_balance__gt=Decimal("0"),
            status__in=("completed", "partially_paid"),
        )
        .select_related("customer")
        .order_by("debt_due_date", "-completed_at")[:25]
    )

    today = timezone.localdate()
    rows = []

    for sale in sales:
        due_date = sale.debt_due_date
        rows.append(
            {
                "customer": getattr(
                    sale.customer,
                    "name",
                    str(sale.customer),
                ),
                "invoiceNumber": sale.invoice_number,
                "dueDate": (
                    due_date.isoformat()
                    if due_date
                    else None
                ),
                "principalOutstanding": str(
                    sale.outstanding_balance
                ),
                "overdue": bool(
                    due_date
                    and due_date < today
                    and sale.outstanding_balance > Decimal("0")
                ),
            }
        )

    return rows


def _customer_report(context, definition, business):
    overview = context["overview"]
    debts = overview.get("debts") or {}
    rows = _customer_rows(business)
    overdue_count = sum(1 for row in rows if row["overdue"])

    return {
        "period": {
            "label": definition["period_label"],
            "start": None,
            "end": overview.get("generated_at"),
        },
        "metrics": [
            _metric(
                "customer_debt",
                "Customer debt payable",
                debts.get("customerDebt", "0"),
                "currency",
            ),
            _metric(
                "customers_with_debt",
                "Customers with debt",
                debts.get("customersWithDebt", 0),
                "number",
            ),
            _metric(
                "overdue_invoices",
                "Overdue invoices listed",
                overdue_count,
                "number",
            ),
        ],
        "managementQuestions": {
            "whatHappened": [
                (
                    f"Verified customer debt payable is "
                    f"{_money(debts.get('customerDebt'))} across "
                    f"{debts.get('customersWithDebt', 0)} customer(s)."
                )
            ],
            "why": [
                (
                    "The aggregate debt metric follows StockFlow's authoritative "
                    "debt service and may include overdue charges. Detail rows "
                    "below list the recorded invoice principal still outstanding."
                )
            ],
            "attention": (
                [
                    f"{overdue_count} listed invoice(s) are past their recorded "
                    "due date."
                ]
                if overdue_count
                else ["No listed customer invoice is currently past its due date."]
            ),
            "nextActions": [
                (
                    "Review each outstanding invoice and follow up with the "
                    "customer using the recorded payment history before taking "
                    "any collection action."
                )
            ],
        },
        "sections": [
            {
                "key": "customer_debt",
                "title": "Outstanding customer invoices",
                "columns": [
                    {
                        "key": "customer",
                        "label": "Customer",
                        "format": "text",
                    },
                    {
                        "key": "invoiceNumber",
                        "label": "Invoice",
                        "format": "text",
                    },
                    {
                        "key": "dueDate",
                        "label": "Due date",
                        "format": "date",
                    },
                    {
                        "key": "principalOutstanding",
                        "label": "Principal",
                        "format": "currency",
                    },
                    {
                        "key": "overdue",
                        "label": "Overdue",
                        "format": "boolean",
                    },
                ],
                "rows": rows,
            }
        ],
    }


def build_report_payload(*, business, report_type):
    definition = REPORT_DEFINITIONS[report_type]
    context = build_verified_intelligence_context(business)

    if report_type in {
        "daily_summary",
        "weekly_management",
        "monthly_management",
        "sales_profit",
    }:
        specific = _performance_report(
            context,
            definition,
            business,
        )
    elif report_type == "stock_risk_restocking":
        specific = _stock_report(context, definition)
    elif report_type == "supplier_balances":
        specific = _supplier_report(context, definition, business)
    else:
        specific = _customer_report(context, definition, business)

    confidence = (
        context["overview"].get("confidence") or {}
    ).get("grade", "low")

    return {
        "version": 1,
        "business": {
            "id": str(business.id),
            "name": business.name,
            "businessType": business.business_type,
        },
        "reportType": report_type,
        "title": definition["title"],
        "period": specific["period"],
        "confidence": confidence,
        "metrics": specific["metrics"],
        "managementQuestions": specific["managementQuestions"],
        "sections": specific["sections"],
        "sourceSummary": {
            "overviewGeneratedAt": context["overview"].get(
                "generated_at"
            ),
            "availableForecastHorizons": [
                int(item)
                for item in context.get("stored_forecasts", {}).keys()
            ],
            "activeRecommendationCount": len(
                context.get("active_recommendations") or []
            ),
            "calculationAuthority": "django",
        },
    }


def _period_datetime(value):
    if not value:
        return None
    return parse_datetime(value)


def generate_and_store_report(
    *,
    business,
    generated_by,
    report_type,
    include_ai_summary=False,
):
    payload = build_report_payload(
        business=business,
        report_type=report_type,
    )

    ai_result = {
        "status": GeneratedReport.AIStatus.NOT_REQUESTED,
        "narrative": "",
        "provider": "",
        "model": "",
    }

    if include_ai_summary:
        ai_result = generate_report_narrative(payload)

    period = payload.get("period") or {}

    return GeneratedReport.objects.create(
        business=business,
        generated_by=generated_by,
        report_type=report_type,
        title=payload["title"],
        period_start=_period_datetime(period.get("start")),
        period_end=_period_datetime(period.get("end")),
        data_confidence=payload["confidence"],
        payload=payload,
        ai_narrative=ai_result.get("narrative", ""),
        ai_status=ai_result.get(
            "status",
            GeneratedReport.AIStatus.UNAVAILABLE,
        ),
        ai_provider=ai_result.get("provider", ""),
        ai_model=ai_result.get("model", ""),
    )
