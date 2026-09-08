import uuid
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from businesses.access import get_business_and_role_for_user
from businesses.branch_access import ensure_main_branch
from businesses.models import Branch, BusinessMembership
from inventory.models import Product
from inventory.restock_models import RestockPayment, RestockPurchase, Supplier
from inventory.restock_service import create_restock

from .models import (
    SupplierPurchaseOrder,
    SupplierPurchaseOrderItem,
    SupplierPurchaseOrderReceipt,
)


def _business(request, business_id):
    business, role = get_business_and_role_for_user(
        user=request.user,
        business_id=business_id,
    )
    if role not in {
        BusinessMembership.Role.OWNER,
        BusinessMembership.Role.MANAGER,
        BusinessMembership.Role.INVENTORY_CLERK,
    }:
        raise PermissionDenied(
            "Your role does not allow supplier purchase-order access."
        )
    return business


class SupplierPurchaseOrderItemInputSerializer(serializers.Serializer):
    productId = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)
    unitCost = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.00"),
    )


class SupplierPurchaseOrderCreateSerializer(serializers.Serializer):
    branchId = serializers.UUIDField(required=False)
    supplierId = serializers.UUIDField()
    supplierReference = serializers.CharField(
        max_length=120,
        required=False,
        allow_blank=True,
    )
    orderDate = serializers.DateField(
        required=False,
        default=timezone.localdate,
    )
    expectedDate = serializers.DateField(
        required=False,
        allow_null=True,
    )
    notes = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
    )
    items = SupplierPurchaseOrderItemInputSerializer(
        many=True,
        allow_empty=False,
    )

    def validate_items(self, items):
        ids = [str(item["productId"]) for item in items]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError(
                "Each product can appear only once in a supplier order."
            )
        return items


class SupplierPurchaseOrderReceiveItemSerializer(serializers.Serializer):
    purchaseOrderItemId = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1)


class SupplierPurchaseOrderReceiveSerializer(serializers.Serializer):
    idempotencyKey = serializers.CharField(max_length=128)
    purchaseDate = serializers.DateField(
        required=False,
        default=timezone.localdate,
    )
    initialPayment = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.00"),
        required=False,
        default=Decimal("0.00"),
    )
    paymentMethod = serializers.ChoiceField(
        choices=RestockPayment.Method.choices,
        required=False,
        default=RestockPayment.Method.CASH,
    )
    items = SupplierPurchaseOrderReceiveItemSerializer(
        many=True,
        allow_empty=False,
    )

    def validate_items(self, items):
        ids = [item["purchaseOrderItemId"] for item in items]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError(
                "Each purchase-order item can appear only once per receipt."
            )
        return items


def _po_number():
    return f"SPO-{uuid.uuid4().hex[:12].upper()}"


@transaction.atomic
def create_supplier_purchase_order(*, business, user, data):
    branch_id = data.get("branchId")
    if branch_id:
        branch = Branch.objects.filter(
            id=branch_id,
            business=business,
            is_active=True,
        ).first()
        if not branch:
            raise serializers.ValidationError(
                {"branchId": "Select an active branch for this business."}
            )
    else:
        branch = ensure_main_branch(business=business, created_by=user)

    supplier = Supplier.objects.filter(
        id=data["supplierId"],
        business=business,
        is_active=True,
    ).first()
    if not supplier:
        raise serializers.ValidationError(
            {"supplierId": "Select an active supplier for this business."}
        )

    product_ids = [item["productId"] for item in data["items"]]
    products = {
        str(product.id): product
        for product in Product.objects.filter(
            business=business,
            is_active=True,
            id__in=product_ids,
        )
    }
    if any(str(product_id) not in products for product_id in product_ids):
        raise serializers.ValidationError(
            {"items": "One or more products do not belong to this business."}
        )

    order = SupplierPurchaseOrder.objects.create(
        business=business,
        branch=branch,
        supplier=supplier,
        po_number=_po_number(),
        supplier_reference=data.get("supplierReference", "").strip(),
        order_date=data["orderDate"],
        expected_date=data.get("expectedDate"),
        notes=data.get("notes", "").strip(),
        created_by=user,
    )
    for item in data["items"]:
        product = products[str(item["productId"])]
        SupplierPurchaseOrderItem.objects.create(
            purchase_order=order,
            product=product,
            product_name=product.name,
            sku=product.sku,
            unit=product.unit,
            quantity_ordered=item["quantity"],
            unit_cost=item["unitCost"],
        )
    return order


@transaction.atomic
def issue_supplier_purchase_order(*, business, purchase_order_id):
    order = SupplierPurchaseOrder.objects.select_for_update().filter(
        id=purchase_order_id,
        business=business,
    ).first()
    if not order:
        raise serializers.ValidationError(
            {"purchaseOrder": "Supplier purchase order not found."}
        )
    if order.status != SupplierPurchaseOrder.Status.DRAFT:
        raise serializers.ValidationError(
            {"status": "Only draft supplier orders can be issued."}
        )
    order.status = SupplierPurchaseOrder.Status.ISSUED
    order.issued_at = timezone.now()
    order.save(update_fields=("status", "issued_at", "updated_at"))
    return order


@transaction.atomic
def receive_supplier_purchase_order(
    *,
    business,
    user,
    purchase_order_id,
    data,
):
    order = (
        SupplierPurchaseOrder.objects.select_for_update()
        .select_related("branch", "supplier")
        .filter(id=purchase_order_id, business=business)
        .first()
    )
    if not order:
        raise serializers.ValidationError(
            {"purchaseOrder": "Supplier purchase order not found."}
        )

    key = data["idempotencyKey"].strip()
    existing_receipt = SupplierPurchaseOrderReceipt.objects.filter(
        purchase_order=order,
        idempotency_key=key,
    ).first()
    if existing_receipt:
        purchase = RestockPurchase.objects.get(
            id=existing_receipt.restock_purchase_id,
            business=business,
        )
        return order, purchase, True

    if order.status not in {
        SupplierPurchaseOrder.Status.ISSUED,
        SupplierPurchaseOrder.Status.PARTIALLY_RECEIVED,
    }:
        raise serializers.ValidationError(
            {
                "status": (
                    "Only issued or partially received supplier orders "
                    "can receive stock."
                )
            }
        )

    locked_items = {
        item.id: item
        for item in SupplierPurchaseOrderItem.objects.select_for_update().filter(
            purchase_order=order
        )
    }

    restock_items = []
    for received in data["items"]:
        item = locked_items.get(received["purchaseOrderItemId"])
        if not item:
            raise serializers.ValidationError(
                {
                    "items": (
                        "One or more receipt items do not belong to "
                        "this supplier order."
                    )
                }
            )
        remaining = item.quantity_ordered - item.quantity_received
        if received["quantity"] > remaining:
            raise serializers.ValidationError(
                {
                    "items": (
                        f"Cannot receive more than the remaining quantity "
                        f"for {item.product_name}."
                    )
                }
            )
        restock_items.append(
            {
                "productId": item.product_id,
                "quantity": received["quantity"],
                "unitCost": item.unit_cost,
            }
        )

    purchase = create_restock(
        business=business,
        user=user,
        branch=order.branch,
        data={
            "supplierId": order.supplier_id,
            "supplierReference": order.supplier_reference or order.po_number,
            "purchaseDate": data["purchaseDate"],
            "initialPayment": data.get("initialPayment", Decimal("0.00")),
            "paymentMethod": data.get(
                "paymentMethod",
                RestockPayment.Method.CASH,
            ),
            "items": restock_items,
        },
    )

    for received in data["items"]:
        item = locked_items[received["purchaseOrderItemId"]]
        item.quantity_received += received["quantity"]
        item.save(update_fields=("quantity_received",))

    all_received = all(
        item.quantity_received >= item.quantity_ordered
        for item in locked_items.values()
    )
    order.status = (
        SupplierPurchaseOrder.Status.RECEIVED
        if all_received
        else SupplierPurchaseOrder.Status.PARTIALLY_RECEIVED
    )
    order.save(update_fields=("status", "updated_at"))

    SupplierPurchaseOrderReceipt.objects.create(
        purchase_order=order,
        idempotency_key=key,
        restock_purchase_id=str(purchase.id),
        received_by=user,
    )
    return order, purchase, False


def purchase_order_payload(order):
    items = list(order.items.all())
    total = sum(
        (
            Decimal(item.quantity_ordered) * item.unit_cost
            for item in items
        ),
        Decimal("0.00"),
    )
    return {
        "id": str(order.id),
        "poNumber": order.po_number,
        "status": order.status,
        "branch": {
            "id": str(order.branch_id),
            "name": order.branch.name,
            "code": order.branch.code,
        },
        "supplier": {
            "id": str(order.supplier_id),
            "name": order.supplier.name,
        },
        "supplierReference": order.supplier_reference,
        "orderDate": order.order_date,
        "expectedDate": order.expected_date,
        "notes": order.notes,
        "total": f"{total:.2f}",
        "issuedAt": order.issued_at,
        "createdAt": order.created_at,
        "items": [
            {
                "id": item.id,
                "productId": str(item.product_id),
                "productName": item.product_name,
                "sku": item.sku,
                "unit": item.unit,
                "quantityOrdered": item.quantity_ordered,
                "quantityReceived": item.quantity_received,
                "quantityRemaining": max(
                    0,
                    item.quantity_ordered - item.quantity_received,
                ),
                "unitCost": f"{item.unit_cost:.2f}",
            }
            for item in items
        ],
    }


def _fresh_order(order_id):
    return (
        SupplierPurchaseOrder.objects.select_related("branch", "supplier")
        .prefetch_related("items")
        .get(id=order_id)
    )


class SupplierOrderAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "integration_admin"


class SupplierPurchaseOrderCollectionAPIView(SupplierOrderAPIView):
    def get(self, request, business_id):
        business = _business(request, business_id)
        rows = (
            SupplierPurchaseOrder.objects.filter(business=business)
            .select_related("branch", "supplier")
            .prefetch_related("items")
            .order_by("-order_date", "-created_at")[:200]
        )
        return Response(
            {"purchaseOrders": [purchase_order_payload(row) for row in rows]}
        )

    def post(self, request, business_id):
        business = _business(request, business_id)
        serializer = SupplierPurchaseOrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = create_supplier_purchase_order(
            business=business,
            user=request.user,
            data=serializer.validated_data,
        )
        return Response(
            purchase_order_payload(_fresh_order(order.id)),
            status=status.HTTP_201_CREATED,
        )


class SupplierPurchaseOrderIssueAPIView(SupplierOrderAPIView):
    def post(self, request, business_id, purchase_order_id):
        business = _business(request, business_id)
        order = issue_supplier_purchase_order(
            business=business,
            purchase_order_id=purchase_order_id,
        )
        return Response(purchase_order_payload(_fresh_order(order.id)))


class SupplierPurchaseOrderReceiveAPIView(SupplierOrderAPIView):
    def post(self, request, business_id, purchase_order_id):
        business = _business(request, business_id)
        serializer = SupplierPurchaseOrderReceiveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order, purchase, replay = receive_supplier_purchase_order(
            business=business,
            user=request.user,
            purchase_order_id=purchase_order_id,
            data=serializer.validated_data,
        )
        return Response(
            {
                "purchaseOrder": purchase_order_payload(_fresh_order(order.id)),
                "restockPurchaseId": str(purchase.id),
                "restockPurchaseNumber": purchase.purchase_number,
                "idempotentReplay": replay,
            }
        )
