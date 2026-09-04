from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from rest_framework import serializers

from .models import Product, StockMovement
from .restock_models import (
    RestockItem,
    RestockPayment,
    RestockPurchase,
    Supplier,
)

CENT = Decimal("0.01")


def money(value):
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def status_for(total, paid):
    if paid <= 0:
        return RestockPurchase.PaymentStatus.UNPAID
    if paid >= total:
        return RestockPurchase.PaymentStatus.PAID
    return RestockPurchase.PaymentStatus.PARTIAL


@transaction.atomic
def create_restock(*, business, user, data):
    supplier = (
        Supplier.objects.select_for_update()
        .filter(pk=data["supplierId"], business=business, is_active=True)
        .first()
    )
    if not supplier:
        raise serializers.ValidationError(
            {"supplierId": "Select an active supplier for this business."}
        )

    product_ids = [item["productId"] for item in data["items"]]
    products = {
        str(product.id): product
        for product in Product.objects.select_for_update().filter(
            business=business, is_active=True, id__in=product_ids
        )
    }
    if any(str(product_id) not in products for product_id in product_ids):
        raise serializers.ValidationError(
            {"items": "One or more products do not belong to this business."}
        )

    total = money(sum(
        (
            money(item["unitCost"]) * item["quantity"]
            for item in data["items"]
        ),
        Decimal("0.00"),
    ))
    paid = money(data.get("initialPayment", Decimal("0.00")))
    if paid > total:
        raise serializers.ValidationError(
            {"initialPayment": "Amount paid cannot exceed the restock total."}
        )

    purchase = RestockPurchase.objects.create(
        business=business,
        supplier=supplier,
        supplier_reference=data.get("supplierReference", "").strip(),
        purchase_date=data["purchaseDate"],
        total_amount=total,
        amount_paid=paid,
        payment_status=status_for(total, paid),
        created_by=user,
    )

    for item in data["items"]:
        product = products[str(item["productId"])]
        quantity = int(item["quantity"])
        unit_cost = money(item["unitCost"])
        previous_stock = product.stock
        new_stock = previous_stock + quantity

        if previous_stock:
            next_cost = money(
                (
                    Decimal(previous_stock) * product.cost_price
                    + Decimal(quantity) * unit_cost
                )
                / Decimal(new_stock)
            )
        else:
            next_cost = unit_cost

        product.stock = new_stock
        product.cost_price = next_cost
        product.save(update_fields=("stock", "cost_price", "updated_at"))

        RestockItem.objects.create(
            purchase=purchase,
            product=product,
            quantity=quantity,
            unit_cost=unit_cost,
            line_total=money(unit_cost * quantity),
        )
        StockMovement.objects.create(
            business=business,
            product=product,
            movement_type=StockMovement.MovementType.STOCK_IN,
            quantity=quantity,
            previous_stock=previous_stock,
            new_stock=new_stock,
            reason=f"Restock {purchase.purchase_number} from {supplier.name}",
            created_by=user,
        )

    if paid > 0:
        RestockPayment.objects.create(
            business=business,
            purchase=purchase,
            amount=paid,
            method=data.get("paymentMethod", RestockPayment.Method.CASH),
            recorded_by=user,
        )
    return purchase


@transaction.atomic
def record_payment(*, business, purchase_id, user, data):
    purchase = (
        RestockPurchase.objects.select_for_update()
        .filter(pk=purchase_id, business=business)
        .first()
    )
    if not purchase:
        raise serializers.ValidationError(
            {"purchase": "Restock purchase not found."}
        )

    amount = money(data["amount"])
    if purchase.outstanding_balance <= 0:
        raise serializers.ValidationError(
            {"amount": "This purchase is already fully paid."}
        )
    if amount > purchase.outstanding_balance:
        raise serializers.ValidationError(
            {"amount": "Payment cannot exceed the outstanding balance."}
        )

    RestockPayment.objects.create(
        business=business,
        purchase=purchase,
        amount=amount,
        method=data.get("method", RestockPayment.Method.CASH),
        note=data.get("note", "").strip(),
        recorded_by=user,
    )
    purchase.amount_paid = money(purchase.amount_paid + amount)
    purchase.payment_status = status_for(
        purchase.total_amount, purchase.amount_paid
    )
    purchase.save(update_fields=("amount_paid", "payment_status"))
    return purchase
