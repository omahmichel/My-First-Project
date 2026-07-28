from django.db import transaction
from rest_framework import serializers

from businesses.models import Business
from .models import Product, StockMovement


class ProductSerializer(serializers.ModelSerializer):
    # Uses the exact camelCase field names already expected by React.

    businessId = serializers.UUIDField(
        source="business_id",
        read_only=True,
    )
    businessType = serializers.CharField(
        source="business.business_type",
        read_only=True,
    )
    productType = serializers.ChoiceField(
        source="product_type",
        choices=Product.ProductType.choices,
    )
    lowStockLevel = serializers.IntegerField(
        source="low_stock_level",
        min_value=0,
        required=False,
    )
    reservedStock = serializers.IntegerField(
        source="reserved_stock",
        read_only=True,
    )
    availableStock = serializers.SerializerMethodField()
    costPrice = serializers.DecimalField(
        source="cost_price",
        max_digits=14,
        decimal_places=2,
        min_value=0,
        required=False,
    )
    sellingPrice = serializers.DecimalField(
        source="selling_price",
        max_digits=14,
        decimal_places=2,
        min_value=0,
        required=False,
    )
    designCode = serializers.CharField(
        source="design_code",
        max_length=100,
        required=False,
        allow_blank=True,
    )
    batchNumber = serializers.CharField(
        source="batch_number",
        max_length=120,
        required=False,
        allow_blank=True,
    )
    piecesPerBox = serializers.IntegerField(
        source="pieces_per_box",
        min_value=0,
        required=False,
    )
    sqmPerBox = serializers.DecimalField(
        source="sqm_per_box",
        max_digits=10,
        decimal_places=2,
        min_value=0,
        required=False,
    )
    loosePieces = serializers.IntegerField(
        source="loose_pieces",
        min_value=0,
        required=False,
    )
    styleCode = serializers.CharField(
        source="style_code",
        max_length=100,
        required=False,
        allow_blank=True,
    )
    isActive = serializers.BooleanField(
        source="is_active",
        read_only=True,
    )
    createdAt = serializers.DateTimeField(
        source="created_at",
        read_only=True,
    )
    updatedAt = serializers.DateTimeField(
        source="updated_at",
        read_only=True,
    )

    def get_availableStock(self, obj):
        # Reports stock that is not held by pending external payments.
        return max(0, obj.stock - obj.reserved_stock)

    class Meta:
        model = Product
        fields = (
            "id",
            "businessId",
            "businessType",
            "productType",
            "name",
            "sku",
            "category",
            "brand",
            "unit",
            "stock",
            "reservedStock",
            "availableStock",
            "lowStockLevel",
            "costPrice",
            "sellingPrice",
            "designCode",
            "size",
            "finish",
            "color",
            "batchNumber",
            "piecesPerBox",
            "sqmPerBox",
            "loosePieces",
            "styleCode",
            "isActive",
            "createdAt",
            "updatedAt",
        )
        read_only_fields = (
            "id",
            "businessId",
            "businessType",
            "reservedStock",
            "availableStock",
            "isActive",
            "createdAt",
            "updatedAt",
        )
        extra_kwargs = {
            "name": {"max_length": 180},
            "sku": {"max_length": 100},
            "category": {"max_length": 120},
            "brand": {
                "max_length": 120,
                "required": False,
                "allow_blank": True,
            },
            "stock": {
                "min_value": 0,
                "required": False,
            },
            "size": {
                "max_length": 100,
                "required": False,
                "allow_blank": True,
            },
            "finish": {
                "max_length": 100,
                "required": False,
                "allow_blank": True,
            },
            "color": {
                "max_length": 120,
                "required": False,
                "allow_blank": True,
            },
        }

    def validate_name(self, value):
        # Prevents blank-looking product names.
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "A product name is required."
            )

        return value

    def validate_sku(self, value):
        # Normalizes spacing while preserving the shop's preferred SKU case.
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "A SKU or stock code is required."
            )

        return value

    def validate_category(self, value):
        # Prevents blank-looking categories.
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "A product category is required."
            )

        return value

    def validate(self, attrs):
        # Enforces business type, tile design code and SKU isolation.
        business = self.context["business"]
        instance = self.instance

        product_type = attrs.get(
            "product_type",
            instance.product_type if instance else Product.ProductType.STANDARD,
        )
        design_code = attrs.get(
            "design_code",
            instance.design_code if instance else "",
        )
        sku = attrs.get(
            "sku",
            instance.sku if instance else "",
        )

        errors = {}

        if (
            product_type == Product.ProductType.FASHION
            and business.business_type != Business.BusinessType.BOUTIQUE
        ):
            errors["productType"] = (
                "Boutique products can only belong to a boutique business."
            )

        if (
            product_type
            in (
                Product.ProductType.STANDARD,
                Product.ProductType.TILE,
            )
            and business.business_type
            != Business.BusinessType.BUILDING_MATERIALS
        ):
            errors["productType"] = (
                "Standard and tile products can only belong to a "
                "building materials business."
            )

        if (
            product_type == Product.ProductType.TILE
            and not design_code.strip()
        ):
            errors["designCode"] = (
                "A tile design number or design code is required."
            )

        duplicate_sku = Product.objects.filter(
            business=business,
            sku__iexact=sku,
        )

        if instance:
            duplicate_sku = duplicate_sku.exclude(pk=instance.pk)

        if duplicate_sku.exists():
            errors["sku"] = (
                "A product with this SKU already exists in this business."
            )

        if (
            instance
            and "stock" in attrs
            and attrs["stock"] != instance.stock
        ):
            errors["stock"] = (
                "Use the stock-adjustment endpoint to change stock "
                "so the movement is recorded."
            )

        if errors:
            raise serializers.ValidationError(errors)

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        # Creates the product only inside the business resolved by the URL.
        product = Product(
            business=self.context["business"],
            **validated_data,
        )
        product.full_clean()
        product.save()

        # Records opening stock so the first quantity has an audit trail.
        if product.stock > 0:
            request = self.context["request"]

            StockMovement.objects.create(
                business=product.business,
                product=product,
                movement_type=StockMovement.MovementType.STOCK_IN,
                quantity=product.stock,
                previous_stock=0,
                new_stock=product.stock,
                reason="Opening stock",
                created_by=request.user,
            )

        return product

    def update(self, instance, validated_data):
        # Validates the complete product before saving any change.
        for field_name, value in validated_data.items():
            setattr(instance, field_name, value)

        instance.full_clean()
        instance.save()
        return instance

    def to_representation(self, instance):
        # Cashiers can sell products but cannot view confidential cost prices.
        data = super().to_representation(instance)

        if self.context.get("current_role") == "cashier":
            data.pop("costPrice", None)

        return data


class StockAdjustmentSerializer(serializers.Serializer):
    # Validates signed stock changes submitted by the inventory pages.

    quantity = serializers.IntegerField()
    type = serializers.ChoiceField(
        choices=(
            StockMovement.MovementType.STOCK_IN,
            StockMovement.MovementType.ADJUSTMENT,
            StockMovement.MovementType.DAMAGE,
            StockMovement.MovementType.RETURN,
        )
    )
    reason = serializers.CharField(max_length=255)

    def validate_reason(self, value):
        # Prevents blank-looking audit reasons.
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "A reason is required."
            )

        return value

    def validate(self, attrs):
        # Enforces sensible quantity directions for each movement type.
        quantity = attrs["quantity"]
        movement_type = attrs["type"]
        errors = {}

        if quantity == 0:
            errors["quantity"] = (
                "A stock adjustment quantity cannot be zero."
            )

        if (
            movement_type
            in (
                StockMovement.MovementType.STOCK_IN,
                StockMovement.MovementType.RETURN,
            )
            and quantity < 0
        ):
            errors["quantity"] = (
                "Stock received and customer returns must increase stock."
            )

        if (
            movement_type == StockMovement.MovementType.DAMAGE
            and quantity > 0
        ):
            errors["quantity"] = (
                "Damaged stock must reduce the available quantity."
            )

        if errors:
            raise serializers.ValidationError(errors)

        return attrs


class StockMovementSerializer(serializers.ModelSerializer):
    # Matches the stock-movement field names already used by React.

    businessId = serializers.UUIDField(
        source="business_id",
        read_only=True,
    )
    businessType = serializers.CharField(
        source="business.business_type",
        read_only=True,
    )
    productId = serializers.UUIDField(
        source="product_id",
        read_only=True,
    )
    productName = serializers.CharField(
        source="product_name",
        read_only=True,
    )
    type = serializers.CharField(
        source="movement_type",
        read_only=True,
    )
    previousStock = serializers.IntegerField(
        source="previous_stock",
        read_only=True,
    )
    newStock = serializers.IntegerField(
        source="new_stock",
        read_only=True,
    )
    user = serializers.CharField(
        source="created_by_name",
        read_only=True,
    )
    createdAt = serializers.DateTimeField(
        source="created_at",
        read_only=True,
    )

    class Meta:
        model = StockMovement
        fields = (
            "id",
            "businessId",
            "businessType",
            "productId",
            "productName",
            "type",
            "quantity",
            "unit",
            "previousStock",
            "newStock",
            "reason",
            "user",
            "createdAt",
        )
        read_only_fields = fields

