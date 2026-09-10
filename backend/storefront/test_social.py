from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from businesses.models import Business
from . import test_listings
from .models import StorefrontListing, SocialChannel, SocialPublishingJob
from .social import sync_social_shop


@override_settings(ALLOWED_HOSTS=['testserver', 'localhost'])
class SocialPublishingTests(TestCase):
    def setUp(self):
        test_listings.ShopListingApiTests.setUp(self)
        self.shop.is_published = True
        self.shop.save()
        self.social = f'/api/businesses/{self.business.id}/storefront/social/'

    def enable(self, platform='facebook', enabled=True):
        return self.client.patch(self.social + 'channels/' + platform + '/', {'autoPublish': enabled}, format='json')

    def publish(self, **extra):
        return self.client.put(self.url, {'isPublished': True, **extra}, format='json')

    def test_defaults_off_and_no_secrets(self):
        response = self.client.get(self.social + 'channels/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['channels']), 4)
        self.assertTrue(all(not c['autoPublish'] and not c['deliveryAvailable'] for c in response.data['channels']))
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(self.publish().status_code, 201)
        self.assertFalse(SocialPublishingJob.objects.exists())

    def test_each_platform_can_prepare_a_job(self):
        for platform in SocialChannel.Platform.values:
            self.assertEqual(self.enable(platform).status_code, 200)
        self.assertEqual(self.publish().status_code, 201)
        self.assertEqual(SocialPublishingJob.objects.count(), 4)
        self.assertTrue(all(j.status == 'pending_connection' for j in SocialPublishingJob.objects.all()))

    def test_repeat_save_and_edit_keep_one_current_job(self):
        self.enable()
        self.publish()
        original = SocialPublishingJob.objects.get()
        self.publish()
        self.assertEqual(SocialPublishingJob.objects.count(), 1)
        self.publish(description='Updated description')
        current = SocialPublishingJob.objects.get()
        self.assertEqual(current.pk, original.pk)
        self.assertNotEqual(current.fingerprint, original.fingerprint)
        self.assertEqual(current.payload['description'], 'Updated description')
        self.assertEqual(current.payload['currency'], 'GHS')
        self.assertNotIn('costPrice', current.payload)

    def test_enabling_includes_existing_published_listings(self):
        self.publish()
        self.enable()
        self.assertEqual(SocialPublishingJob.objects.count(), 1)

    def test_disable_cancel_and_reenable(self):
        self.enable()
        self.publish()
        self.enable(enabled=False)
        self.assertEqual(SocialPublishingJob.objects.get().status, 'cancelled')
        self.enable()
        self.assertEqual(SocialPublishingJob.objects.get().status, 'pending_connection')
        self.assertEqual(SocialPublishingJob.objects.count(), 1)

    def test_unpublish_listing_cancels(self):
        self.enable()
        self.publish()
        response = self.client.put(self.url, {'isPublished': False}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SocialPublishingJob.objects.get().status, 'cancelled')

    def test_shop_publish_controls_jobs(self):
        self.enable()
        self.publish()
        url = f'/api/businesses/{self.business.id}/storefront/settings/'
        self.assertEqual(self.client.patch(url, {'isPublished': False}, format='json').status_code, 200)
        self.assertEqual(SocialPublishingJob.objects.get().status, 'cancelled')
        self.assertEqual(self.client.patch(url, {'isPublished': True}, format='json').status_code, 200)
        self.assertEqual(SocialPublishingJob.objects.get().status, 'pending_connection')

    def test_draft_shop_does_not_queue(self):
        self.shop.is_published = False
        self.shop.save()
        self.enable()
        self.publish()
        self.assertFalse(SocialPublishingJob.objects.exists())

    def test_inactive_product_is_cancelled_on_reconciliation(self):
        self.enable()
        self.publish()
        self.product.is_active = False
        self.product.save()
        sync_social_shop(self.shop)
        self.assertEqual(SocialPublishingJob.objects.get().status, 'cancelled')

    def test_unknown_platform_and_connection_fields_rejected(self):
        self.assertEqual(self.enable('unknown').status_code, 404)
        response = self.client.patch(self.social + 'channels/facebook/', {'autoPublish': True, 'connectionStatus': 'connected'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(SocialChannel.objects.exists())

    def test_outsider_and_anonymous_rejected(self):
        outsider = get_user_model().objects.create_user(email='social-outsider@example.com', password=None)
        self.client.force_authenticate(outsider)
        self.assertEqual(self.enable().status_code, 404)
        self.assertEqual(self.client.get(self.social + 'jobs/').status_code, 404)
        self.client.force_authenticate(user=None)
        self.assertIn(self.enable().status_code, (401, 403))

    def test_other_owned_business_does_not_see_jobs(self):
        self.enable()
        self.publish()
        other = Business.objects.create(owner=self.owner, name='Other social', slug='other-social', business_type='building_materials')
        response = self.client.get(f'/api/businesses/{other.pk}/storefront/social/jobs/')
        self.assertEqual(response.status_code, 404)
        response = self.client.get(self.social + 'jobs/')
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertNotIn('payload', response.data['results'][0])
