from datetime import timedelta
import shutil
import tempfile
from unittest.mock import Mock, patch

from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from integrations.provider_credentials import save_provider_credential
from inventory.models import ProductVideo

from . import test_listings
from .models import SocialPublishingJob


@override_settings(
    ALLOWED_HOSTS=['testserver', 'localhost'],
    META_APP_SECRET='test-meta-secret',
    META_GRAPH_API_VERSION='v26.0',
    META_INSTAGRAM_MEDIA_BASE_URL='https://media.stockflow.test',
    STOCKFLOW_PUBLIC_BASE_URL='https://shops.stockflow.test',
)
class InstagramVideoDeliveryTests(TestCase):
    def setUp(self):
        test_listings.ShopListingApiTests.setUp(self)
        self.directory = tempfile.mkdtemp(prefix='sf-instagram-video-test-')
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
            content_type='video/mp4', extension='mp4', size_bytes=76,
            uploaded_by=self.owner,
        )

        self.shop.is_published = True
        self.shop.save()
        self.social = f'/api/businesses/{self.business.id}/storefront/social/'
        self.client.patch(self.social + 'channels/instagram/', {'autoPublish': True}, format='json')
        self.client.put(
            self.url,
            {'isPublished': True, 'description': 'Reel product'},
            format='json',
        )
        self.job = SocialPublishingJob.objects.get(channel__platform='instagram')
        self.publish_url = self.social + 'jobs/' + str(self.job.id) + '/publish-instagram/'
        save_provider_credential(
            business=self.business, category='social', provider='facebook',
            payload={
                'system_access_token': 'system-token', 'page_id': 'PAGE-1',
                'page_name': 'Test Page', 'page_access_token': 'page-token',
                'instagram_account_id': 'IG-1',
                'instagram_username': 'stockflowghana',
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

    @patch('storefront.instagram_delivery.time.sleep')
    @patch('storefront.instagram_delivery.requests.get')
    @patch('storefront.instagram_delivery.requests.post')
    def test_video_creates_reel_container_and_publishes(self, mocked_post, mocked_get, mocked_sleep):
        mocked_post.side_effect = [
            self.meta_response(200, {'id': 'REEL-CONTAINER'}),
            self.meta_response(200, {'id': 'REEL-MEDIA'}),
        ]
        mocked_get.return_value = self.meta_response(200, {'status_code': 'FINISHED'})

        response = self.client.post(self.publish_url, {}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['deliveryStatus'], 'succeeded')
        self.assertEqual(response.data['remoteContainerId'], 'REEL-CONTAINER')
        self.assertEqual(response.data['remotePostId'], 'REEL-MEDIA')

        create_args, create_kwargs = mocked_post.call_args_list[0]
        self.assertTrue(create_args[0].endswith('/IG-1/media'))
        data = create_kwargs['data']
        self.assertEqual(data['media_type'], 'REELS')
        self.assertEqual(data['share_to_feed'], 'true')
        self.assertIn('https://media.stockflow.test/api/product-videos/', data['video_url'])
        self.assertNotIn('image_url', data)
        mocked_sleep.assert_not_called()
