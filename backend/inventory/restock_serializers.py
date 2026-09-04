from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from .restock_models import (
    RestockItem,
    RestockPayment,
    RestockPurchase,
    Supplier,
)


class SupplierSerializer(serializers.ModelSerializer):
    businessId = serializers.UUIDField(source="business_id", read_only=True)
    isActive = serializers.BooleanField(source="is_active", required=False)
    totalPurchased = serializers.SerializerMethodField()
    amountPaid = serializers.SerializerMethodField()
    outstandingBalance = serializers.SerializerMethodField()
    purchaseCount = serializers.SerializerMethodField()

    class Meta:
        model = Supplier
        fields = (
            "id", "businessId", "name", "phone", "email", "address", "notes",
            "isActive", "totalPurchased", "amountPaid",
            "outstandingBalance", "purchaseCount",
        )
        read_only_fields = (
            "id", "businessId", "totalPurchased", "amountPaid",
            "outstandingBalance", "purchaseCount",
        )

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("A supplier name is required.")
        return value

    def _purchases(self, obj):
        return list(obj.restock_purchases.all())

    def get_totalPurchased(self, obj):
        total = sum(
            (item.total_amount for item in self._purchases(obj)),
            Decimal("0.00"),
        )
        return f"{total:.2f}"

    def get_amountPaid(self, obj):
        total = sum(
            (item.amount_paid for item in self._purchases(obj)),
            Decimal("0.00"),
        )
        return f"{total:.2f}"

    def get_outstandingBalance(self, obj):
        return f"{max(Decimal('0.00'), Decimal(self.get_totalPurchased(obj)) - Decimal(self.get_amountPaid(obj))):.2f}"

    def get_purchaseCount(self, obj):
        return len(self._purchases(obj))


class RestockItemReadSerializer(serializers.ModelSerializer):
    productId = serializers.UUIDField(source="product_id", read_only=True)
    productName = serializers.CharField(source="product_name", read_only=True)
    unitCost = serializers.DecimalField(
        source="unit_cost", max_digits=14, decimal_places=2, read_only=True
    )
    lineTotal = serializers.DecimalField(
        source="line_total", max_digits=14, decimal_places=2, read_only=True
    )

    class Meta:
        model = RestockItem
        fields = (
            "id", "productId", "productName", "sku", "unit",
            "quantity", "unitCost", "lineTotal",
        )


class RestockPurchaseSerializer(serializers.ModelSerializer):
    supplierId = serializers.UUIDField(source="supplier_id", read_only=True)
    supplierName = serializers.CharField(source="supplier.name", read_only=True)
    purchaseNumber = serializers.CharField(
        source="purchase_number", read_only=True
    )
    supplierReference = serializers.CharField(
        source="supplier_reference", read_only=True
    )
    purchaseDate = serializers.DateField(source="purchase_date", read_only=True)
    totalAmount = serializers.DecimalField(
        source="total_amount", max_digits=14, decimal_places=2, read_only=True
    )
    amountPaid = serializers.DecimalField(
        source="amount_paid", max_digits=14, decimal_places=2, read_only=True
    )
    outstandingBalance = serializers.SerializerMethodField()
    paymentStatus = serializers.CharField(
        source="payment_status", read_only=True
    )
    createdBy = serializers.CharField(
        source="created_by_name", read_only=True
    )
    items = RestockItemReadSerializer(many=True, read_only=True)

    class Meta:
        model = RestockPurchase
        fields = (
            "id", "supplierId", "supplierName", "purchaseNumber",
            "supplierReference", "purchaseDate", "totalAmount",
            "amountPaid", "outstandingBalance", "paymentStatus",
            "createdBy", "items",
        )

    def get_outstandingBalance(self, obj):
        return f"{obj.outstanding_balance:.2f}"


class RestockItemInputSerializer(serializers.Serializer):
    productId = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)
    unitCost = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=0
    )


class RestockCreateSerializer(serializers.Serializer):
    supplierId = serializers.UUIDField()
    supplierReference = serializers.CharField(
        max_length=120, required=False, allow_blank=True
    )
    purchaseDate = serializers.DateField(
        required=False, default=timezone.localdate
    )
    initialPayment = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=0,
        required=False,
        default=Decimal("0.00"),
    )
    paymentMethod = serializers.ChoiceField(
        choices=RestockPayment.Method.choices,
        required=False,
        default=RestockPayment.Method.CASH,
    )
    items = RestockItemInputSerializer(many=True, allow_empty=False)

    def validate_items(self, items):
        ids = [str(item["productId"]) for item in items]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError(
                "Each product can appear only once in a restock."
            )
        return items


class RestockPaymentCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("0.01")
    )
    method = serializers.ChoiceField(
        choices=RestockPayment.Method.choices,
        required=False,
        default=RestockPayment.Method.CASH,
    )
    note = serializers.CharField(
        max_length=255, required=False, allow_blank=True
    )
