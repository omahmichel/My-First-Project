from io import BytesIO
from pathlib import Path
import shutil
import tempfile
from unittest.mock import Mock, patch

from PIL import Image
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from datetime import timedelta
from django.utils import timezone

from integrations.provider_credentials import save_provider_credential
from inventory.models import ProductPhoto

from . import test_listings
from .models import SocialPublishingJob


@override_settings(
    ALLOWED_HOSTS=['testserver', 'localhost'],
    META_APP_SECRET='test-meta-secret',
    META_GRAPH_API_VERSION='v26.0',
    STOCKFLOW_PUBLIC_BASE_URL='https://shops.stockflow.test',
)
class FacebookPhotoWhatsAppDeliveryTests(TestCase):
    def setUp(self):
        test_listings.ShopListingApiTests.setUp(self)

        self.directory = tempfile.mkdtemp(prefix='sf-facebook-photo-test-')
        self.addCleanup(lambda: shutil.rmtree(self.directory, ignore_errors=True))
        image_field = ProductPhoto._meta.get_field('image')
        original_storage = image_field.storage
        image_field.storage = FileSystemStorage(location=self.directory)
        self.addCleanup(setattr, image_field, 'storage', original_storage)

        stream = BytesIO()
        Image.new('RGB', (80, 60), '#9b8c7a').save(stream, format='JPEG')
        ProductPhoto.objects.create(
            product=self.product,
            image=SimpleUploadedFile(
                'product.jpg',
                stream.getvalue(),
                content_type='image/jpeg',
            ),
            uploaded_by=self.owner,
        )

        self.shop.is_published = True
        self.shop.whatsapp_enabled = True
        self.shop.whatsapp_phone = '0542777495'
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
                {'isPublished': True, 'description': 'Quality tile'},
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
                'page_name': 'StockFlow Test Shop',
                'page_access_token': 'page-token',
                'graph_api_version': 'v26.0',
            },
            created_by=self.owner,
            access_expires_at=timezone.now() + timedelta(days=30),
        )

    @staticmethod
    def meta_response(payload):
        response = Mock()
        response.status_code = 200
        response.json.return_value = payload
        return response

    @patch('storefront.facebook_delivery.requests.post')
    def test_product_photo_is_uploaded_and_whatsapp_link_is_in_caption(self, mocked_post):
        mocked_post.return_value = self.meta_response({
            'id': 'PHOTO-123',
            'post_id': 'PAGE-1_789',
        })

        response = self.client.post(self.publish_url, {}, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['deliveryStatus'], 'succeeded')
        self.assertEqual(response.data['remotePostId'], 'PAGE-1_789')
        self.assertEqual(mocked_post.call_count, 1)

        args, kwargs = mocked_post.call_args
        self.assertTrue(args[0].endswith('/PAGE-1/photos'))
        self.assertIn('files', kwargs)
        self.assertIn('source', kwargs['files'])
        self.assertEqual(kwargs['files']['source'][0], 'product.jpg')
        self.assertEqual(kwargs['files']['source'][2], 'image/jpeg')

        caption = kwargs['data']['caption']
        self.assertIn('Shop online:', caption)
        self.assertIn(
            'https://shops.stockflow.test/shops/' + self.business.slug,
            caption,
        )
        self.assertIn('Enquire on WhatsApp:', caption)
        self.assertIn('https://wa.me/233542777495?text=', caption)
        self.assertIn('GH₵', caption)
        self.assertNotIn('page-token', str(response.data))

    @patch('storefront.facebook_delivery.requests.post')
    def test_photo_response_uses_photo_id_when_meta_omits_post_id(self, mocked_post):
        mocked_post.return_value = self.meta_response({'id': 'PHOTO-ONLY-123'})

        response = self.client.post(self.publish_url, {}, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['deliveryStatus'], 'succeeded')
        self.assertEqual(response.data['remotePostId'], 'PHOTO-ONLY-123')
