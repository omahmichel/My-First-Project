from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers

from customers.models import Customer
from inventory.models import Product, StockMovement
from .models import DocumentSequence, Payment, Sale, SaleItem


def _load_customer(business, customer_id):
    # Locks the selected active customer inside the current business.
    if not customer_id:
        return None

    return get_object_or_404(
        Customer.objects.select_for_update(),
        pk=customer_id,
        business=business,
        is_active=True,
    )


def _load_products(business, checkout_items):
    # Locks every requested product before checking or changing stock.
    product_ids = [item["productId"] for item in checkout_items]

    products = {
        product.id: product
        for product in Product.objects.select_for_update().filter(
            business=business,
            id__in=product_ids,
            is_active=True,
        )
    }

    if len(products) != len(product_ids):
        raise serializers.ValidationError(
            {
                "items": (
                    "One or more products are unavailable "
                    "in this business."
                )
            }
        )

    return products


def _prepare_lines(products, checkout_items):
    # Validates available stock and calculates server-side line totals.
    prepared_lines = []
    subtotal = Decimal("0.00")

    for item in checkout_items:
        product = products[item["productId"]]
        quantity = item["quantity"]
        unit_price = item["unitPrice"]
        available_stock = product.stock - product.reserved_stock

        if quantity > available_stock:
            raise serializers.ValidationError(
                {
                    "items": (
                        f"Only {available_stock} {product.unit}(s) "
                        f"of {product.name} are currently available."
                    )
                }
            )

        line_total = unit_price * quantity
        subtotal += line_total

        prepared_lines.append(
            {
                "product": product,
                "quantity": quantity,
                "unit_price": unit_price,
                "line_total": line_total,
            }
        )

    return prepared_lines, subtotal


def _next_document_numbers(business, issue_receipt):
    # Locks and advances the business-specific numbering sequence.
    sequence, _ = (
        DocumentSequence.objects.select_for_update().get_or_create(
            business=business,
        )
    )

    sale_number = f"SAL-{sequence.next_sale_number:05d}"
    invoice_number = (
        f"{business.invoice_prefix}-"
        f"{sequence.next_invoice_number:05d}"
    )
    receipt_number = None

    sequence.next_sale_number += 1
    sequence.next_invoice_number += 1

    if issue_receipt:
        receipt_number = (
            f"{business.receipt_prefix}-"
            f"{sequence.next_receipt_number:05d}"
        )
        sequence.next_receipt_number += 1

    sequence.save(
        update_fields=(
            "next_sale_number",
            "next_invoice_number",
            "next_receipt_number",
            "updated_at",
        )
    )

    return sale_number, invoice_number, receipt_number



def _next_receipt_number(business):
    # Locks and advances only the business receipt counter.
    sequence, _ = (
        DocumentSequence.objects.select_for_update().get_or_create(
            business=business,
        )
    )

    receipt_number = (
        f"{business.receipt_prefix}-"
        f"{sequence.next_receipt_number:05d}"
    )
    sequence.next_receipt_number += 1
    sequence.save(
        update_fields=(
            "next_receipt_number",
            "updated_at",
        )
    )

    return receipt_number


def _payment_method_for_completed_sale(data):
    # Resolves the method used for money received at checkout.
    if data["paymentMethod"] == Sale.PaymentMethod.CREDIT:
        return data.get("amountPaidMethod", "")

    return data["paymentMethod"]


def _uses_mobile_money_prompt(data):
    # Detects both full and part payments that require an external prompt.
    if data["paymentMethod"] == Sale.PaymentMethod.MOBILE_MONEY:
        return True

    return (
        data["paymentMethod"] == Sale.PaymentMethod.CREDIT
        and data.get("amountPaid", Decimal("0.00")) > Decimal("0.00")
        and data.get("amountPaidMethod") == Payment.Method.MOBILE_MONEY
    )


@transaction.atomic
def create_completed_sale(
    *,
    business,
    user,
    data,
    idempotency_key,
):
    # Creates a finalized cash, bank-transfer, or credit sale atomically.
    existing_sale = (
        Sale.objects.filter(
            business=business,
            idempotency_key=idempotency_key,
        )
        .select_related("business", "customer", "cashier")
        .prefetch_related("items", "payments")
        .first()
    )

    if existing_sale:
        return existing_sale, True

    if _uses_mobile_money_prompt(data):
        raise serializers.ValidationError(
            {
                "paymentMethod": (
                    "The real Mobile Money gateway is not connected yet. "
                    "No sale or payment prompt was created."
                )
            }
        )

    customer = _load_customer(
        business,
        data.get("customerId"),
    )
    products = _load_products(business, data["items"])
    lines, subtotal = _prepare_lines(products, data["items"])

    discount = data.get("discount", Decimal("0.00"))

    if discount > subtotal:
        raise serializers.ValidationError(
            {
                "discount": (
                    "Discount cannot be greater than the subtotal."
                )
            }
        )

    total = subtotal - discount
    payment_method = data["paymentMethod"]

    if payment_method in (
        Sale.PaymentMethod.CASH,
        Sale.PaymentMethod.BANK_TRANSFER,
    ):
        amount_paid = total
    else:
        amount_paid = data.get("amountPaid", Decimal("0.00"))

    if amount_paid > total:
        raise serializers.ValidationError(
            {
                "amountPaid": (
                    "Amount paid cannot be greater than the sale total."
                )
            }
        )

    outstanding_balance = total - amount_paid

    if outstanding_balance > Decimal("0.00") and not customer:
        raise serializers.ValidationError(
            {
                "customerId": (
                    "Select a customer before completing a credit sale."
                )
            }
        )

    issue_receipt = amount_paid > Decimal("0.00")
    sale_number, invoice_number, receipt_number = (
        _next_document_numbers(
            business,
            issue_receipt=issue_receipt,
        )
    )

    status_value = (
        Sale.Status.COMPLETED
        if outstanding_balance == Decimal("0.00")
        else Sale.Status.PARTIALLY_PAID
    )

    sale = Sale.objects.create(
        business=business,
        customer=customer,
        sale_number=sale_number,
        invoice_number=invoice_number,
        idempotency_key=idempotency_key,
        payment_method=payment_method,
        status=status_value,
        subtotal=subtotal,
        discount=discount,
        total=total,
        amount_paid=amount_paid,
        outstanding_balance=outstanding_balance,
        cashier=user,
        completed_at=timezone.now(),
    )

    for line in lines:
        product = line["product"]
        previous_stock = product.stock
        new_stock = previous_stock - line["quantity"]

        product.stock = new_stock
        product.save(
            update_fields=("stock", "updated_at")
        )

        SaleItem.objects.create(
            sale=sale,
            product=product,
            quantity=line["quantity"],
            unit_price=line["unit_price"],
            cost_price=product.cost_price,
            line_total=line["line_total"],
        )

        StockMovement.objects.create(
            business=business,
            product=product,
            movement_type=StockMovement.MovementType.SALE,
            quantity=-line["quantity"],
            previous_stock=previous_stock,
            new_stock=new_stock,
            reason=f"Sale {sale_number}",
            created_by=user,
        )

    if customer:
        customer.total_purchases += total
        customer.outstanding_balance += outstanding_balance
        customer.save(
            update_fields=(
                "total_purchases",
                "outstanding_balance",
                "updated_at",
            )
        )

    if issue_receipt:
        Payment.objects.create(
            business=business,
            sale=sale,
            customer=customer,
            payment_type=Payment.PaymentType.SALE_PAYMENT,
            method=_payment_method_for_completed_sale(data),
            status=Payment.Status.SUCCESSFUL,
            amount=amount_paid,
            receipt_number=receipt_number,
            note="Payment received when the sale was completed.",
            initiated_by=user,
            verified_at=timezone.now(),
        )

    sale = (
        Sale.objects.select_related(
            "business",
            "customer",
            "cashier",
        )
        .prefetch_related("items", "payments")
        .get(pk=sale.pk)
    )

    return sale, False



@transaction.atomic
def record_customer_debt_payment(
    *,
    business,
    customer_id,
    user,
    data,
    idempotency_key,
):
    # Applies one verified payment to one unpaid invoice atomically.
    existing_payment = (
        Payment.objects.filter(
            business=business,
            idempotency_key=idempotency_key,
        )
        .select_related(
            "business",
            "sale",
            "customer",
            "initiated_by",
        )
        .first()
    )

    if existing_payment:
        return existing_payment, True

    if data["paymentMethod"] == Payment.Method.MOBILE_MONEY:
        raise serializers.ValidationError(
            {
                "paymentMethod": (
                    "The real Mobile Money gateway is not connected yet. "
                    "No debt payment or prompt was created."
                )
            }
        )

    customer = get_object_or_404(
        Customer.objects.select_for_update(),
        pk=customer_id,
        business=business,
        is_active=True,
    )

    amount = data["amount"]

    if amount > customer.outstanding_balance:
        raise serializers.ValidationError(
            {
                "amount": (
                    "Payment cannot exceed the customer's "
                    "outstanding balance."
                )
            }
        )

    unpaid_sales = (
        Sale.objects.select_for_update()
        .filter(
            business=business,
            customer=customer,
            outstanding_balance__gt=Decimal("0.00"),
        )
        .order_by("created_at")
    )

    sale_id = data.get("saleId")

    if sale_id:
        unpaid_sales = unpaid_sales.filter(pk=sale_id)

    sale = unpaid_sales.first()

    if not sale:
        raise serializers.ValidationError(
            {
                "saleId": (
                    "No unpaid invoice was found for this customer."
                )
            }
        )

    if amount > sale.outstanding_balance:
        raise serializers.ValidationError(
            {
                "amount": (
                    "Payment cannot exceed the selected invoice "
                    f"balance of {sale.outstanding_balance}."
                )
            }
        )

    receipt_number = _next_receipt_number(business)

    sale.amount_paid += amount
    sale.outstanding_balance -= amount
    sale.status = (
        Sale.Status.COMPLETED
        if sale.outstanding_balance == Decimal("0.00")
        else Sale.Status.PARTIALLY_PAID
    )
    sale.save(
        update_fields=(
            "amount_paid",
            "outstanding_balance",
            "status",
            "updated_at",
        )
    )

    customer.outstanding_balance -= amount
    customer.save(
        update_fields=(
            "outstanding_balance",
            "updated_at",
        )
    )

    payment = Payment.objects.create(
        business=business,
        sale=sale,
        customer=customer,
        payment_type=Payment.PaymentType.DEBT_PAYMENT,
        method=data["paymentMethod"],
        status=Payment.Status.SUCCESSFUL,
        amount=amount,
        idempotency_key=idempotency_key,
        receipt_number=receipt_number,
        reference=data.get("reference", ""),
        note=data.get("note", ""),
        initiated_by=user,
        verified_at=timezone.now(),
    )

    payment = Payment.objects.select_related(
        "business",
        "sale",
        "customer",
        "initiated_by",
    ).get(pk=payment.pk)

    return payment, False
