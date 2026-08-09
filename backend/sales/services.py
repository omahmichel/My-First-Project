from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers

from businesses.models import BusinessPaymentAccount

from customers.models import Customer
from inventory.models import Product, StockMovement
from .models import (
    DebtOverdueCharge,
    DebtPaymentAllocation,
    DocumentSequence,
    Payment,
    Sale,
    SaleItem,
)


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


def _resolve_bank_receiving_account(*, business, data):
    # Authoritatively validates the selected account inside the transaction boundary.
    account_id = data.get("receivingAccountId")
    if not account_id:
        raise serializers.ValidationError(
            {
                "receivingAccountId": (
                    "Select the business bank account that received "
                    "this transfer."
                )
            }
        )

    account = (
        BusinessPaymentAccount.objects.filter(
            id=account_id,
            business=business,
            account_type=BusinessPaymentAccount.AccountType.BANK,
            is_active=True,
        )
        .first()
    )
    if account is None:
        raise serializers.ValidationError(
            {
                "receivingAccountId": (
                    "The selected receiving account is not an active "
                    "bank account for this business."
                )
            }
        )

    return account


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

    payment_method_for_receipt = _payment_method_for_completed_sale(data)
    receiving_account = None
    if (
        amount_paid > Decimal("0.00")
        and payment_method_for_receipt == Payment.Method.BANK_TRANSFER
    ):
        receiving_account = _resolve_bank_receiving_account(
            business=business,
            data=data,
        )

    if outstanding_balance > Decimal("0.00") and not customer:
        raise serializers.ValidationError(
            {
                "customerId": (
                    "Select a customer before completing a credit sale."
                )
            }
        )

    # Uses the trusted server-calculated balance for due-date rules.
    debt_due_date = data.get("debtDueDate")

    if (
        outstanding_balance > Decimal("0.00")
        and not debt_due_date
    ):
        raise serializers.ValidationError(
            {
                "debtDueDate": (
                    "Select the date when this debt is due."
                )
            }
        )

    if outstanding_balance == Decimal("0.00"):
        debt_due_date = None

    debt_principal_at_due = (
        outstanding_balance
        if outstanding_balance > Decimal("0.00")
        else Decimal("0.00")
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
        debt_due_date=debt_due_date,
        debt_principal_at_due=debt_principal_at_due,
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
            method=payment_method_for_receipt,
            status=Payment.Status.SUCCESSFUL,
            amount=amount_paid,
            receipt_number=receipt_number,
            reference=data.get("reference", ""),
            note=(
                data.get("note", "")
                or "Payment received when the sale was completed."
            ),
            receiving_account_id_snapshot=(
                receiving_account.id if receiving_account else None
            ),
            receiving_account_type=(
                receiving_account.account_type if receiving_account else ""
            ),
            receiving_account_display_name=(
                receiving_account.display_name if receiving_account else ""
            ),
            receiving_account_bank_name=(
                receiving_account.bank_name if receiving_account else ""
            ),
            receiving_account_account_name=(
                receiving_account.account_name if receiving_account else ""
            ),
            receiving_account_network=(
                receiving_account.network if receiving_account else ""
            ),
            receiving_account_masked_number=(
                receiving_account.masked_number if receiving_account else ""
            ),
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




OVERDUE_TIER_PERCENTAGES = (5, 10, 15, 20, 25, 30)


def overdue_tier_percentage_for_days(days_overdue):
    # Maps overdue age to the capped non-compounding percentage.
    if days_overdue <= 0:
        return 0

    tier = (((days_overdue - 1) // 30) + 1) * 5
    return min(tier, DebtOverdueCharge.Tier.THIRTY)


def ensure_current_overdue_charges(*, sale, as_of_date=None):
    # Creates every crossed tier once using the original due-date principal.
    if (
        not sale.debt_due_date
        or sale.debt_principal_at_due <= Decimal("0.00")
        or sale.outstanding_balance <= Decimal("0.00")
        or not sale.customer_id
    ):
        return []

    current_date = as_of_date or timezone.localdate()
    days_overdue = (current_date - sale.debt_due_date).days
    target_tier = overdue_tier_percentage_for_days(days_overdue)

    if target_tier == 0:
        return []

    existing_tiers = set(
        DebtOverdueCharge.objects.filter(
            sale=sale,
        ).values_list(
            "tier_percentage",
            flat=True,
        )
    )
    principal_base = sale.debt_principal_at_due
    created_charges = []
    previous_total = Decimal("0.00")

    for tier_percentage in OVERDUE_TIER_PERCENTAGES:
        if tier_percentage > target_tier:
            break

        total_charge_required = (
            principal_base
            * Decimal(tier_percentage)
            / Decimal("100")
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
        incremental_amount = (
            total_charge_required - previous_total
        )

        if tier_percentage not in existing_tiers:
            created_charges.append(
                DebtOverdueCharge.objects.create(
                    business=sale.business,
                    customer=sale.customer,
                    sale=sale,
                    tier_percentage=tier_percentage,
                    principal_base=principal_base,
                    total_charge_required=total_charge_required,
                    incremental_amount=incremental_amount,
                )
            )

        previous_total = total_charge_required

    return created_charges


def debt_snapshot(*, sale, as_of_date=None):
    # Returns the current principal, overdue charge, and total debt payable.
    current_date = as_of_date or timezone.localdate()

    if (
        sale.debt_due_date
        and sale.outstanding_balance > Decimal("0.00")
    ):
        ensure_current_overdue_charges(
            sale=sale,
            as_of_date=current_date,
        )

    total_charge_required = sum(
        DebtOverdueCharge.objects.filter(
            sale=sale,
        ).values_list(
            "incremental_amount",
            flat=True,
        ),
        Decimal("0.00"),
    )
    total_charge_paid = sum(
        DebtPaymentAllocation.objects.filter(
            sale=sale,
        ).values_list(
            "overdue_charge_paid",
            flat=True,
        ),
        Decimal("0.00"),
    )
    unpaid_charge = max(
        Decimal("0.00"),
        total_charge_required - total_charge_paid,
    )
    days_overdue = (
        max(0, (current_date - sale.debt_due_date).days)
        if sale.debt_due_date
        else 0
    )

    return {
        "principal_balance": sale.outstanding_balance,
        "overdue_charge": unpaid_charge,
        "total_debt_payable": (
            sale.outstanding_balance + unpaid_charge
        ),
        "days_overdue": days_overdue,
        "overdue_percentage": overdue_tier_percentage_for_days(
            days_overdue,
        ),
    }


def debt_payment_split(*, sale, amount):
    # Applies any current tier before allocating charges ahead of principal.
    snapshot = debt_snapshot(sale=sale)
    unpaid_charge = snapshot["overdue_charge"]
    overdue_charge_paid = min(amount, unpaid_charge)
    principal_paid = amount - overdue_charge_paid

    return {
        "unpaid_charge": unpaid_charge,
        "total_due": snapshot["total_debt_payable"],
        "overdue_charge_paid": overdue_charge_paid,
        "principal_paid": principal_paid,
    }


def _apply_debt_payment_allocation_locked(
    *,
    payment,
    sale,
    customer,
):
    # Applies one successful payment to charges first, then principal.
    split = debt_payment_split(
        sale=sale,
        amount=payment.amount,
    )

    if payment.amount > split["total_due"]:
        raise serializers.ValidationError(
            {
                "amount": (
                    "Payment cannot exceed the selected invoice "
                    f"total due of {split['total_due']}."
                )
            }
        )

    if split["principal_paid"] > customer.outstanding_balance:
        raise serializers.ValidationError(
            {
                "amount": (
                    "The customer principal balance changed before "
                    "this payment was applied."
                )
            }
        )

    sale.amount_paid += split["principal_paid"]
    sale.outstanding_balance -= split["principal_paid"]
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

    customer.outstanding_balance -= split["principal_paid"]
    customer.save(
        update_fields=(
            "outstanding_balance",
            "updated_at",
        )
    )

    return DebtPaymentAllocation.objects.create(
        payment=payment,
        business=payment.business,
        customer=customer,
        sale=sale,
        amount_received=payment.amount,
        overdue_charge_paid=split["overdue_charge_paid"],
        principal_paid=split["principal_paid"],
    )


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

    split = debt_payment_split(
        sale=sale,
        amount=amount,
    )

    if amount > split["total_due"]:
        raise serializers.ValidationError(
            {
                "amount": (
                    "Payment cannot exceed the selected invoice "
                    f"total due of {split['total_due']}."
                )
            }
        )

    receipt_number = _next_receipt_number(business)

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

    _apply_debt_payment_allocation_locked(
        payment=payment,
        sale=sale,
        customer=customer,
    )

    payment = Payment.objects.select_related(
        "business",
        "sale",
        "customer",
        "initiated_by",
    ).get(pk=payment.pk)

    return payment, False
