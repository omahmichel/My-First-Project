from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from businesses.models import Business, Branch, BusinessMembership
from .models import Storefront


@override_settings(ALLOWED_HOSTS=['testserver', 'localhost'])
class ShopSettingsApiTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(email='shop-owner@example.com', password=None)
        self.business = Business.objects.create(owner=self.owner, name='Settings Shop', slug='settings-shop', business_type='building_materials')
        self.branch = Branch.objects.create(business=self.business, name='Main', code='MAIN', is_main=True)
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.url = f'/api/businesses/{self.business.id}/storefront/settings/'

    def test_read_does_not_create_or_publish_shop(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['configured'])
        self.assertFalse(response.data['isPublished'])
        self.assertFalse(Storefront.objects.exists())
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_owner_can_create_publish_and_unpublish(self):
        response = self.client.patch(self.url, {'branchId': str(self.branch.id), 'introduction': 'Welcome'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['isPublished'])
        response = self.client.patch(self.url, {'isPublished': True, 'contactPhone': '024 400 0000'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['isPublished'])
        self.assertEqual(response.data['contactPhone'], '0244000000')
        response = self.client.patch(self.url, {'isPublished': False}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Storefront.objects.get().is_published)

    def test_anonymous_cannot_publish(self):
        self.client.force_authenticate(user=None)
        response = self.client.patch(self.url, {'branchId': str(self.branch.id), 'isPublished': True}, format='json')
        self.assertIn(response.status_code, (401, 403))
        self.assertFalse(Storefront.objects.exists())

    def test_manager_cannot_publish(self):
        manager = get_user_model().objects.create_user(email='shop-manager@example.com', password=None)
        BusinessMembership.objects.create(business=self.business, user=manager, role='manager')
        self.client.force_authenticate(manager)
        response = self.client.patch(self.url, {'branchId': str(self.branch.id), 'isPublished': True}, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Storefront.objects.exists())

    def test_other_business_branch_is_rejected(self):
        other = Business.objects.create(owner=self.owner, name='Other', slug='other-settings', business_type='building_materials')
        branch = Branch.objects.create(business=other, name='Main', code='MAIN', is_main=True)
        response = self.client.patch(self.url, {'branchId': str(branch.id)}, format='json')
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Storefront.objects.exists())

    def test_unknown_fields_and_missing_branch_are_rejected(self):
        response = self.client.patch(self.url, {'branchId': str(self.branch.id), 'businessId': str(self.business.id)}, format='json')
        self.assertEqual(response.status_code, 400)
        response = self.client.patch(self.url, {'isPublished': True}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Storefront.objects.exists())
