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
    STOCKFLOW_PUBLIC_BASE_URL='https://shops.stockflow.test',
)
class InstagramDeliveryTests(TestCase):
    def setUp(self):
        test_listings.ShopListingApiTests.setUp(self)
        self.shop.is_published = True
        self.shop.whatsapp_enabled = True
        self.shop.whatsapp_phone = '0542777495'
        self.shop.save()

        self.social = f'/api/businesses/{self.business.id}/storefront/social/'
        self.assertEqual(
            self.client.patch(
                self.social + 'channels/instagram/',
                {'autoPublish': True},
                format='json',
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.put(
                self.url,
                {
                    'isPublished': True,
                    'description': 'Quality tile',
                    'imageUrl': 'https://cdn.example.com/products/tile.jpg',
                },
                format='json',
            ).status_code,
            201,
        )
        self.job = SocialPublishingJob.objects.get(channel__platform='instagram')
        self.publish_url = self.social + 'jobs/' + str(self.job.id) + '/publish-instagram/'

        save_provider_credential(
            business=self.business,
            category='social',
            provider='facebook',
            payload={
                'system_access_token': 'system-token',
                'page_id': 'PAGE-1',
                'page_name': 'StockFlow Test Shop',
                'page_access_token': 'page-token',
                'instagram_account_id': 'IG-1',
                'instagram_username': 'stockflowghana',
                'graph_api_version': 'v26.0',
            },
            created_by=self.owner,
            access_expires_at=timezone.now() + timedelta(days=30),
        )

        self.container_status_patcher = patch(
            'storefront.instagram_delivery.requests.get'
        )
        self.mocked_get = self.container_status_patcher.start()
        self.addCleanup(self.container_status_patcher.stop)
        self.mocked_get.return_value = self.meta_response(
            200,
            {
                'status_code': 'FINISHED',
                'status': 'Finished: Media is ready to be published.',
            },
        )

    @staticmethod
    def meta_response(status_code, payload):
        response = Mock()
        response.status_code = status_code
        response.json.return_value = payload
        return response

    @patch('storefront.instagram_delivery.requests.post')
    def test_photo_container_publish_is_recorded_and_repeat_is_idempotent(self, mocked_post):
        mocked_post.side_effect = [
            self.meta_response(200, {'id': 'CONTAINER-123'}),
            self.meta_response(200, {'id': 'MEDIA-456'}),
        ]

        first = self.client.post(self.publish_url, {}, format='json')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data['deliveryStatus'], 'succeeded')
        self.assertEqual(first.data['remoteContainerId'], 'CONTAINER-123')
        self.assertEqual(first.data['remotePostId'], 'MEDIA-456')
        self.assertEqual(mocked_post.call_count, 2)
        self.assertEqual(self.mocked_get.call_count, 1)

        status_args, status_kwargs = self.mocked_get.call_args
        self.assertTrue(status_args[0].endswith('/CONTAINER-123'))
        self.assertEqual(status_kwargs['params']['fields'], 'status_code,status')

        create_args, create_kwargs = mocked_post.call_args_list[0]
        self.assertTrue(create_args[0].endswith('/IG-1/media'))
        self.assertEqual(create_kwargs['data']['image_url'], 'https://cdn.example.com/products/tile.jpg')
        caption = create_kwargs['data']['caption']
        self.assertIn('GH₵', caption)
        self.assertIn(
            'Shop online or enquire on WhatsApp using the links in our profile.',
            caption,
        )
        self.assertNotIn('https://wa.me/', caption)
        self.assertNotIn('https://shops.stockflow.test/', caption)

        publish_args, publish_kwargs = mocked_post.call_args_list[1]
        self.assertTrue(publish_args[0].endswith('/IG-1/media_publish'))
        self.assertEqual(publish_kwargs['data']['creation_id'], 'CONTAINER-123')

        second = self.client.post(self.publish_url, {}, format='json')
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data['deliveryStatus'], 'succeeded')
        self.assertEqual(mocked_post.call_count, 2)

        attempt = SocialDeliveryAttempt.objects.get()
        self.assertEqual(attempt.attempt_count, 1)
        self.assertEqual(attempt.provider_container_id, 'CONTAINER-123')
        self.assertNotIn('page-token', str(first.data))


    @patch('storefront.instagram_delivery.requests.post')
    def test_caption_omits_whatsapp_when_shop_enquiries_are_disabled(self, mocked_post):
        self.shop.whatsapp_enabled = False
        self.shop.save(update_fields=('whatsapp_enabled', 'updated_at'))
        mocked_post.side_effect = [
            self.meta_response(200, {'id': 'CONTAINER-NO-WA'}),
            self.meta_response(200, {'id': 'MEDIA-NO-WA'}),
        ]

        response = self.client.post(self.publish_url, {}, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['deliveryStatus'], 'succeeded')
        create_kwargs = mocked_post.call_args_list[0][1]
        caption = create_kwargs['data']['caption']
        self.assertIn('Shop online using the link in our profile.', caption)
        self.assertNotIn('Enquire on WhatsApp', caption)
        self.assertNotIn('https://wa.me/', caption)
        self.assertNotIn('https://shops.stockflow.test/', caption)

    @patch('storefront.instagram_delivery.requests.post')
    def test_definite_container_rejection_can_be_retried(self, mocked_post):
        mocked_post.side_effect = [
            self.meta_response(400, {'error': {'code': 100}}),
            self.meta_response(200, {'id': 'CONTAINER-2'}),
            self.meta_response(200, {'id': 'MEDIA-2'}),
        ]

        first = self.client.post(self.publish_url, {}, format='json')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data['deliveryStatus'], 'failed')
        self.assertIn('Meta code 100', first.data['error'])

        second = self.client.post(self.publish_url, {}, format='json')
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data['deliveryStatus'], 'succeeded')
        self.assertEqual(mocked_post.call_count, 3)
        self.assertEqual(SocialDeliveryAttempt.objects.get().attempt_count, 2)

    @patch('storefront.instagram_delivery.requests.post')
    def test_container_timeout_is_retryable_because_no_publish_request_was_sent(self, mocked_post):
        mocked_post.side_effect = [
            requests.Timeout('container timeout'),
            self.meta_response(200, {'id': 'CONTAINER-3'}),
            self.meta_response(200, {'id': 'MEDIA-3'}),
        ]

        first = self.client.post(self.publish_url, {}, format='json')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data['deliveryStatus'], 'failed')
        self.assertEqual(mocked_post.call_count, 1)

        second = self.client.post(self.publish_url, {}, format='json')
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data['deliveryStatus'], 'succeeded')
        self.assertEqual(mocked_post.call_count, 3)

    @patch('storefront.instagram_delivery.requests.post')
    def test_publish_network_uncertainty_blocks_retry(self, mocked_post):
        mocked_post.side_effect = [
            self.meta_response(200, {'id': 'CONTAINER-4'}),
            requests.Timeout('publish timeout'),
        ]

        first = self.client.post(self.publish_url, {}, format='json')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data['deliveryStatus'], 'unknown')
        self.assertEqual(first.data['remoteContainerId'], 'CONTAINER-4')
        self.assertEqual(mocked_post.call_count, 2)

        second = self.client.post(self.publish_url, {}, format='json')
        self.assertEqual(second.status_code, 409)
        self.assertEqual(mocked_post.call_count, 2)


    @patch('storefront.instagram_delivery.time.sleep')
    @patch('storefront.instagram_delivery.requests.post')
    def test_container_waits_until_finished_before_publish(self, mocked_post, mocked_sleep):
        mocked_post.side_effect = [
            self.meta_response(200, {'id': 'CONTAINER-WAIT'}),
            self.meta_response(200, {'id': 'MEDIA-WAIT'}),
        ]
        self.mocked_get.side_effect = [
            self.meta_response(200, {'status_code': 'IN_PROGRESS', 'status': 'Processing'}),
            self.meta_response(200, {'status_code': 'FINISHED', 'status': 'Finished'}),
        ]

        response = self.client.post(self.publish_url, {}, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['deliveryStatus'], 'succeeded')
        self.assertEqual(self.mocked_get.call_count, 2)
        mocked_sleep.assert_called_once_with(2)
        self.assertEqual(mocked_post.call_count, 2)

    @patch('storefront.instagram_delivery.requests.post')
    def test_container_error_blocks_publish_and_remains_retryable(self, mocked_post):
        mocked_post.side_effect = [
            self.meta_response(200, {'id': 'CONTAINER-ERROR'}),
            self.meta_response(200, {'id': 'CONTAINER-RECOVER'}),
            self.meta_response(200, {'id': 'MEDIA-RECOVER'}),
        ]
        self.mocked_get.side_effect = [
            self.meta_response(200, {'status_code': 'ERROR', 'status': 'Failed'}),
            self.meta_response(200, {'status_code': 'FINISHED', 'status': 'Finished'}),
        ]

        first = self.client.post(self.publish_url, {}, format='json')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data['deliveryStatus'], 'failed')
        self.assertIn('status ERROR', first.data['error'])
        self.assertEqual(mocked_post.call_count, 1)

        second = self.client.post(self.publish_url, {}, format='json')
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data['deliveryStatus'], 'succeeded')
        self.assertEqual(mocked_post.call_count, 3)
        self.assertEqual(SocialDeliveryAttempt.objects.get().attempt_count, 2)

    @patch('storefront.instagram_delivery.CONTAINER_STATUS_MAX_ATTEMPTS', 2)
    @patch('storefront.instagram_delivery.time.sleep')
    @patch('storefront.instagram_delivery.requests.post')
    def test_container_status_timeout_blocks_publish_but_can_retry(
        self,
        mocked_post,
        mocked_sleep,
    ):
        mocked_post.return_value = self.meta_response(200, {'id': 'CONTAINER-TIMEOUT'})
        self.mocked_get.side_effect = requests.Timeout('status timeout')

        response = self.client.post(self.publish_url, {}, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['deliveryStatus'], 'failed')
        self.assertIn('No publish request was sent', response.data['error'])
        self.assertEqual(mocked_post.call_count, 1)
        self.assertEqual(self.mocked_get.call_count, 2)
        mocked_sleep.assert_called_once_with(2)

    def test_connection_is_required(self):
        delete_provider_credential(
            business=self.business,
            category='social',
            provider='facebook',
        )
        response = self.client.post(self.publish_url, {}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(SocialDeliveryAttempt.objects.exists())

    @patch('storefront.instagram_delivery.requests.post')
    def test_local_only_image_fails_before_contacting_meta(self, mocked_post):
        listing = self.job.listing
        listing.image_url = ''
        listing.save(update_fields=('image_url', 'updated_at'))
        payload = dict(self.job.payload)
        payload['imageUrl'] = '/api/product-photos/example/'
        self.job.payload = payload
        self.job.save(update_fields=('payload', 'updated_at'))

        response = self.client.post(self.publish_url, {}, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['deliveryStatus'], 'failed')
        self.assertIn('publicly reachable HTTPS', response.data['error'])
        self.assertEqual(mocked_post.call_count, 0)
