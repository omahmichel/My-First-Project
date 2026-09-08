import uuid

from django.db import transaction
from rest_framework import serializers

from businesses.branch_access import ensure_main_branch
from businesses.models import Branch

from .models import (
    BranchInventory,
    BranchStockMovement,
    BranchTransfer,
    BranchTransferItem,
    Product,
    StockMovement,
)


def seed_branch_inventory(*, branch):
    """Creates zero-balance rows for every product not yet represented at a branch."""
    products = list(Product.objects.filter(business=branch.business))
    existing = set(
        BranchInventory.objects.filter(
            branch=branch, product_id__in=[item.id for item in products]
        ).values_list("product_id", flat=True)
    )
    BranchInventory.objects.bulk_create(
        [
            BranchInventory(
                branch=branch,
                product=product,
                stock=0,
                reserved_stock=0,
                low_stock_level=product.low_stock_level,
            )
            for product in products
            if product.id not in existing
        ],
        ignore_conflicts=True,
    )


def seed_product_inventory(*, product, selected_branch, opening_stock=0):
    """Creates one inventory row per active branch and puts opening stock in one branch."""
    branches = list(
        Branch.objects.filter(business=product.business, is_active=True).order_by(
            "-is_main", "id"
        )
    )
    if not branches:
        branches = [ensure_main_branch(business=product.business)]

    BranchInventory.objects.bulk_create(
        [
            BranchInventory(
                branch=branch,
                product=product,
                stock=(opening_stock if branch.id == selected_branch.id else 0),
                reserved_stock=0,
                low_stock_level=product.low_stock_level,
            )
            for branch in branches
        ],
        ignore_conflicts=True,
    )


def locked_branch_inventory_map(*, branch, products):
    """Returns locked branch rows for already-locked products, repairing old data safely."""
    product_list = list(products.values()) if isinstance(products, dict) else list(products)
    if any(product.business_id != branch.business_id for product in product_list):
        raise serializers.ValidationError(
            {"branchId": "The selected branch does not match the products."}
        )

    product_ids = [product.id for product in product_list]
    existing_ids = set(
        BranchInventory.objects.filter(
            branch=branch, product_id__in=product_ids
        ).values_list("product_id", flat=True)
    )
    missing = [product for product in product_list if product.id not in existing_ids]
    if missing:
        main_branch = ensure_main_branch(business=branch.business)
        BranchInventory.objects.bulk_create(
            [
                BranchInventory(
                    branch=branch,
                    product=product,
                    stock=(product.stock if branch.id == main_branch.id else 0),
                    reserved_stock=(
                        product.reserved_stock if branch.id == main_branch.id else 0
                    ),
                    low_stock_level=product.low_stock_level,
                )
                for product in missing
            ],
            ignore_conflicts=True,
        )

    rows = BranchInventory.objects.select_for_update().filter(
        branch=branch, product_id__in=product_ids
    ).select_related("product")
    result = {row.product_id: row for row in rows}
    if len(result) != len(set(product_ids)):
        raise serializers.ValidationError(
            {"items": "Branch inventory could not be prepared for every product."}
        )
    return result


def apply_locked_branch_change(
    *,
    business,
    branch,
    product,
    branch_inventory,
    stock_delta=0,
    reserved_delta=0,
    movement_type,
    reason,
    user,
    business_movement_type=None,
):
    """Changes branch and aggregate quantities together and writes immutable audit rows."""
    stock_delta = int(stock_delta)
    reserved_delta = int(reserved_delta)
    if stock_delta == 0 and reserved_delta == 0:
        raise serializers.ValidationError(
            {"quantity": "The branch inventory change cannot be zero."}
        )

    previous_branch_stock = int(branch_inventory.stock)
    previous_branch_reserved = int(branch_inventory.reserved_stock)
    next_branch_stock = previous_branch_stock + stock_delta
    next_branch_reserved = previous_branch_reserved + reserved_delta

    previous_product_stock = int(product.stock)
    previous_product_reserved = int(product.reserved_stock)
    next_product_stock = previous_product_stock + stock_delta
    next_product_reserved = previous_product_reserved + reserved_delta

    if next_branch_stock < 0 or next_product_stock < 0:
        raise serializers.ValidationError(
            {"quantity": "This change would reduce stock below zero."}
        )
    if next_branch_reserved < 0 or next_product_reserved < 0:
        raise serializers.ValidationError(
            {"quantity": "This change would reduce reserved stock below zero."}
        )
    if next_branch_reserved > next_branch_stock:
        raise serializers.ValidationError(
            {
                "quantity": (
                    f"This change would reduce branch stock below {next_branch_reserved} "
                    "unit(s) reserved for pending payments."
                )
            }
        )
    if next_product_reserved > next_product_stock:
        raise serializers.ValidationError(
            {"quantity": "This change would make aggregate reserved stock invalid."}
        )

    branch_inventory.stock = next_branch_stock
    branch_inventory.reserved_stock = next_branch_reserved
    branch_inventory.save(
        update_fields=("stock", "reserved_stock", "updated_at")
    )

    product.stock = next_product_stock
    product.reserved_stock = next_product_reserved
    product.save(update_fields=("stock", "reserved_stock", "updated_at"))

    stock_movement = None
    if stock_delta and business_movement_type:
        stock_movement = StockMovement.objects.create(
            business=business,
            branch=branch,
            product=product,
            movement_type=business_movement_type,
            quantity=stock_delta,
            previous_stock=previous_product_stock,
            new_stock=next_product_stock,
            reason=reason,
            created_by=user,
        )

    branch_movement = BranchStockMovement.objects.create(
        business=business,
        branch=branch,
        product=product,
        stock_movement=stock_movement,
        movement_type=movement_type,
        quantity=stock_delta,
        reserved_quantity=reserved_delta,
        previous_stock=previous_branch_stock,
        new_stock=next_branch_stock,
        previous_reserved_stock=previous_branch_reserved,
        new_reserved_stock=next_branch_reserved,
        reason=reason,
        created_by=user,
    )
    return stock_movement, branch_movement


def generate_transfer_number():
    return f"BTR-{uuid.uuid4().hex[:10].upper()}"


@transaction.atomic
def create_branch_transfer(
    *, business, source_branch, destination_branch, user, items, reason=""
):
    if source_branch.business_id != business.id or destination_branch.business_id != business.id:
        raise serializers.ValidationError(
            {"branchId": "Both transfer branches must belong to this business."}
        )
    if source_branch.id == destination_branch.id:
        raise serializers.ValidationError(
            {"destinationBranchId": "Choose a different destination branch."}
        )
    if not source_branch.is_active or not destination_branch.is_active:
        raise serializers.ValidationError(
            {"branchId": "Stock can only be transferred between active branches."}
        )

    product_ids = [item["productId"] for item in items]
    if len(product_ids) != len(set(product_ids)):
        raise serializers.ValidationError(
            {"items": "Each product can appear only once in a branch transfer."}
        )
    products = {
        product.id: product
        for product in Product.objects.select_for_update().filter(
            business=business, id__in=product_ids, is_active=True
        ).order_by("id")
    }
    if len(products) != len(product_ids):
        raise serializers.ValidationError(
            {"items": "One or more transfer products are unavailable."}
        )

    source_map = locked_branch_inventory_map(
        branch=source_branch, products=products
    )
    destination_map = locked_branch_inventory_map(
        branch=destination_branch, products=products
    )

    for item in items:
        source = source_map[item["productId"]]
        quantity = int(item["quantity"])
        if quantity <= 0:
            raise serializers.ValidationError(
                {"items": "Transfer quantities must be above zero."}
            )
        if quantity > source.available_stock:
            raise serializers.ValidationError(
                {
                    "items": (
                        f"Only {source.available_stock} {source.product.unit}(s) of "
                        f"{source.product.name} are available at {source_branch.name}."
                    )
                }
            )

    transfer = BranchTransfer.objects.create(
        business=business,
        source_branch=source_branch,
        destination_branch=destination_branch,
        transfer_number=generate_transfer_number(),
        reason=str(reason or "").strip(),
        created_by=user,
    )

    for item in items:
        product = products[item["productId"]]
        quantity = int(item["quantity"])
        source = source_map[product.id]
        destination = destination_map[product.id]

        previous_source_stock = source.stock
        previous_destination_stock = destination.stock
        source.stock -= quantity
        destination.stock += quantity
        source.save(update_fields=("stock", "updated_at"))
        destination.save(update_fields=("stock", "updated_at"))

        BranchTransferItem.objects.create(
            transfer=transfer, product=product, quantity=quantity
        )
        BranchStockMovement.objects.create(
            business=business,
            branch=source_branch,
            product=product,
            movement_type=BranchStockMovement.MovementType.TRANSFER_OUT,
            quantity=-quantity,
            reserved_quantity=0,
            previous_stock=previous_source_stock,
            new_stock=source.stock,
            previous_reserved_stock=source.reserved_stock,
            new_reserved_stock=source.reserved_stock,
            reason=f"Transfer {transfer.transfer_number} to {destination_branch.name}",
            created_by=user,
        )
        BranchStockMovement.objects.create(
            business=business,
            branch=destination_branch,
            product=product,
            movement_type=BranchStockMovement.MovementType.TRANSFER_IN,
            quantity=quantity,
            reserved_quantity=0,
            previous_stock=previous_destination_stock,
            new_stock=destination.stock,
            previous_reserved_stock=destination.reserved_stock,
            new_reserved_stock=destination.reserved_stock,
            reason=f"Transfer {transfer.transfer_number} from {source_branch.name}",
            created_by=user,
        )

    return transfer
