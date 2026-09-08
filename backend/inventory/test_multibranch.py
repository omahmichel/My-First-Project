from decimal import Decimal

from django.contrib.auth import get_user_model
from django.http import Http404
from django.test import TestCase

from businesses.branch_access import ensure_main_branch, resolve_branch_for_user
from businesses.models import Branch, BranchAccess, Business, BusinessMembership
from intelligence.services.branches import calculate_multibranch_intelligence
from inventory.branch_service import create_branch_transfer
from inventory.models import BranchInventory, BranchStockMovement, Product, StockMovement
from inventory.restock_models import Supplier
from inventory.restock_service import create_restock
from sales.mobile_money_service import (
    _create_pending_mobile_money_records,
    _release_failed_mobile_money_sale,
)
from sales.models import Sale
from sales.services import create_completed_sale


User = get_user_model()


class MultiBranchFoundationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner.multibranch@example.com",
            full_name="Branch Owner",
            password="test-password-123",
        )
        self.business = Business.objects.create(
            owner=self.owner,
            name="Branch Test Traders",
            slug="branch-test-traders",
            business_type=Business.BusinessType.BUILDING_MATERIALS,
            location="Accra",
        )
        self.owner_membership = BusinessMembership.objects.create(
            business=self.business,
            user=self.owner,
            role=BusinessMembership.Role.OWNER,
        )
        self.main = ensure_main_branch(
            business=self.business,
            created_by=self.owner,
        )
        self.kumasi = Branch.objects.create(
            business=self.business,
            name="Kumasi Branch",
            code="KSI",
            location="Kumasi",
            created_by=self.owner,
        )
        self.product = Product.objects.create(
            business=self.business,
            product_type=Product.ProductType.STANDARD,
            name="Premium Cement",
            sku="CEM-001",
            category="Cement",
            unit=Product.Unit.BAG,
            stock=10,
            reserved_stock=0,
            low_stock_level=2,
            cost_price=Decimal("8.00"),
            selling_price=Decimal("20.00"),
        )
        BranchInventory.objects.create(
            branch=self.main,
            product=self.product,
            stock=10,
            reserved_stock=0,
            low_stock_level=2,
        )
        BranchInventory.objects.create(
            branch=self.kumasi,
            product=self.product,
            stock=0,
            reserved_stock=0,
            low_stock_level=2,
        )

    def inventory(self, branch):
        return BranchInventory.objects.get(branch=branch, product=self.product)

    def test_transfer_moves_location_stock_without_changing_business_total(self):
        transfer = create_branch_transfer(
            business=self.business,
            source_branch=self.main,
            destination_branch=self.kumasi,
            user=self.owner,
            items=[{"productId": self.product.id, "quantity": 4}],
            reason="Balance branch stock",
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)
        self.assertEqual(self.inventory(self.main).stock, 6)
        self.assertEqual(self.inventory(self.kumasi).stock, 4)
        self.assertEqual(transfer.items.count(), 1)
        self.assertEqual(
            BranchStockMovement.objects.filter(
                movement_type__in=(
                    BranchStockMovement.MovementType.TRANSFER_OUT,
                    BranchStockMovement.MovementType.TRANSFER_IN,
                )
            ).count(),
            2,
        )
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_sale_restock_and_reservation_keep_branch_and_aggregate_in_sync(self):
        create_branch_transfer(
            business=self.business,
            source_branch=self.main,
            destination_branch=self.kumasi,
            user=self.owner,
            items=[{"productId": self.product.id, "quantity": 4}],
        )

        sale, replayed = create_completed_sale(
            business=self.business,
            user=self.owner,
            branch=self.kumasi,
            idempotency_key="branch-cash-sale",
            data={
                "items": [
                    {
                        "productId": self.product.id,
                        "quantity": 2,
                        "unitPrice": Decimal("20.00"),
                    }
                ],
                "discount": Decimal("0.00"),
                "paymentMethod": Sale.PaymentMethod.CASH,
            },
        )
        self.assertFalse(replayed)
        self.assertEqual(sale.branch_id, self.kumasi.id)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)
        self.assertEqual(self.inventory(self.main).stock, 6)
        self.assertEqual(self.inventory(self.kumasi).stock, 2)

        supplier = Supplier.objects.create(
            business=self.business,
            name="Cement Supplier",
        )
        create_restock(
            business=self.business,
            branch=self.kumasi,
            user=self.owner,
            data={
                "supplierId": supplier.id,
                "supplierReference": "SUP-001",
                "purchaseDate": sale.completed_at.date(),
                "initialPayment": Decimal("0.00"),
                "items": [
                    {
                        "productId": self.product.id,
                        "quantity": 3,
                        "unitCost": Decimal("10.00"),
                    }
                ],
            },
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 11)
        self.assertEqual(self.inventory(self.kumasi).stock, 5)

        pending_sale, payment = _create_pending_mobile_money_records(
            business=self.business,
            branch=self.kumasi,
            user=self.owner,
            idempotency_key="branch-mobile-pending",
            data={
                "items": [
                    {
                        "productId": self.product.id,
                        "quantity": 1,
                        "unitPrice": Decimal("20.00"),
                    }
                ],
                "discount": Decimal("0.00"),
                "paymentMethod": Sale.PaymentMethod.MOBILE_MONEY,
                "mobileMoneyNetwork": "mtn",
                "mobileMoneyNumber": "0241234567",
            },
        )
        self.assertEqual(pending_sale.branch_id, self.kumasi.id)
        self.product.refresh_from_db()
        self.assertEqual(self.product.reserved_stock, 1)
        self.assertEqual(self.inventory(self.kumasi).reserved_stock, 1)

        _release_failed_mobile_money_sale(
            payment_id=payment.id,
            message="Gateway rejected test prompt.",
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.reserved_stock, 0)
        self.assertEqual(self.inventory(self.kumasi).reserved_stock, 0)

        intelligence = calculate_multibranch_intelligence(self.business)
        kumasi = next(
            row for row in intelligence["branches"]
            if row["id"] == str(self.kumasi.id)
        )
        self.assertEqual(kumasi["revenue"], "40.00")
        self.assertEqual(kumasi["totalStockUnits"], 5)
        self.assertTrue(intelligence["safety"]["transfersRequireExplicitConfirmation"])

    def test_cashier_without_assignment_cannot_cross_from_main_to_other_branch(self):
        cashier = User.objects.create_user(
            email="cashier.multibranch@example.com",
            full_name="Branch Cashier",
            password="test-password-123",
        )
        membership = BusinessMembership.objects.create(
            business=self.business,
            user=cashier,
            role=BusinessMembership.Role.CASHIER,
        )
        BranchAccess.objects.create(
            branch=self.main,
            membership=membership,
            is_active=True,
        )

        self.assertEqual(
            resolve_branch_for_user(
                business=self.business,
                user=cashier,
                role=BusinessMembership.Role.CASHIER,
            ).id,
            self.main.id,
        )
        with self.assertRaises(Http404):
            resolve_branch_for_user(
                business=self.business,
                user=cashier,
                role=BusinessMembership.Role.CASHIER,
                branch_id=self.kumasi.id,
            )
