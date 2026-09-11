from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from businesses.models import Business, Branch
from inventory.models import Product
from sales.models import Sale, Payment
from .models import Storefront, StorefrontListing, StorefrontOrder
from .tests import PendingStorefrontOrderTests


@override_settings(
    ALLOWED_HOSTS=['testserver', 'localhost'],
    CACHES={'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'storefront-public-api-tests',
    }},
)
class PublicStorefrontApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        PendingStorefrontOrderTests.setUpTestData.__func__(cls)

    payload = PendingStorefrontOrderTests.payload

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.url = '/api/shops/test-shop/'

    def tearDown(self):
        cache.clear()

    def test_catalogue_exposes_only_public_fields(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(set(response.data['shop']), {
            'name', 'slug', 'introduction', 'contactPhone',
            'whatsappEnabled', 'whatsappPhone', 'currency',
        })
        self.assertFalse(response.data['shop']['whatsappEnabled'])
        self.assertEqual(response.data['shop']['whatsappPhone'], '')
        product = response.data['results'][0]
        self.assertEqual(set(product), {
            'listingId', 'productId', 'name', 'category', 'brand', 'unit',
            'price', 'currency', 'size', 'color', 'designCode', 'styleCode',
            'description', 'imageUrl', 'availableQuantity', 'inStock',
        })
        self.assertEqual(product['price'], '50.00')
        self.assertEqual(product['availableQuantity'], 5)

    def test_anonymous_order_and_retry_return_no_buyer_details(self):
        payload = self.payload()
        first = self.client.post(self.url + 'orders/', payload, format='json')
        self.assertEqual(first.status_code, 201)
        self.assertEqual(set(first.data), {'orderId', 'status', 'total', 'currency', 'idempotentReplay'})
        self.assertEqual(first.data['status'], 'pending')
        self.assertEqual(first.data['total'], '100.00')
        second = self.client.post(self.url + 'orders/', payload, format='json')
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.data['idempotentReplay'])
        self.assertEqual(first.data['orderId'], second.data['orderId'])
        self.assertEqual(StorefrontOrder.objects.count(), 1)
        self.assertEqual(Sale.objects.count(), 0)
        self.assertEqual(Payment.objects.count(), 0)
        self.inventory.refresh_from_db()
        self.assertEqual((self.inventory.stock, self.inventory.reserved_stock), (7, 2))

    def test_unpublished_shop_blocks_browsing_and_orders(self):
        self.shop.is_published = False
        self.shop.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)
        response = self.client.post(self.url + 'orders/', self.payload(), format='json')
        self.assertEqual(response.status_code, 404)
        self.assertFalse(StorefrontOrder.objects.exists())

    def test_expired_business_blocks_browsing_and_orders(self):
        self.business.trial_ends_at = timezone.now() - timedelta(days=1)
        self.business.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)
        response = self.client.post(self.url + 'orders/', self.payload(), format='json')
        self.assertEqual(response.status_code, 404)
        self.assertFalse(StorefrontOrder.objects.exists())

    def test_other_business_products_are_not_visible_or_orderable(self):
        other = Business.objects.create(owner=self.owner, name='Other Shop', slug='other-shop', business_type='building_materials')
        branch = Branch.objects.create(business=other, name='Main', code='MAIN', is_main=True)
        product = Product.objects.create(business=other, name='Private Other Product', sku='OTHER-1', category='Cement', selling_price=10, stock=100)
        shop = Storefront.objects.create(business=other, branch=branch, is_published=True)
        StorefrontListing.objects.create(storefront=shop, product=product, is_published=True)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['productId'], str(self.product.id))
        payload = self.payload()
        payload['items'][0]['productId'] = str(product.id)
        response = self.client.post(self.url + 'orders/', payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(StorefrontOrder.objects.exists())

    def test_search_and_unpublished_listing_filter(self):
        response = self.client.get(self.url, {'q': 'Cement'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        response = self.client.get(self.url, {'q': 'no-such-product'})
        self.assertEqual(response.data['count'], 0)
        self.listing.is_published = False
        self.listing.save()
        response = self.client.get(self.url)
        self.assertEqual(response.data['count'], 0)

    def test_order_endpoint_rejects_buyer_price(self):
        payload = self.payload()
        payload['items'][0]['unitPrice'] = '0.01'
        response = self.client.post(self.url + 'orders/', payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(StorefrontOrder.objects.exists())

    def test_order_requests_are_throttled(self):
        for attempt in range(10):
            response = self.client.post(self.url + 'orders/', {}, format='json')
            self.assertEqual(response.status_code, 400)
        response = self.client.post(self.url + 'orders/', {}, format='json')
        self.assertEqual(response.status_code, 429)
        self.assertFalse(StorefrontOrder.objects.exists())
