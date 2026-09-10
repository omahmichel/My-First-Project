import uuid
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from businesses.models import Business, Branch
from inventory.models import Product
from .models import Storefront, StorefrontListing, StorefrontActivity
from .tests import PendingStorefrontOrderTests


@override_settings(ALLOWED_HOSTS=['testserver', 'localhost'], CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'activity-tests'}})
class StorefrontActivityApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        PendingStorefrontOrderTests.setUpTestData.__func__(cls)

    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def tearDown(self):
        cache.clear()

    def payload(self):
        return {'eventId': str(uuid.uuid4()), 'sessionId': str(uuid.uuid4()), 'eventType': 'product_view', 'listingId': str(self.listing.id)}

    def post(self, data):
        return self.client.post('/api/shops/test-shop/activity/', data, format='json')

    def test_replay_is_deduplicated_without_stock_changes(self):
        data = self.payload()
        self.assertEqual(self.post(data).status_code, 201)
        replay = self.post(data)
        self.assertEqual(replay.status_code, 200)
        self.assertTrue(replay.data['idempotentReplay'])
        self.assertEqual(StorefrontActivity.objects.count(), 1)
        self.inventory.refresh_from_db()
        self.assertEqual((self.inventory.stock, self.inventory.reserved_stock), (7, 2))

    def test_conflicting_event_id_is_rejected(self):
        data = self.payload()
        self.assertEqual(self.post(data).status_code, 201)
        data['eventType'] = 'cart_add'
        self.assertEqual(self.post(data).status_code, 400)
        self.assertEqual(StorefrontActivity.objects.get().event_type, 'product_view')

    def test_product_event_requires_listing(self):
        data = self.payload()
        del data['listingId']
        self.assertEqual(self.post(data).status_code, 400)
        self.assertFalse(StorefrontActivity.objects.exists())

    def test_browser_cannot_claim_completed_order(self):
        data = self.payload()
        data['eventType'] = 'order_completed'
        self.assertEqual(self.post(data).status_code, 400)
        self.assertFalse(StorefrontActivity.objects.exists())

    def test_unpublished_shop_rejects_activity(self):
        self.shop.is_published = False
        self.shop.save()
        self.assertEqual(self.post(self.payload()).status_code, 404)
        self.assertFalse(StorefrontActivity.objects.exists())

    def test_other_business_listing_is_rejected(self):
        business = Business.objects.create(owner=self.owner, name='Other', slug='other-activity', business_type='building_materials')
        branch = Branch.objects.create(business=business, name='Main', code='MAIN', is_main=True)
        product = Product.objects.create(business=business, name='Other', sku='OTHER', category='Cement')
        shop = Storefront.objects.create(business=business, branch=branch, is_published=True)
        listing = StorefrontListing.objects.create(storefront=shop, product=product, is_published=True)
        data = self.payload()
        data['listingId'] = str(listing.id)
        self.assertEqual(self.post(data).status_code, 404)
        self.assertFalse(StorefrontActivity.objects.exists())
