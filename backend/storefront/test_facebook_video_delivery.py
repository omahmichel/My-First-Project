from datetime import timedelta
import shutil
import tempfile
from unittest.mock import Mock, patch

import requests
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from integrations.provider_credentials import save_provider_credential
from inventory.models import ProductVideo

from . import test_listings
from .models import SocialDeliveryAttempt, SocialPublishingJob


@override_settings(
    ALLOWED_HOSTS=['testserver', 'localhost'],
    META_APP_SECRET='test-meta-secret',
    META_GRAPH_API_VERSION='v26.0',
)
class FacebookVideoDeliveryTests(TestCase):
    def setUp(self):
        test_listings.ShopListingApiTests.setUp(self)
        self.directory = tempfile.mkdtemp(prefix='sf-facebook-video-test-')
        self.addCleanup(lambda: shutil.rmtree(self.directory, ignore_errors=True))
        field = ProductVideo._meta.get_field('video')
        original = field.storage
        field.storage = FileSystemStorage(location=self.directory)
        self.addCleanup(setattr, field, 'storage', original)
        ProductVideo.objects.create(
            product=self.product,
            video=SimpleUploadedFile(
                'product.mp4',
                b'\x00\x00\x00\x18ftypmp42' + b'\x00' * 64,
                content_type='video/mp4',
            ),
            content_type='video/mp4',
            extension='mp4',
            size_bytes=76,
            uploaded_by=self.owner,
        )

        self.shop.is_published = True
        self.shop.save()
        self.social = f'/api/businesses/{self.business.id}/storefront/social/'
        self.client.patch(self.social + 'channels/facebook/', {'autoPublish': True}, format='json')
        self.client.put(
            self.url,
            {'isPublished': True, 'description': 'Video product'},
            format='json',
        )
        self.job = SocialPublishingJob.objects.get(channel__platform='facebook')
        self.publish_url = self.social + 'jobs/' + str(self.job.id) + '/publish-facebook/'
        save_provider_credential(
            business=self.business, category='social', provider='facebook',
            payload={
                'system_access_token': 'system-token',
                'page_id': 'PAGE-1', 'page_name': 'Test Page',
                'page_access_token': 'page-token', 'graph_api_version': 'v26.0',
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
    def test_video_uses_reels_flow_and_repeat_is_idempotent(self, mocked_post):
        mocked_post.side_effect = [
            self.meta_response(200, {'video_id': 'VIDEO-123', 'upload_url': 'ignored'}),
            self.meta_response(200, {'success': True}),
            self.meta_response(200, {'success': True}),
        ]

        first = self.client.post(self.publish_url, {}, format='json')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data['deliveryStatus'], 'succeeded')
        self.assertEqual(first.data['remotePostId'], 'VIDEO-123')
        self.assertEqual(first.data['remoteContainerId'], 'VIDEO-123')
        self.assertEqual(mocked_post.call_count, 3)

        create_args, create_kwargs = mocked_post.call_args_list[0]
        self.assertTrue(create_args[0].endswith('/PAGE-1/video_reels'))
        self.assertEqual(create_kwargs['data']['upload_phase'], 'start')

        upload_args, upload_kwargs = mocked_post.call_args_list[1]
        self.assertEqual(
            upload_args[0],
            'https://rupload.facebook.com/video-upload/v26.0/VIDEO-123',
        )
        self.assertEqual(upload_kwargs['headers']['Authorization'], 'OAuth page-token')
        self.assertEqual(upload_kwargs['headers']['file_size'], '76')

        finish_args, finish_kwargs = mocked_post.call_args_list[2]
        self.assertTrue(finish_args[0].endswith('/PAGE-1/video_reels'))
        self.assertEqual(finish_kwargs['data']['upload_phase'], 'finish')
        self.assertEqual(finish_kwargs['data']['video_state'], 'PUBLISHED')
        self.assertIn('Video product', finish_kwargs['data']['description'])

        second = self.client.post(self.publish_url, {}, format='json')
        self.assertEqual(second.data['deliveryStatus'], 'succeeded')
        self.assertEqual(mocked_post.call_count, 3)

    @patch('storefront.facebook_delivery.requests.post')
    def test_publish_network_uncertainty_blocks_retry(self, mocked_post):
        mocked_post.side_effect = [
            self.meta_response(200, {'video_id': 'VIDEO-UNKNOWN'}),
            self.meta_response(200, {'success': True}),
            requests.Timeout('finish timeout'),
        ]
        first = self.client.post(self.publish_url, {}, format='json')
        self.assertEqual(first.data['deliveryStatus'], 'unknown')
        second = self.client.post(self.publish_url, {}, format='json')
        self.assertEqual(second.status_code, 409)
        self.assertEqual(mocked_post.call_count, 3)
        self.assertEqual(SocialDeliveryAttempt.objects.get().provider_container_id, 'VIDEO-UNKNOWN')
