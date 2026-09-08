from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from businesses.branch_access import ensure_main_branch
from inventory.models import BranchInventory
from inventory.restock_models import RestockPurchase
from sales.models import Sale
from sales.services import debt_snapshot


ZERO = Decimal("0.00")
RECOGNIZED_STATUSES = (
    Sale.Status.COMPLETED,
    Sale.Status.PARTIALLY_PAID,
)
LOOKBACK_DAYS = 30
MAX_TRANSFER_SUGGESTIONS = 12


def _money(value):
    return value if value is not None else ZERO


def _branch_matches(record_branch_id, *, branch, main_branch):
    if record_branch_id == branch.id:
        return True
    return branch.id == main_branch.id and record_branch_id is None


def _sale_profit(sale):
    historical_cost = sum(
        (_money(item.cost_price) * item.quantity for item in sale.items.all()),
        ZERO,
    )
    return _money(sale.total) - historical_cost, historical_cost


def _rank(rows, key):
    ordered = sorted(
        rows,
        key=lambda row: (-row[key], row["name"].casefold(), str(row["id"])),
    )
    return {row["id"]: index + 1 for index, row in enumerate(ordered)}


def _transfer_suggestions(*, branches, inventory_rows):
    by_product = defaultdict(list)
    for row in inventory_rows:
        by_product[row.product_id].append(row)

    suggestions = []
    for rows in by_product.values():
        if not rows:
            continue
        product = rows[0].product
        for destination in rows:
            if not destination.branch.is_active:
                continue
            available = destination.available_stock
            threshold = int(destination.low_stock_level)
            if available > threshold:
                continue

            target = threshold + 1
            needed = max(1, target - available)
            donors = []
            for donor in rows:
                if donor.branch_id == destination.branch_id or not donor.branch.is_active:
                    continue
                donor_floor = int(donor.low_stock_level) + 1
                surplus = donor.available_stock - donor_floor
                if surplus > 0:
                    donors.append((surplus, donor))
            if not donors:
                continue
            donors.sort(key=lambda item: (-item[0], item[1].branch.name.casefold()))
            surplus, donor = donors[0]
            quantity = min(needed, surplus)
            if quantity <= 0:
                continue
            suggestions.append(
                {
                    "productId": str(product.id),
                    "productName": product.name,
                    "sku": product.sku,
                    "unit": product.unit,
                    "sourceBranchId": str(donor.branch_id),
                    "sourceBranchName": donor.branch.name,
                    "destinationBranchId": str(destination.branch_id),
                    "destinationBranchName": destination.branch.name,
                    "suggestedQuantity": int(quantity),
                    "sourceAvailableStock": int(donor.available_stock),
                    "destinationAvailableStock": int(available),
                    "destinationLowStockLevel": threshold,
                    "reason": (
                        f"{destination.branch.name} is at or below its low-stock "
                        f"threshold while {donor.branch.name} has transferable surplus."
                    ),
                    "requiresConfirmation": True,
                }
            )

    suggestions.sort(
        key=lambda item: (
            item["destinationAvailableStock"] - item["destinationLowStockLevel"],
            item["productName"].casefold(),
        )
    )
    return suggestions[:MAX_TRANSFER_SUGGESTIONS]


def calculate_multibranch_intelligence(business):
    """Returns deterministic branch comparison data without changing stock."""
    main_branch = ensure_main_branch(business=business, created_by=business.owner)
    branches = list(
        business.branches.filter(is_active=True).order_by("-is_main", "name", "id")
    )
    now = timezone.now()
    period_start = now - timedelta(days=LOOKBACK_DAYS)

    sales = list(
        Sale.objects.filter(
            business=business,
            status__in=RECOGNIZED_STATUSES,
            completed_at__gte=period_start,
            completed_at__lte=now,
        )
        .select_related("branch", "customer")
        .prefetch_related("items")
    )
    inventory_rows = list(
        BranchInventory.objects.filter(
            branch__in=branches,
            product__business=business,
            product__is_active=True,
        ).select_related("branch", "product")
    )
    debt_sales = list(
        Sale.objects.filter(
            business=business,
            customer__isnull=False,
            outstanding_balance__gt=ZERO,
            status__in=RECOGNIZED_STATUSES,
        ).select_related("branch", "customer")
    )
    restocks = list(
        RestockPurchase.objects.filter(business=business).select_related("branch")
    )

    rows = []
    for branch in branches:
        branch_sales = [
            sale
            for sale in sales
            if _branch_matches(sale.branch_id, branch=branch, main_branch=main_branch)
        ]
        revenue = ZERO
        historical_cost = ZERO
        units_sold = 0
        for sale in branch_sales:
            gross_profit, sale_cost = _sale_profit(sale)
            revenue += _money(sale.total)
            historical_cost += sale_cost
            units_sold += sum(item.quantity for item in sale.items.all())
        gross_profit = revenue - historical_cost
        margin = (
            ((gross_profit / revenue) * Decimal("100")).quantize(Decimal("0.01"))
            if revenue > ZERO
            else ZERO
        )

        branch_inventory = [row for row in inventory_rows if row.branch_id == branch.id]
        total_stock_units = sum(row.stock for row in branch_inventory)
        reserved_stock_units = sum(row.reserved_stock for row in branch_inventory)
        available_stock_units = sum(row.available_stock for row in branch_inventory)
        inventory_cost_value = sum(
            (_money(row.product.cost_price) * row.stock for row in branch_inventory),
            ZERO,
        )
        low_stock_count = sum(
            1 for row in branch_inventory if row.available_stock <= row.low_stock_level
        )
        stockout_count = sum(1 for row in branch_inventory if row.available_stock == 0)

        customer_debt = ZERO
        customer_ids = set()
        for sale in debt_sales:
            if not _branch_matches(
                sale.branch_id, branch=branch, main_branch=main_branch
            ):
                continue
            snapshot = debt_snapshot(sale=sale)
            total_due = _money(snapshot["total_debt_payable"])
            if total_due > ZERO:
                customer_debt += total_due
                customer_ids.add(sale.customer_id)

        branch_restocks = [
            purchase
            for purchase in restocks
            if _branch_matches(
                purchase.branch_id, branch=branch, main_branch=main_branch
            )
        ]
        supplier_debt = sum(
            (max(ZERO, _money(p.total_amount) - _money(p.amount_paid)) for p in branch_restocks),
            ZERO,
        )

        rows.append(
            {
                "id": branch.id,
                "name": branch.name,
                "code": branch.code,
                "location": branch.location,
                "isMain": branch.is_main,
                "salesCount": len(branch_sales),
                "unitsSold": units_sold,
                "revenue": revenue,
                "historicalCost": historical_cost,
                "grossProfit": gross_profit,
                "profitMargin": margin,
                "activeProducts": len(branch_inventory),
                "totalStockUnits": total_stock_units,
                "reservedStockUnits": reserved_stock_units,
                "availableStockUnits": available_stock_units,
                "inventoryCostValue": inventory_cost_value,
                "lowStockCount": low_stock_count,
                "stockoutCount": stockout_count,
                "customerDebt": customer_debt,
                "customersWithDebt": len(customer_ids),
                "supplierDebt": supplier_debt,
            }
        )

    revenue_ranks = _rank(rows, "revenue") if rows else {}
    profit_ranks = _rank(rows, "grossProfit") if rows else {}
    for row in rows:
        row["revenueRank"] = revenue_ranks[row["id"]]
        row["profitRank"] = profit_ranks[row["id"]]
        row["id"] = str(row["id"])
        for key in (
            "revenue", "historicalCost", "grossProfit", "profitMargin",
            "inventoryCostValue", "customerDebt", "supplierDebt",
        ):
            row[key] = str(row[key])

    consolidated_revenue = sum((_money(s.total) for s in sales), ZERO)
    consolidated_cost = sum((_sale_profit(s)[1] for s in sales), ZERO)
    consolidated_profit = consolidated_revenue - consolidated_cost
    consolidated_margin = (
        ((consolidated_profit / consolidated_revenue) * Decimal("100")).quantize(
            Decimal("0.01")
        )
        if consolidated_revenue > ZERO
        else ZERO
    )

    return {
        "version": 1,
        "generatedAt": now,
        "business": {
            "id": str(business.id),
            "name": business.name,
            "businessType": business.business_type,
        },
        "period": {
            "days": LOOKBACK_DAYS,
            "start": period_start,
            "end": now,
        },
        "consolidated": {
            "branchCount": len(branches),
            "salesCount": len(sales),
            "revenue": str(consolidated_revenue),
            "historicalCost": str(consolidated_cost),
            "grossProfit": str(consolidated_profit),
            "profitMargin": str(consolidated_margin),
            "totalStockUnits": sum(row.stock for row in inventory_rows),
            "reservedStockUnits": sum(row.reserved_stock for row in inventory_rows),
            "availableStockUnits": sum(row.available_stock for row in inventory_rows),
            "inventoryCostValue": str(
                sum(
                    (_money(row.product.cost_price) * row.stock for row in inventory_rows),
                    ZERO,
                )
            ),
            "customerDebt": str(
                sum((Decimal(row["customerDebt"]) for row in rows), ZERO)
            ),
            "supplierDebt": str(
                sum((Decimal(row["supplierDebt"]) for row in rows), ZERO)
            ),
        },
        "branches": rows,
        "transferSuggestions": _transfer_suggestions(
            branches=branches, inventory_rows=inventory_rows
        ),
        "safety": {
            "calculationAuthority": "django",
            "transferSuggestionsAreReadOnly": True,
            "transfersRequireExplicitConfirmation": True,
        },
    }
