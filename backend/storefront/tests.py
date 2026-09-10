import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import NotFound, ValidationError

from businesses.models import Business, Branch
from inventory.models import Product, BranchInventory, StockMovement, BranchStockMovement
from sales.models import Sale, Payment
from .models import Storefront, StorefrontListing, StorefrontOrder, StorefrontOrderItem
from .services import create_pending_order


class PendingStorefrontOrderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(email='storefront-test@example.com', password=None)
        cls.business = Business.objects.create(owner=cls.owner, name='Test Shop', slug='test-shop', business_type='building_materials')
        cls.branch = Branch.objects.create(business=cls.business, name='Main', code='MAIN', is_main=True)
        cls.product = Product.objects.create(business=cls.business, name='Cement', sku='CEM-1', category='Cement', unit='bag', stock=12, reserved_stock=2, selling_price=Decimal('50.00'))
        cls.inventory = BranchInventory.objects.create(branch=cls.branch, product=cls.product, stock=7, reserved_stock=2)
        cls.shop = Storefront.objects.create(business=cls.business, branch=cls.branch, is_published=True)
        cls.listing = StorefrontListing.objects.create(storefront=cls.shop, product=cls.product, is_published=True)

    def payload(self):
        return {
            'idempotencyKey': str(uuid.uuid4()),
            'customerName': 'Demo Buyer',
            'customerPhone': '0244000000',
            'items': [{'productId': str(self.product.id), 'quantity': 2}],
        }

    def submit(self, data):
        return create_pending_order(shop_slug=self.business.slug, data=data)

    def test_pending_order_snapshots_price_without_stock_or_payment_changes(self):
        order, replay = self.submit(self.payload())
        self.assertFalse(replay)
        self.assertEqual(order.status, 'pending')
        self.assertEqual(order.total, Decimal('100.00'))
        self.assertEqual(order.currency, 'GHS')
        self.assertIsNone(order.sale_id)
        line = order.items.get()
        self.assertEqual(line.unit_price, Decimal('50.00'))
        self.assertEqual(line.product_name, 'Cement')
        self.product.refresh_from_db()
        self.inventory.refresh_from_db()
        self.assertEqual((self.product.stock, self.product.reserved_stock), (12, 2))
        self.assertEqual((self.inventory.stock, self.inventory.reserved_stock), (7, 2))
        for model in (Sale, Payment, StockMovement, BranchStockMovement):
            self.assertEqual(model.objects.count(), 0)

    def test_repeated_submission_returns_same_order(self):
        data = self.payload()
        first, _ = self.submit(data)
        second, replay = self.submit(data)
        self.assertTrue(replay)
        self.assertEqual(first.id, second.id)
        self.assertEqual(StorefrontOrder.objects.count(), 1)
        self.assertEqual(StorefrontOrderItem.objects.count(), 1)

    def test_submission_key_cannot_be_reused_for_changed_order(self):
        data = self.payload()
        self.submit(data)
        data['items'][0]['quantity'] = 3
        with self.assertRaises(ValidationError):
            self.submit(data)
        self.assertEqual(StorefrontOrder.objects.count(), 1)

    def test_buyer_cannot_supply_price(self):
        data = self.payload()
        data['items'][0]['unitPrice'] = '0.01'
        with self.assertRaises(ValidationError):
            self.submit(data)
        self.assertFalse(StorefrontOrder.objects.exists())

    def test_branch_available_stock_limits_order(self):
        data = self.payload()
        data['items'][0]['quantity'] = 6
        with self.assertRaises(ValidationError):
            self.submit(data)
        self.assertFalse(StorefrontOrder.objects.exists())

    def test_unpublished_shop_is_unavailable(self):
        self.shop.is_published = False
        self.shop.save()
        with self.assertRaises(NotFound):
            self.submit(self.payload())
        self.assertFalse(StorefrontOrder.objects.exists())

    def test_unpublished_product_is_unavailable(self):
        self.listing.is_published = False
        self.listing.save()
        with self.assertRaises(ValidationError):
            self.submit(self.payload())
        self.assertFalse(StorefrontOrder.objects.exists())

    def test_duplicate_product_lines_are_rejected(self):
        data = self.payload()
        data['items'].append(dict(data['items'][0]))
        with self.assertRaises(ValidationError):
            self.submit(data)
        self.assertFalse(StorefrontOrder.objects.exists())
