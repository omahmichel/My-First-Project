from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from businesses.models import Business
from inventory.models import Product
from .models import Storefront, StorefrontListing
from . import test_management


@override_settings(ALLOWED_HOSTS=['testserver', 'localhost'])
class ShopListingApiTests(TestCase):
    def setUp(self):
        test_management.ShopSettingsApiTests.setUp(self)
        self.shop = Storefront.objects.create(business=self.business, branch=self.branch)
        self.product = Product.objects.create(business=self.business, name='Cement', sku='CEM-1', category='Cement', unit='bag', selling_price='50.00')
        self.base = f'/api/businesses/{self.business.id}/storefront/listings/'
        self.url = self.base + str(self.product.id) + '/'

    def put(self, data):
        return self.client.put(self.url, data, format='json')

    def test_owner_can_create_update_and_list_without_duplicates(self):
        response = self.put({'description': 'Quality cement'})
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.data['isPublished'])
        listing_id = response.data['listingId']
        response = self.put({'isPublished': True, 'imageUrl': 'https://example.com/cement.jpg'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['listingId'], listing_id)
        self.assertTrue(response.data['isPublished'])
        response = self.client.get(self.base)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['description'], 'Quality cement')
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertNotIn('costPrice', response.data['results'][0])

    def test_http_image_is_rejected(self):
        response = self.put({'imageUrl': 'http://example.com/cement.jpg'})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(StorefrontListing.objects.exists())

    def test_listing_endpoint_cannot_change_inventory_price(self):
        response = self.put({'price': '1.00', 'isPublished': True})
        self.assertEqual(response.status_code, 400)
        self.product.refresh_from_db()
        self.assertEqual(str(self.product.selling_price), '50.00')
        self.assertFalse(StorefrontListing.objects.exists())

    def test_inactive_product_can_be_hidden_but_not_published(self):
        self.assertEqual(self.put({'isPublished': True}).status_code, 201)
        Product.objects.filter(pk=self.product.id).update(is_active=False)
        self.assertEqual(self.put({'isPublished': True}).status_code, 400)
        self.assertEqual(self.put({'isPublished': False}).status_code, 200)
        self.assertFalse(StorefrontListing.objects.get().is_published)

    def test_other_business_product_is_rejected(self):
        other = Business.objects.create(owner=self.owner, name='Other', slug='other-listings', business_type='building_materials')
        product = Product.objects.create(business=other, name='Other cement', sku='OTHER', category='Cement')
        response = self.client.put(self.base + str(product.id) + '/', {'isPublished': True}, format='json')
        self.assertEqual(response.status_code, 404)
        self.assertFalse(StorefrontListing.objects.exists())

    def test_outsider_and_anonymous_cannot_manage_listings(self):
        outsider = get_user_model().objects.create_user(email='listing-outsider@example.com', password=None)
        self.client.force_authenticate(outsider)
        self.assertEqual(self.put({'isPublished': True}).status_code, 404)
        self.assertEqual(self.client.get(self.base).status_code, 404)
        self.client.force_authenticate(user=None)
        self.assertIn(self.put({'isPublished': True}).status_code, (401, 403))
        self.assertFalse(StorefrontListing.objects.exists())
