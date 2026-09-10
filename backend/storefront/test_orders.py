import uuid
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from businesses.models import BusinessMembership
from inventory.models import Product, StockMovement
from sales.models import Sale, Payment
from .models import Storefront, StorefrontOrder, StorefrontOrderItem
from . import test_management


@override_settings(ALLOWED_HOSTS=['testserver', 'localhost'])
class ShopOrderManagementTests(TestCase):
    def setUp(self):
        test_management.ShopSettingsApiTests.setUp(self)
        self.shop = Storefront.objects.create(business=self.business, branch=self.branch)
        self.product = Product.objects.create(business=self.business, name='Cement', sku='CEM-ORDER', category='Cement', unit='bag', stock=10, selling_price='50.00')
        self.order = StorefrontOrder.objects.create(storefront=self.shop, branch=self.branch, idempotency_key=uuid.uuid4(), request_fingerprint='a' * 64, customer_name='Demo Buyer', customer_phone='0244000000', total='50.00')
        StorefrontOrderItem.objects.create(order=self.order, product=self.product, product_name=self.product.name, sku=self.product.sku, unit='bag', quantity=1, unit_price=self.product.selling_price, line_total=self.product.selling_price)
        self.base = f'/api/businesses/{self.business.id}/storefront/orders/'
        self.detail = self.base + str(self.order.id) + '/'
        self.cancel = self.detail + 'cancel/'

    def test_owner_sees_order_and_snapshot_details(self):
        response = self.client.get(self.base)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        response = self.client.get(self.detail)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['customerName'], 'Demo Buyer')
        self.assertEqual(response.data['items'][0]['unitPrice'], '50.00')
        self.assertNotIn('request_fingerprint', response.data)
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_cancellation_retry_does_not_change_stock_or_payments(self):
        first = self.client.post(self.cancel, {}, format='json')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data['status'], 'cancelled')
        self.assertFalse(first.data['idempotentReplay'])
        second = self.client.post(self.cancel, {}, format='json')
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.data['idempotentReplay'])
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)
        self.assertFalse(Sale.objects.exists())
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(StockMovement.objects.exists())
        self.assertEqual(StorefrontOrderItem.objects.count(), 1)

    def test_manager_can_review_and_cancel(self):
        user = get_user_model().objects.create_user(email='order-manager@example.com', password=None)
        BusinessMembership.objects.create(business=self.business, user=user, role='manager')
        self.client.force_authenticate(user)
        self.assertEqual(self.client.get(self.detail).status_code, 200)
        self.assertEqual(self.client.post(self.cancel, {}, format='json').status_code, 200)

    def test_cashier_and_outsider_cannot_access_orders(self):
        for role in ('cashier', None):
            user = get_user_model().objects.create_user(email=str(role) + '@orders.example.com', password=None)
            if role:
                BusinessMembership.objects.create(business=self.business, user=user, role=role)
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get(self.base).status_code, 404)
            self.assertEqual(self.client.get(self.detail).status_code, 404)
            self.assertEqual(self.client.post(self.cancel, {}, format='json').status_code, 404)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'pending')

    def test_anonymous_cannot_read_buyer_details(self):
        self.client.force_authenticate(user=None)
        self.assertIn(self.client.get(self.detail).status_code, (401, 403))
        self.assertIn(self.client.post(self.cancel, {}, format='json').status_code, (401, 403))

    def test_status_filter_and_unsupported_cancellation_fields(self):
        response = self.client.get(self.base, {'status': 'completed'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 0)
        self.assertEqual(self.client.get(self.base, {'status': 'unknown'}).status_code, 400)
        response = self.client.post(self.cancel, {'status': 'completed'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'pending')
