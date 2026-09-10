from unittest.mock import patch
from django.test import TestCase, override_settings
from rest_framework.exceptions import ValidationError
from customers.models import Customer
from inventory.models import BranchInventory, BranchStockMovement, Product, StockMovement
from sales.models import Sale, Payment
from .models import StorefrontOrder
from . import test_orders


@override_settings(ALLOWED_HOSTS=['testserver', 'localhost'])
class OrderCompletionTests(TestCase):
    def setUp(self):
        test_orders.ShopOrderManagementTests.setUp(self)
        self.customer = Customer.objects.create(business=self.business, name='Demo Buyer', phone='0244000000')
        self.inventory = BranchInventory.objects.create(branch=self.branch, product=self.product, stock=5, reserved_stock=1)
        self.complete = self.detail + 'complete/'
        self.payload = {'cashReceived': True, 'amountReceived': '50.00'}

    def submit(self, data=None):
        return self.client.post(self.complete, self.payload if data is None else data, format='json')

    def assert_untouched(self):
        self.order.refresh_from_db()
        self.product.refresh_from_db()
        self.inventory.refresh_from_db()
        self.assertEqual(self.order.status, 'pending')
        self.assertEqual(self.product.stock, 10)
        self.assertEqual(self.inventory.stock, 5)
        self.assertFalse(Sale.objects.exists())
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(StockMovement.objects.exists())
        self.assertFalse(BranchStockMovement.objects.exists())

    def test_completion_uses_snapshot_price_and_only_deducts_once(self):
        Product.objects.filter(pk=self.product.id).update(selling_price='75.00')
        first = self.submit()
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(first.data['status'], 'completed')
        self.assertTrue(first.data['receiptNumber'])
        self.assertFalse(first.data['idempotentReplay'])
        second = self.submit()
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.data['idempotentReplay'])
        self.assertEqual(first.data['saleId'], second.data['saleId'])
        self.assertEqual(Sale.objects.count(), 1)
        sale = Sale.objects.get()
        self.assertEqual(str(sale.total), '50.00')
        self.assertEqual(sale.customer_name, 'Demo Buyer')
        self.assertEqual(sale.branch_id, self.branch.id)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(StockMovement.objects.count(), 1)
        self.assertEqual(BranchStockMovement.objects.count(), 1)
        self.product.refresh_from_db()
        self.inventory.refresh_from_db()
        self.assertEqual(self.product.stock, 9)
        self.assertEqual(self.inventory.stock, 4)
        self.assertEqual(self.inventory.reserved_stock, 1)

    def test_cash_confirmation_and_exact_amount_are_required(self):
        for changes in ({'cashReceived': False}, {'amountReceived': '49.00'}, {'unitPrice': '1.00'}):
            self.assertEqual(self.submit(dict(self.payload, **changes)).status_code, 400)
        self.assert_untouched()

    def test_insufficient_branch_stock_rolls_back(self):
        BranchInventory.objects.filter(pk=self.inventory.id).update(stock=1, reserved_stock=1)
        response = self.submit()
        self.assertEqual(response.status_code, 400)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'pending')
        self.assertFalse(Sale.objects.exists())
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(StockMovement.objects.exists())

    def test_cancelled_order_cannot_complete(self):
        self.assertEqual(self.client.post(self.cancel, {}, format='json').status_code, 200)
        self.assertEqual(self.submit().status_code, 400)
        self.assertFalse(Sale.objects.exists())

    def test_completed_order_cannot_cancel(self):
        self.assertEqual(self.submit().status_code, 200)
        self.assertEqual(self.client.post(self.cancel, {}, format='json').status_code, 400)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'completed')

    def test_final_order_save_failure_rolls_back_sale_and_stock(self):
        with patch.object(StorefrontOrder, 'save', side_effect=ValidationError('Simulated final write failure')):
            self.assertEqual(self.submit().status_code, 400)
        self.assert_untouched()

    def test_anonymous_completion_is_denied(self):
        self.client.force_authenticate(user=None)
        self.assertIn(self.submit().status_code, (401, 403))
        self.assert_untouched()

    def test_inactive_product_cannot_complete(self):
        Product.objects.filter(pk=self.product.id).update(is_active=False)
        self.assertEqual(self.submit().status_code, 400)
        self.assert_untouched()
