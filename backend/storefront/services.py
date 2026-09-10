import hashlib
import json
from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound, ValidationError

from inventory.models import BranchInventory, Product
from .models import Storefront, StorefrontListing, StorefrontOrder, StorefrontOrderItem
from .serializers import PublicOrderCreateSerializer


MAX_ORDER_TOTAL = Decimal('999999999999.99')


def require_public_storefront(storefront):
    business = storefront.business
    branch = storefront.branch
    if (
        not storefront.is_published
        or business.status != business.Status.ACTIVE
        or not business.has_system_access
        or not branch.is_active
        or branch.business_id != business.id
    ):
        raise NotFound('This shop is currently unavailable.')
    return storefront


def order_request_fingerprint(data):
    payload = {
        'customerName': data['customerName'],
        'customerPhone': data['customerPhone'],
        'customerNote': data['customerNote'],
        'items': sorted(
            [(str(item['productId']), item['quantity']) for item in data['items']]
        ),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


@transaction.atomic
def create_pending_order(*, shop_slug, data):
    serializer = PublicOrderCreateSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    storefront = get_object_or_404(
        Storefront.objects.select_for_update().select_related('business', 'branch'),
        business__slug=shop_slug,
    )
    require_public_storefront(storefront)
    fingerprint = order_request_fingerprint(data)
    existing = StorefrontOrder.objects.filter(
        storefront=storefront, idempotency_key=data['idempotencyKey'],
    ).first()
    if existing:
        if existing.request_fingerprint != fingerprint:
            raise ValidationError({
                'idempotencyKey': 'This submission key was already used for a different order.',
            })
        return existing, True

    product_ids = [item['productId'] for item in data['items']]
    published_ids = set(StorefrontListing.objects.filter(
        storefront=storefront, is_published=True,
        product_id__in=product_ids, product__business=storefront.business,
        product__is_active=True,
    ).values_list('product_id', flat=True))
    if published_ids != set(product_ids):
        raise ValidationError({'items': 'One or more products are unavailable in this shop.'})

    products = {product.id: product for product in Product.objects.select_for_update().filter(
        business=storefront.business, id__in=product_ids, is_active=True,
    ).order_by('id')}
    if len(products) != len(product_ids):
        raise ValidationError({'items': 'One or more products are unavailable in this shop.'})
    inventory = {row.product_id: row for row in BranchInventory.objects.select_for_update().filter(
        branch=storefront.branch, product_id__in=product_ids,
    ).order_by('product_id')}

    total = Decimal('0.00')
    lines = []
    for item in data['items']:
        product = products[item['productId']]
        row = inventory.get(product.id)
        available = row.available_stock if row is not None else 0
        if item['quantity'] > available:
            raise ValidationError({'items': 'The requested quantity of ' + product.name + ' is currently unavailable.'})
        price = product.selling_price
        if price < 0:
            raise ValidationError({'items': 'A product price is currently unavailable.'})
        line_total = price * item['quantity']
        total += line_total
        if total > MAX_ORDER_TOTAL:
            raise ValidationError({'items': 'The order total exceeds the supported limit.'})
        lines.append((product, item['quantity'], price, line_total))

    order = StorefrontOrder.objects.create(
        storefront=storefront, branch=storefront.branch,
        idempotency_key=data['idempotencyKey'], request_fingerprint=fingerprint,
        customer_name=data['customerName'], customer_phone=data['customerPhone'],
        customer_note=data['customerNote'], currency='GHS', total=total,
    )
    for product, quantity, price, line_total in lines:
        StorefrontOrderItem.objects.create(
            order=order, product=product, product_name=product.name,
            sku=product.sku, unit=product.unit, quantity=quantity,
            unit_price=price, line_total=line_total,
        )
    return order, False
