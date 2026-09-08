import hashlib
import json
from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from inventory.models import Product

from integrations.models import (
    CommerceConnection,
    CommerceExternalReference,
    ExternalCommerceOrder,
    ExternalCommerceOrderItem,
)


def _money_text(value):
    return f"{Decimal(value or 0):.2f}"


def _source_hash(data):
    normalized = {
        "externalOrderId": str(data["externalOrderId"]),
        "externalOrderNumber": str(data.get("externalOrderNumber", "")),
        "paymentStatus": str(data.get("paymentStatus", "")),
        "currency": str(data.get("currency", "GHS")).upper(),
        "customerName": str(data.get("customerName", "")),
        "customerEmail": str(data.get("customerEmail", "")),
        "customerPhone": str(data.get("customerPhone", "")),
        "subtotal": _money_text(data["subtotal"]),
        "discount": _money_text(data.get("discount", 0)),
        "shippingTotal": _money_text(data.get("shippingTotal", 0)),
        "total": _money_text(data["total"]),
        "items": [
            {
                "externalItemId": str(item["externalItemId"]),
                "externalProductId": str(item.get("externalProductId", "")),
                "name": str(item["name"]),
                "sku": str(item.get("sku", "")),
                "quantity": int(item["quantity"]),
                "unitPrice": _money_text(item["unitPrice"]),
            }
            for item in data["items"]
        ],
    }
    raw = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _mapped_product(*, business, connection, item):
    external_product_id = str(
        item.get("externalProductId", "")
    ).strip()
    if external_product_id:
        reference = CommerceExternalReference.objects.filter(
            connection=connection,
            entity_type="product",
            external_id=external_product_id,
        ).first()
        if reference:
            return Product.objects.filter(
                business=business,
                id=reference.stockflow_id,
                is_active=True,
            ).first()

    sku = str(item.get("sku", "")).strip()
    if sku:
        matches = list(
            Product.objects.filter(
                business=business,
                sku__iexact=sku,
                is_active=True,
            )[:2]
        )
        if len(matches) == 1:
            return matches[0]
    return None


@transaction.atomic
def upsert_product_mapping(
    *,
    business,
    connection,
    external_product_id,
    product_id,
):
    product = Product.objects.filter(
        business=business,
        id=product_id,
        is_active=True,
    ).first()
    if not product:
        raise serializers.ValidationError(
            {"productId": "Select an active product from this business."}
        )

    reference = CommerceExternalReference.objects.select_for_update().filter(
        connection=connection,
        entity_type="product",
        external_id=external_product_id,
    ).first()
    if reference:
        reference.stockflow_id = str(product.id)
        reference.save(update_fields=("stockflow_id", "synced_at"))
        return reference

    return CommerceExternalReference.objects.create(
        connection=connection,
        entity_type="product",
        stockflow_id=str(product.id),
        external_id=external_product_id,
    )


@transaction.atomic
def stage_external_order(*, business, user, data):
    connection = CommerceConnection.objects.select_for_update().filter(
        business=business,
        id=data["connectionId"],
    ).first()
    if not connection:
        raise serializers.ValidationError(
            {"connectionId": "Commerce connection not found."}
        )

    digest = _source_hash(data)
    existing = ExternalCommerceOrder.objects.select_for_update().filter(
        connection=connection,
        external_order_id=data["externalOrderId"],
    ).first()
    if existing:
        if existing.source_hash != digest:
            raise serializers.ValidationError(
                {
                    "externalOrderId": (
                        "This external order ID already exists with "
                        "different order data."
                    )
                }
            )
        return existing, True

    order = ExternalCommerceOrder.objects.create(
        business=business,
        connection=connection,
        external_order_id=data["externalOrderId"],
        external_order_number=data.get("externalOrderNumber", "").strip(),
        payment_status=data.get(
            "paymentStatus",
            ExternalCommerceOrder.PaymentStatus.UNKNOWN,
        ),
        currency=data.get("currency", "GHS").strip().upper(),
        customer_name=data.get("customerName", "").strip(),
        customer_email=data.get("customerEmail", "").strip(),
        customer_phone=data.get("customerPhone", "").strip(),
        subtotal=data["subtotal"],
        discount=data.get("discount", Decimal("0.00")),
        shipping_total=data.get("shippingTotal", Decimal("0.00")),
        total=data["total"],
        source_hash=digest,
        source_summary={
            "provider": connection.provider,
            "itemCount": len(data["items"]),
            "externalOrderNumber": data.get("externalOrderNumber", ""),
        },
        staged_by=user,
    )

    mapped_count = 0
    for item in data["items"]:
        product = _mapped_product(
            business=business,
            connection=connection,
            item=item,
        )
        if product:
            mapped_count += 1
        ExternalCommerceOrderItem.objects.create(
            order=order,
            external_item_id=item["externalItemId"],
            external_product_id=item.get("externalProductId", "").strip(),
            name=item["name"].strip(),
            sku=item.get("sku", "").strip(),
            quantity=item["quantity"],
            unit_price=item["unitPrice"],
            product=product,
        )

    order.status = (
        ExternalCommerceOrder.Status.READY
        if mapped_count == len(data["items"])
        else ExternalCommerceOrder.Status.BLOCKED
    )
    order.save(update_fields=("status", "updated_at"))
    return order, False


def order_payload(order):
    return {
        "id": str(order.id),
        "connectionId": str(order.connection_id),
        "provider": order.connection.provider,
        "externalOrderId": order.external_order_id,
        "externalOrderNumber": order.external_order_number,
        "status": order.status,
        "paymentStatus": order.payment_status,
        "currency": order.currency,
        "customer": {
            "name": order.customer_name,
            "email": order.customer_email,
            "phone": order.customer_phone,
        },
        "subtotal": _money_text(order.subtotal),
        "discount": _money_text(order.discount),
        "shippingTotal": _money_text(order.shipping_total),
        "total": _money_text(order.total),
        "stagedAt": order.staged_at,
        "items": [
            {
                "id": str(item.id),
                "externalItemId": item.external_item_id,
                "externalProductId": item.external_product_id,
                "name": item.name,
                "sku": item.sku,
                "quantity": item.quantity,
                "unitPrice": _money_text(item.unit_price),
                "productId": str(item.product_id) if item.product_id else None,
                "mappingStatus": "mapped" if item.product_id else "unmapped",
            }
            for item in order.items.all()
        ],
    }
