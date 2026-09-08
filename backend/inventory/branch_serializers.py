from rest_framework import serializers

from .models import BranchInventory, BranchTransfer, BranchTransferItem


class BranchInventorySerializer(serializers.ModelSerializer):
    branchId = serializers.UUIDField(source="branch_id", read_only=True)
    branchName = serializers.CharField(source="branch.name", read_only=True)
    productId = serializers.UUIDField(source="product_id", read_only=True)
    productName = serializers.CharField(source="product.name", read_only=True)
    sku = serializers.CharField(source="product.sku", read_only=True)
    unit = serializers.CharField(source="product.unit", read_only=True)
    reservedStock = serializers.IntegerField(source="reserved_stock", read_only=True)
    availableStock = serializers.IntegerField(source="available_stock", read_only=True)
    lowStockLevel = serializers.IntegerField(source="low_stock_level", read_only=True)

    class Meta:
        model = BranchInventory
        fields = (
            "id", "branchId", "branchName", "productId", "productName", "sku",
            "unit", "stock", "reservedStock", "availableStock", "lowStockLevel",
        )


class BranchTransferItemInputSerializer(serializers.Serializer):
    productId = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)


class BranchTransferCreateSerializer(serializers.Serializer):
    sourceBranchId = serializers.UUIDField()
    destinationBranchId = serializers.UUIDField()
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True)
    items = BranchTransferItemInputSerializer(many=True, allow_empty=False)

    def validate(self, attrs):
        if attrs["sourceBranchId"] == attrs["destinationBranchId"]:
            raise serializers.ValidationError(
                {"destinationBranchId": "Choose a different destination branch."}
            )
        ids = [item["productId"] for item in attrs["items"]]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError(
                {"items": "Each product can appear only once in a branch transfer."}
            )
        return attrs


class BranchTransferItemSerializer(serializers.ModelSerializer):
    productId = serializers.UUIDField(source="product_id", read_only=True)
    productName = serializers.CharField(source="product_name", read_only=True)

    class Meta:
        model = BranchTransferItem
        fields = ("id", "productId", "productName", "sku", "unit", "quantity")


class BranchTransferSerializer(serializers.ModelSerializer):
    sourceBranchId = serializers.UUIDField(source="source_branch_id", read_only=True)
    sourceBranchName = serializers.CharField(source="source_branch.name", read_only=True)
    destinationBranchId = serializers.UUIDField(source="destination_branch_id", read_only=True)
    destinationBranchName = serializers.CharField(source="destination_branch.name", read_only=True)
    transferNumber = serializers.CharField(source="transfer_number", read_only=True)
    createdBy = serializers.CharField(source="created_by_name", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    completedAt = serializers.DateTimeField(source="completed_at", read_only=True)
    items = BranchTransferItemSerializer(many=True, read_only=True)

    class Meta:
        model = BranchTransfer
        fields = (
            "id", "sourceBranchId", "sourceBranchName", "destinationBranchId",
            "destinationBranchName", "transferNumber", "status", "reason",
            "createdBy", "createdAt", "completedAt", "items",
        )
