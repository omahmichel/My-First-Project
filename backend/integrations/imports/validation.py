from decimal import Decimal

from rest_framework import serializers

from businesses.models import Business
from customers.models import Customer
from customers.serializers import CustomerSerializer
from inventory.models import (
    BranchInventory,
    BranchStockMovement,
    Product,
    StockMovement,
)
from inventory.restock_models import Supplier
from inventory.restock_serializers import SupplierSerializer
from inventory.serializers import ProductSerializer


ACTION_CREATE = "CREATE"
ACTION_UPDATE = "UPDATE"
ACTION_SKIP = "SKIP"
ACTION_ERROR = "ERROR"


def _json_errors(errors):
    if isinstance(errors, dict):
        return {str(key): _json_errors(value) for key, value in errors.items()}
    if isinstance(errors, (list, tuple)):
        return [_json_errors(value) for value in errors]
    return str(errors)


def _context(*, business, request):
    return {
        "business": business,
        "request": request,
        "current_role": "owner",
    }


def _guard(instance):
    return {
        "matchId": str(instance.id),
        "updatedAt": instance.updated_at.isoformat(),
    }


def _changed(instance, validated_data):
    for field, value in validated_data.items():
        if getattr(instance, field) != value:
            return True
    return False


def _optional(row, key):
    return key in row and str(row.get(key, "")).strip() != ""


def _product_payload(*, row, business, creating):
    payload = {
        "name": row.get("name", ""),
        "sku": row.get("sku", ""),
        "category": row.get("category", ""),
    }
    optional_fields = (
        "brand",
        "unit",
        "productType",
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
    )
    for field in optional_fields:
        if _optional(row, field):
            payload[field] = row[field]

    if creating:
        payload.setdefault(
            "productType",
            (
                Product.ProductType.FASHION
                if business.business_type == Business.BusinessType.BOUTIQUE
                else Product.ProductType.STANDARD
            ),
        )
        payload.setdefault("unit", Product.Unit.PIECE)
        payload["stock"] = 0
    return payload


def _opening_stock(row):
    raw = row.get("openingStock", "")
    if str(raw).strip() == "":
        return 0
    return serializers.IntegerField(min_value=0).run_validation(raw)


def validate_product_row(*, row, row_number, business, request):
    matches = list(
        Product.objects.filter(business=business, sku__iexact=row.get("sku", ""))[:2]
    )
    if len(matches) > 1:
        return _error_row(row, row_number, {"sku": ["More than one product matches this SKU."]})
    existing = matches[0] if matches else None

    try:
        opening_stock = _opening_stock(row)
    except serializers.ValidationError as exc:
        return _error_row(row, row_number, {"openingStock": _json_errors(exc.detail)})

    if existing and opening_stock > 0:
        return _error_row(
            row,
            row_number,
            {
                "openingStock": [
                    "Opening stock is only allowed for new products. Use the branch inventory import to set stock for an existing SKU."
                ]
            },
        )

    serializer = ProductSerializer(
        existing,
        data=_product_payload(row=row, business=business, creating=existing is None),
        partial=existing is not None,
        context=_context(business=business, request=request),
    )
    if not serializer.is_valid():
        return _error_row(row, row_number, _json_errors(serializer.errors))

    action = ACTION_CREATE
    guard = None
    if existing:
        action = ACTION_UPDATE if _changed(existing, serializer.validated_data) else ACTION_SKIP
        guard = _guard(existing)

    data = dict(row)
    data["openingStock"] = opening_stock
    return {
        "rowNumber": row_number,
        "action": action,
        "data": data,
        "errors": {},
        "matchId": str(existing.id) if existing else None,
        "guard": guard,
    }


def validate_customer_row(*, row, row_number, business, request):
    phone = str(row.get("phone", "")).strip()
    matches = list(Customer.objects.filter(business=business, phone__iexact=phone)[:2])
    if len(matches) > 1:
        return _error_row(
            row,
            row_number,
            {"phone": ["More than one customer has this exact phone number. Resolve the duplicates before importing."]},
        )
    existing = matches[0] if matches else None
    payload = {"name": row.get("name", ""), "phone": phone}
    for field in ("email", "address"):
        if field in row:
            payload[field] = row[field]
    serializer = CustomerSerializer(
        existing,
        data=payload,
        partial=existing is not None,
        context=_context(business=business, request=request),
    )
    if not serializer.is_valid():
        return _error_row(row, row_number, _json_errors(serializer.errors))
    action = ACTION_CREATE
    guard = None
    if existing:
        action = ACTION_UPDATE if _changed(existing, serializer.validated_data) else ACTION_SKIP
        guard = _guard(existing)
    return {
        "rowNumber": row_number,
        "action": action,
        "data": dict(row),
        "errors": {},
        "matchId": str(existing.id) if existing else None,
        "guard": guard,
    }


def validate_supplier_row(*, row, row_number, business, request):
    name = str(row.get("name", "")).strip()
    matches = list(Supplier.objects.filter(business=business, name__iexact=name)[:2])
    if len(matches) > 1:
        return _error_row(
            row,
            row_number,
            {"name": ["More than one supplier has this exact name. Resolve the duplicates before importing."]},
        )
    existing = matches[0] if matches else None
    payload = {"name": name}
    for field in ("phone", "email", "address", "notes"):
        if field in row:
            payload[field] = row[field]
    serializer = SupplierSerializer(
        existing,
        data=payload,
        partial=existing is not None,
    )
    if not serializer.is_valid():
        return _error_row(row, row_number, _json_errors(serializer.errors))
    action = ACTION_CREATE
    guard = None
    if existing:
        action = ACTION_UPDATE if _changed(existing, serializer.validated_data) else ACTION_SKIP
        guard = _guard(existing)
    return {
        "rowNumber": row_number,
        "action": action,
        "data": dict(row),
        "errors": {},
        "matchId": str(existing.id) if existing else None,
        "guard": guard,
    }


def validate_branch_inventory_row(*, row, row_number, business, branch, request):
    sku = str(row.get("sku", "")).strip()
    product = Product.objects.filter(
        business=business,
        sku__iexact=sku,
        is_active=True,
    ).first()
    if not product:
        return _error_row(row, row_number, {"sku": ["No active product with this SKU exists in this business."]})
    try:
        target_stock = serializers.IntegerField(min_value=0).run_validation(row.get("stock", ""))
    except serializers.ValidationError as exc:
        return _error_row(row, row_number, {"stock": _json_errors(exc.detail)})

    inventory = BranchInventory.objects.filter(branch=branch, product=product).first()
    if inventory:
        current_stock = int(inventory.stock)
        current_reserved = int(inventory.reserved_stock)
        row_exists = True
    else:
        main_branch = business.branches.filter(is_main=True).first()
        is_main = bool(main_branch and main_branch.id == branch.id)
        current_stock = int(product.stock) if is_main else 0
        current_reserved = int(product.reserved_stock) if is_main else 0
        row_exists = False

    if target_stock < current_reserved:
        return _error_row(
            row,
            row_number,
            {
                "stock": [
                    f"Stock cannot be set below {current_reserved} unit(s) reserved at this branch."
                ]
            },
        )

    action = ACTION_SKIP if target_stock == current_stock else ACTION_UPDATE
    return {
        "rowNumber": row_number,
        "action": action,
        "data": {"sku": sku, "stock": target_stock},
        "errors": {},
        "matchId": str(product.id),
        "guard": {
            "productId": str(product.id),
            "expectedCurrentStock": current_stock,
            "expectedReservedStock": current_reserved,
            "rowExists": row_exists,
        },
    }


def _error_row(row, row_number, errors):
    return {
        "rowNumber": row_number,
        "action": ACTION_ERROR,
        "data": dict(row),
        "errors": errors,
        "matchId": None,
        "guard": None,
    }


def validate_mapped_row(*, dataset, row, row_number, business, branch, request):
    if dataset == "products":
        return validate_product_row(
            row=row,
            row_number=row_number,
            business=business,
            request=request,
        )
    if dataset == "customers":
        return validate_customer_row(
            row=row,
            row_number=row_number,
            business=business,
            request=request,
        )
    if dataset == "suppliers":
        return validate_supplier_row(
            row=row,
            row_number=row_number,
            business=business,
            request=request,
        )
    if dataset == "branch_inventory":
        return validate_branch_inventory_row(
            row=row,
            row_number=row_number,
            business=business,
            branch=branch,
            request=request,
        )
    raise serializers.ValidationError({"dataset": "Unsupported import dataset."})


def _assert_guard(instance, guard, label):
    if not guard or str(instance.id) != str(guard.get("matchId")):
        raise serializers.ValidationError(
            {"previewToken": f"{label} changed after preview. Preview the file again."}
        )
    if instance.updated_at.isoformat() != guard.get("updatedAt"):
        raise serializers.ValidationError(
            {"previewToken": f"{label} changed after preview. Preview the file again."}
        )


def apply_product_row(*, entry, business, branch, user, request):
    if entry["action"] == ACTION_SKIP:
        return ACTION_SKIP
    row = entry["data"]
    existing = Product.objects.select_for_update().filter(
        business=business,
        sku__iexact=row.get("sku", ""),
    ).first()
    guard = entry.get("guard")
    if guard:
        if not existing:
            raise serializers.ValidationError(
                {"previewToken": "A product matched during preview is no longer available. Preview the file again."}
            )
        _assert_guard(existing, guard, "A product")
        serializer = ProductSerializer(
            existing,
            data=_product_payload(row=row, business=business, creating=False),
            partial=True,
            context=_context(business=business, request=request),
        )
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(existing, field, value)
        existing.full_clean()
        existing.save()
        return ACTION_UPDATE

    if existing:
        raise serializers.ValidationError(
            {"previewToken": "A product with this SKU was created after preview. Preview the file again."}
        )

    serializer = ProductSerializer(
        data=_product_payload(row=row, business=business, creating=True),
        context=_context(business=business, request=request),
    )
    serializer.is_valid(raise_exception=True)
    data = dict(serializer.validated_data)
    data["stock"] = 0
    product = Product(business=business, **data)
    product.full_clean()
    product.save()

    from inventory.branch_service import apply_locked_branch_change, seed_product_inventory

    seed_product_inventory(product=product, selected_branch=branch, opening_stock=0)
    opening_stock = int(row.get("openingStock", 0) or 0)
    if opening_stock > 0:
        inventory = BranchInventory.objects.select_for_update().get(
            branch=branch,
            product=product,
        )
        apply_locked_branch_change(
            business=business,
            branch=branch,
            product=product,
            branch_inventory=inventory,
            stock_delta=opening_stock,
            reserved_delta=0,
            movement_type=BranchStockMovement.MovementType.OPENING_STOCK,
            reason="Opening stock from data import",
            user=user,
            business_movement_type=StockMovement.MovementType.STOCK_IN,
        )
    return ACTION_CREATE


def apply_customer_row(*, entry, business, user, request, **_kwargs):
    if entry["action"] == ACTION_SKIP:
        return ACTION_SKIP
    row = entry["data"]
    phone = str(row.get("phone", "")).strip()
    existing = Customer.objects.select_for_update().filter(
        business=business,
        phone__iexact=phone,
    ).first()
    guard = entry.get("guard")
    payload = {"name": row.get("name", ""), "phone": phone}
    for field in ("email", "address"):
        if field in row:
            payload[field] = row[field]
    serializer = CustomerSerializer(
        existing if guard else None,
        data=payload,
        partial=bool(guard),
        context=_context(business=business, request=request),
    )
    if guard:
        if not existing:
            raise serializers.ValidationError(
                {"previewToken": "A customer matched during preview is no longer available. Preview the file again."}
            )
        _assert_guard(existing, guard, "A customer")
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(existing, field, value)
        existing.full_clean()
        existing.save()
        return ACTION_UPDATE
    if existing:
        raise serializers.ValidationError(
            {"previewToken": "A customer with this phone number was created after preview. Preview the file again."}
        )
    serializer.is_valid(raise_exception=True)
    customer = Customer(
        business=business,
        created_by=user,
        **serializer.validated_data,
    )
    customer.full_clean()
    customer.save()
    return ACTION_CREATE


def apply_supplier_row(*, entry, business, user, request, **_kwargs):
    if entry["action"] == ACTION_SKIP:
        return ACTION_SKIP
    row = entry["data"]
    name = str(row.get("name", "")).strip()
    existing = Supplier.objects.select_for_update().filter(
        business=business,
        name__iexact=name,
    ).first()
    guard = entry.get("guard")
    payload = {"name": name}
    for field in ("phone", "email", "address", "notes"):
        if field in row:
            payload[field] = row[field]
    serializer = SupplierSerializer(
        existing if guard else None,
        data=payload,
        partial=bool(guard),
    )
    if guard:
        if not existing:
            raise serializers.ValidationError(
                {"previewToken": "A supplier matched during preview is no longer available. Preview the file again."}
            )
        _assert_guard(existing, guard, "A supplier")
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(existing, field, value)
        existing.full_clean()
        existing.save()
        return ACTION_UPDATE
    if existing:
        raise serializers.ValidationError(
            {"previewToken": "A supplier with this name was created after preview. Preview the file again."}
        )
    serializer.is_valid(raise_exception=True)
    supplier = Supplier(business=business, **serializer.validated_data)
    supplier.full_clean()
    supplier.save()
    return ACTION_CREATE


def apply_branch_inventory_row(*, entry, business, branch, user, request, **_kwargs):
    if entry["action"] == ACTION_SKIP:
        return ACTION_SKIP
    guard = entry.get("guard") or {}
    product = Product.objects.select_for_update().filter(
        business=business,
        id=guard.get("productId"),
        is_active=True,
    ).first()
    if not product:
        raise serializers.ValidationError(
            {"previewToken": "An inventory product changed after preview. Preview the file again."}
        )

    from inventory.branch_service import apply_locked_branch_change, locked_branch_inventory_map

    inventory = locked_branch_inventory_map(
        branch=branch,
        products={product.id: product},
    )[product.id]
    if int(inventory.stock) != int(guard.get("expectedCurrentStock", -1)):
        raise serializers.ValidationError(
            {"previewToken": "Branch stock changed after preview. Preview the file again before applying."}
        )
    if int(inventory.reserved_stock) != int(guard.get("expectedReservedStock", -1)):
        raise serializers.ValidationError(
            {"previewToken": "Reserved branch stock changed after preview. Preview the file again before applying."}
        )

    target = int(entry["data"]["stock"])
    if target < inventory.reserved_stock:
        raise serializers.ValidationError(
            {"stock": "Imported stock cannot be below currently reserved stock."}
        )
    delta = target - int(inventory.stock)
    if delta:
        apply_locked_branch_change(
            business=business,
            branch=branch,
            product=product,
            branch_inventory=inventory,
            stock_delta=delta,
            reserved_delta=0,
            movement_type=BranchStockMovement.MovementType.ADJUSTMENT,
            reason="Branch stock set from data import",
            user=user,
            business_movement_type=StockMovement.MovementType.ADJUSTMENT,
        )
    return ACTION_UPDATE if delta else ACTION_SKIP


APPLIERS = {
    "products": apply_product_row,
    "customers": apply_customer_row,
    "suppliers": apply_supplier_row,
    "branch_inventory": apply_branch_inventory_row,
}
