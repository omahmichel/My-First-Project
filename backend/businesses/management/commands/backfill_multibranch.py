from django.core.management.base import BaseCommand
from django.db import transaction

from businesses.branch_access import ensure_main_branch
from businesses.models import BranchAccess, Business
from inventory.models import BranchInventory, BranchStockMovement, Product, StockMovement
from inventory.restock_models import RestockPurchase
from sales.models import Sale


MOVEMENT_MAP = {
    StockMovement.MovementType.STOCK_IN: BranchStockMovement.MovementType.STOCK_IN,
    StockMovement.MovementType.ADJUSTMENT: BranchStockMovement.MovementType.ADJUSTMENT,
    StockMovement.MovementType.DAMAGE: BranchStockMovement.MovementType.DAMAGE,
    StockMovement.MovementType.RETURN: BranchStockMovement.MovementType.RETURN,
    StockMovement.MovementType.SALE: BranchStockMovement.MovementType.SALE,
}


class Command(BaseCommand):
    help = "Backfill legacy StockFlow records into each business Main Branch."

    @transaction.atomic
    def handle(self, *args, **options):
        totals = {
            "businesses": 0,
            "inventories": 0,
            "stock_movements": 0,
            "branch_movements": 0,
            "restocks": 0,
            "sales": 0,
            "accesses": 0,
        }

        for business in Business.objects.all().order_by("id"):
            main = ensure_main_branch(business=business, created_by=business.owner)
            totals["businesses"] += 1

            for membership in business.memberships.filter(is_active=True):
                _, created = BranchAccess.objects.get_or_create(
                    branch=main,
                    membership=membership,
                    defaults={"is_active": True},
                )
                if created:
                    totals["accesses"] += 1

            for product in Product.objects.filter(business=business).order_by("id"):
                _, created = BranchInventory.objects.get_or_create(
                    branch=main,
                    product=product,
                    defaults={
                        "stock": product.stock,
                        "reserved_stock": product.reserved_stock,
                        "low_stock_level": product.low_stock_level,
                    },
                )
                if created:
                    totals["inventories"] += 1

            movements = StockMovement.objects.filter(
                business=business, branch__isnull=True
            ).select_related("product", "created_by")
            for movement in movements.iterator():
                movement.branch = main
                movement.save(update_fields=("branch",))
                totals["stock_movements"] += 1
                _, created = BranchStockMovement.objects.get_or_create(
                    stock_movement=movement,
                    defaults={
                        "business": business,
                        "branch": main,
                        "product": movement.product,
                        "movement_type": MOVEMENT_MAP[movement.movement_type],
                        "quantity": movement.quantity,
                        "reserved_quantity": 0,
                        "previous_stock": movement.previous_stock,
                        "new_stock": movement.new_stock,
                        "previous_reserved_stock": 0,
                        "new_reserved_stock": 0,
                        "reason": movement.reason,
                        "created_by": movement.created_by,
                    },
                )
                if created:
                    totals["branch_movements"] += 1

            totals["restocks"] += RestockPurchase.objects.filter(
                business=business, branch__isnull=True
            ).update(branch=main)
            totals["sales"] += Sale.objects.filter(
                business=business, branch__isnull=True
            ).update(branch=main)

        self.stdout.write(
            self.style.SUCCESS(
                "Multi-branch backfill complete: "
                + ", ".join(f"{key}={value}" for key, value in totals.items())
            )
        )
