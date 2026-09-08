from decimal import Decimal

from inventory.models import BranchInventory
from inventory.restock_models import RestockPurchase, Supplier
from sales.models import Sale


ZERO = Decimal("0.00")
RECOGNIZED_SALE_STATUSES = (
    Sale.Status.COMPLETED,
    Sale.Status.PARTIALLY_PAID,
)

DATASETS = {
    "sales": {
        "label": "Sales ledger",
        "description": "Completed and partially paid sales with branch-aware accounting totals.",
        "dateFilter": True,
        "branchAware": True,
    },
    "inventory": {
        "label": "Inventory valuation",
        "description": "Current branch inventory, cost value and potential retail value.",
        "dateFilter": False,
        "branchAware": True,
    },
    "purchases": {
        "label": "Purchases and restocking",
        "description": "Supplier restock purchases, payment state and outstanding balances.",
        "dateFilter": True,
        "branchAware": True,
    },
    "customers": {
        "label": "Customer balances",
        "description": "Current customer purchase totals and outstanding balances.",
        "dateFilter": False,
        "branchAware": False,
    },
    "suppliers": {
        "label": "Supplier balances",
        "description": "Current supplier purchasing and outstanding balance summary.",
        "dateFilter": False,
        "branchAware": False,
    },
}


def accounting_export_manifest():
    return {
        "version": 1,
        "format": "csv",
        "currency": "GHS",
        "datasets": [
            {"key": key, **metadata}
            for key, metadata in DATASETS.items()
        ],
        "dateParameters": {
            "from": "dateFrom",
            "to": "dateTo",
            "format": "YYYY-MM-DD",
        },
        "safety": {
            "authoritativeSource": "django",
            "readOnly": True,
            "transactionalRecordsChanged": False,
        },
    }


def _money(value):
    if value is None:
        return ZERO
    return Decimal(value).quantize(Decimal("0.01"))


def _money_text(value):
    return f"{_money(value):.2f}"


def _date_time_text(value):
    if not value:
        return ""
    return value.isoformat()


def _main_branch(business):
    return business.branches.filter(is_main=True).first()


def _branch_values(branch, main_branch):
    resolved = branch or main_branch
    if not resolved:
        return "", ""
    return resolved.name, resolved.code


def _filter_sales(queryset, *, date_from=None, date_to=None):
    if date_from:
        queryset = queryset.filter(completed_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(completed_at__date__lte=date_to)
    return queryset


def _filter_purchases(queryset, *, date_from=None, date_to=None):
    if date_from:
        queryset = queryset.filter(purchase_date__gte=date_from)
    if date_to:
        queryset = queryset.filter(purchase_date__lte=date_to)
    return queryset


def _sales_export(*, business, date_from=None, date_to=None):
    main_branch = _main_branch(business)
    sales = (
        Sale.objects.filter(
            business=business,
            status__in=RECOGNIZED_SALE_STATUSES,
        )
        .select_related("branch", "customer")
        .prefetch_related("items")
        .order_by("completed_at", "id")
    )
    sales = _filter_sales(sales, date_from=date_from, date_to=date_to)

    headers = [
        "Sale number",
        "Invoice number",
        "Completed at",
        "Branch",
        "Branch code",
        "Customer",
        "Customer phone",
        "Payment method",
        "Status",
        "Subtotal (GHS)",
        "Discount (GHS)",
        "Sale total (GHS)",
        "Amount paid (GHS)",
        "Balance due (GHS)",
        "Historical cost (GHS)",
        "Gross profit (GHS)",
    ]
    rows = []
    for sale in sales:
        branch_name, branch_code = _branch_values(sale.branch, main_branch)
        historical_cost = sum(
            (_money(item.cost_price) * item.quantity for item in sale.items.all()),
            ZERO,
        )
        gross_profit = _money(sale.total) - historical_cost
        rows.append(
            [
                sale.sale_number,
                sale.invoice_number,
                _date_time_text(sale.completed_at or sale.created_at),
                branch_name,
                branch_code,
                sale.customer_name,
                sale.customer_phone,
                sale.payment_method,
                sale.status,
                _money_text(sale.subtotal),
                _money_text(sale.discount),
                _money_text(sale.total),
                _money_text(sale.amount_paid),
                _money_text(sale.outstanding_balance),
                _money_text(historical_cost),
                _money_text(gross_profit),
            ]
        )
    return headers, rows


def _inventory_export(*, business, **_kwargs):
    rows_qs = (
        BranchInventory.objects.filter(
            branch__business=business,
            product__business=business,
        )
        .select_related("branch", "product")
        .order_by("branch__name", "product__name", "id")
    )
    headers = [
        "Branch",
        "Branch code",
        "Branch active",
        "SKU",
        "Product",
        "Category",
        "Product type",
        "Unit",
        "Stock",
        "Reserved stock",
        "Available stock",
        "Low-stock level",
        "Cost price (GHS)",
        "Selling price (GHS)",
        "Inventory cost value (GHS)",
        "Potential retail value (GHS)",
        "Product active",
    ]
    rows = []
    for item in rows_qs:
        product = item.product
        cost_value = _money(product.cost_price) * item.stock
        retail_value = _money(product.selling_price) * item.stock
        rows.append(
            [
                item.branch.name,
                item.branch.code,
                "yes" if item.branch.is_active else "no",
                product.sku,
                product.name,
                product.category,
                product.product_type,
                product.unit,
                item.stock,
                item.reserved_stock,
                item.available_stock,
                item.low_stock_level,
                _money_text(product.cost_price),
                _money_text(product.selling_price),
                _money_text(cost_value),
                _money_text(retail_value),
                "yes" if product.is_active else "no",
            ]
        )
    return headers, rows


def _purchases_export(*, business, date_from=None, date_to=None):
    main_branch = _main_branch(business)
    purchases = (
        RestockPurchase.objects.filter(business=business)
        .select_related("branch", "supplier")
        .prefetch_related("items")
        .order_by("purchase_date", "created_at", "id")
    )
    purchases = _filter_purchases(
        purchases, date_from=date_from, date_to=date_to
    )
    headers = [
        "Purchase number",
        "Purchase date",
        "Branch",
        "Branch code",
        "Supplier",
        "Supplier reference",
        "Payment status",
        "Items",
        "Units received",
        "Purchase total (GHS)",
        "Amount paid (GHS)",
        "Outstanding balance (GHS)",
    ]
    rows = []
    for purchase in purchases:
        branch_name, branch_code = _branch_values(purchase.branch, main_branch)
        purchase_items = list(purchase.items.all())
        rows.append(
            [
                purchase.purchase_number,
                purchase.purchase_date.isoformat(),
                branch_name,
                branch_code,
                purchase.supplier.name,
                purchase.supplier_reference,
                purchase.payment_status,
                len(purchase_items),
                sum(item.quantity for item in purchase_items),
                _money_text(purchase.total_amount),
                _money_text(purchase.amount_paid),
                _money_text(purchase.outstanding_balance),
            ]
        )
    return headers, rows


def _customers_export(*, business, **_kwargs):
    customers = business.customers.all().order_by("name", "id")
    headers = [
        "Customer",
        "Phone",
        "Email",
        "Address",
        "Total purchases (GHS)",
        "Outstanding balance (GHS)",
        "Active",
        "Created at",
    ]
    rows = [
        [
            customer.name,
            customer.phone,
            customer.email,
            customer.address,
            _money_text(customer.total_purchases),
            _money_text(customer.outstanding_balance),
            "yes" if customer.is_active else "no",
            _date_time_text(customer.created_at),
        ]
        for customer in customers
    ]
    return headers, rows


def _suppliers_export(*, business, **_kwargs):
    suppliers = (
        Supplier.objects.filter(business=business)
        .prefetch_related("restock_purchases")
        .order_by("name", "id")
    )
    headers = [
        "Supplier",
        "Phone",
        "Email",
        "Address",
        "Active",
        "Purchase count",
        "Total purchases (GHS)",
        "Amount paid (GHS)",
        "Outstanding balance (GHS)",
    ]
    rows = []
    for supplier in suppliers:
        purchases = list(supplier.restock_purchases.all())
        total = sum((_money(item.total_amount) for item in purchases), ZERO)
        paid = sum((_money(item.amount_paid) for item in purchases), ZERO)
        rows.append(
            [
                supplier.name,
                supplier.phone,
                supplier.email,
                supplier.address,
                "yes" if supplier.is_active else "no",
                len(purchases),
                _money_text(total),
                _money_text(paid),
                _money_text(max(ZERO, total - paid)),
            ]
        )
    return headers, rows


_BUILDERS = {
    "sales": _sales_export,
    "inventory": _inventory_export,
    "purchases": _purchases_export,
    "customers": _customers_export,
    "suppliers": _suppliers_export,
}


def build_accounting_export(*, business, dataset, date_from=None, date_to=None):
    builder = _BUILDERS.get(dataset)
    if not builder:
        raise KeyError(dataset)
    headers, rows = builder(
        business=business,
        date_from=date_from,
        date_to=date_to,
    )
    return {
        "dataset": dataset,
        "headers": headers,
        "rows": rows,
    }
