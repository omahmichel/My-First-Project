from datetime import timedelta
from unittest.mock import Mock, patch

import requests
from django.test import TestCase, override_settings
from django.utils import timezone

from integrations.provider_credentials import delete_provider_credential, save_provider_credential

from . import test_listings
from .models import SocialDeliveryAttempt, SocialPublishingJob


@override_settings(
    ALLOWED_HOSTS=['testserver', 'localhost'],
    META_APP_SECRET='test-meta-secret',
    META_GRAPH_API_VERSION='v26.0',
)
class FacebookDeliveryTests(TestCase):
    def setUp(self):
        test_listings.ShopListingApiTests.setUp(self)
        self.shop.is_published = True
        self.shop.save()

        self.social = f'/api/businesses/{self.business.id}/storefront/social/'
        self.assertEqual(
            self.client.patch(
                self.social + 'channels/facebook/',
                {'autoPublish': True},
                format='json',
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.put(
                self.url,
                {'isPublished': True, 'description': 'Quality cement'},
                format='json',
            ).status_code,
            201,
        )
        self.job = SocialPublishingJob.objects.get()
        self.publish_url = self.social + 'jobs/' + str(self.job.id) + '/publish-facebook/'

        save_provider_credential(
            business=self.business,
            category='social',
            provider='facebook',
            payload={
                'system_access_token': 'system-token',
                'page_id': 'PAGE-1',
                'page_name': 'Test Page',
                'page_access_token': 'page-token',
                'graph_api_version': 'v26.0',
            },
            created_by=self.owner,
            access_expires_at=timezone.now() + timedelta(days=30),
        )

    @staticmethod
    def meta_response(status_code, payload):
        response = Mock()
        response.status_code = status_code
        response.json.return_value = payload
        return response

    @patch('storefront.facebook_delivery.requests.post')
    def test_success_is_recorded_and_repeat_is_idempotent(self, mocked_post):
        mocked_post.return_value = self.meta_response(200, {'id': 'PAGE-1_123'})

        first = self.client.post(self.publish_url, {}, format='json')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data['deliveryStatus'], 'succeeded')
        self.assertEqual(first.data['remotePostId'], 'PAGE-1_123')
        self.assertEqual(mocked_post.call_count, 1)

        second = self.client.post(self.publish_url, {}, format='json')
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data['deliveryStatus'], 'succeeded')
        self.assertEqual(mocked_post.call_count, 1)

        attempt = SocialDeliveryAttempt.objects.get()
        self.assertEqual(attempt.attempt_count, 1)
        self.assertNotIn('page-token', str(first.data))

    @patch('storefront.facebook_delivery.requests.post')
    def test_definite_meta_rejection_can_be_retried(self, mocked_post):
        mocked_post.side_effect = [
            self.meta_response(400, {'error': {'code': 200}}),
            self.meta_response(200, {'id': 'PAGE-1_456'}),
        ]

        first = self.client.post(self.publish_url, {}, format='json')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data['deliveryStatus'], 'failed')
        self.assertIn('Meta code 200', first.data['error'])

        second = self.client.post(self.publish_url, {}, format='json')
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data['deliveryStatus'], 'succeeded')
        self.assertEqual(mocked_post.call_count, 2)
        self.assertEqual(SocialDeliveryAttempt.objects.get().attempt_count, 2)

    @patch('storefront.facebook_delivery.requests.post')
    def test_network_uncertainty_blocks_automatic_retry(self, mocked_post):
        mocked_post.side_effect = requests.Timeout('timeout')

        first = self.client.post(self.publish_url, {}, format='json')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data['deliveryStatus'], 'unknown')
        self.assertEqual(mocked_post.call_count, 1)

        second = self.client.post(self.publish_url, {}, format='json')
        self.assertEqual(second.status_code, 409)
        self.assertEqual(mocked_post.call_count, 1)

    def test_connection_is_required(self):
        delete_provider_credential(
            business=self.business,
            category='social',
            provider='facebook',
        )
        response = self.client.post(self.publish_url, {}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(SocialDeliveryAttempt.objects.exists())
