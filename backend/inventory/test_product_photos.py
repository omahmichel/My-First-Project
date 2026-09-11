from io import BytesIO
from pathlib import Path
import shutil
import tempfile
from unittest.mock import patch
from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.exceptions import ValidationError
from storefront import test_listings
from storefront.models import StorefrontListing, SocialPublishingJob
from .models import ProductPhoto, StockMovement
from .photo_images import normalize_photo
from .photo_storage import product_photo_storage
from .photo_urls import product_photo_url


def image_file(name='photo.png', exif=False):
    stream = BytesIO()
    image = Image.new('RGB', (100, 60), '#a07148')
    metadata = Image.Exif()
    if exif:
        metadata[274] = 6
        metadata[315] = 'Private metadata'
    image.save(stream, format='PNG', exif=metadata)
    return SimpleUploadedFile(name, stream.getvalue(), content_type='image/png')


@override_settings(ALLOWED_HOSTS=['testserver', 'localhost'])
class ProductPhotoTests(TestCase):
    def setUp(self):
        test_listings.ShopListingApiTests.setUp(self)
        self.directory = tempfile.mkdtemp(prefix='sf-photo-test-')
        self.addCleanup(lambda: shutil.rmtree(self.directory, ignore_errors=True))
        self.field = ProductPhoto._meta.get_field('image')
        original = self.field.storage
        from django.core.files.storage import FileSystemStorage
        self.field.storage = FileSystemStorage(location=self.directory)
        self.addCleanup(setattr, self.field, 'storage', original)
        self.url = f'/api/businesses/{self.business.id}/products/{self.product.id}/'
        self.photo_url = self.url + 'photo/'

    def upload(self, image=None, suffix=''):
        return self.client.post(self.photo_url + suffix, {'image': image or image_file(), 'branchId': str(self.branch.pk)}, format='multipart')

    def test_upload_attaches_to_product_without_changing_stock(self):
        old_stock = self.product.stock
        movements = StockMovement.objects.count()
        response = self.upload()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(ProductPhoto.objects.get().product_id, self.product.pk)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, old_stock)
        self.assertEqual(StockMovement.objects.count(), movements)
        data = self.client.get(self.url).data
        self.assertIn('preview=', data['imageUrl'])

    def test_prepare_returns_jpeg_without_persisting(self):
        response = self.upload(suffix='prepare/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/jpeg')
        self.assertFalse(ProductPhoto.objects.exists())
        self.assertEqual(list(Path(self.directory).rglob('*.jpg')), [])

    def test_draft_photo_requires_signed_preview(self):
        response = self.upload()
        preview = response.data['imageUrl'].replace('http://testserver', '')
        self.client.force_authenticate(user=None)
        allowed = self.client.get(preview)
        self.assertEqual(allowed.status_code, 200)
        allowed.close()
        self.assertEqual(self.client.get(preview.split('?')[0]).status_code, 404)
        self.assertEqual(self.client.get(preview + 'invalid').status_code, 404)

    def test_public_photo_follows_shop_visibility(self):
        self.upload()
        self.shop.is_published = True
        self.shop.save()
        StorefrontListing.objects.create(storefront=self.shop, product=self.product, is_published=True)
        self.product.refresh_from_db()
        url = product_photo_url(self.product)
        self.client.force_authenticate(user=None)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response.close()
        self.shop.is_published = False
        self.shop.save()
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_replace_keeps_one_photo_and_removes_old_file_after_commit(self):
        self.upload()
        original = ProductPhoto.objects.get()
        old_name = original.image.name
        old_version = original.version
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.upload().status_code, 200)
        self.assertEqual(ProductPhoto.objects.count(), 1)
        self.assertNotEqual(ProductPhoto.objects.get().version, old_version)
        self.assertFalse(self.field.storage.exists(old_name))

    def test_invalid_image_rejected(self):
        response = self.upload(SimpleUploadedFile('fake.jpg', b'not an image', content_type='image/jpeg'))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ProductPhoto.objects.exists())

    def test_oversized_image_rejected(self):
        with patch('inventory.photo_images.MAX_UPLOAD_BYTES', 5):
            self.assertEqual(self.upload().status_code, 400)
        self.assertFalse(ProductPhoto.objects.exists())

    def test_orientation_and_metadata_are_normalized(self):
        data = normalize_photo(image_file(exif=True))
        with Image.open(BytesIO(data)) as photo:
            self.assertEqual(photo.format, 'JPEG')
            self.assertEqual(photo.size, (60, 100))
            self.assertFalse(photo.getexif())

    def test_heic_conversion(self):
        from pillow_heif import register_heif_opener
        register_heif_opener()
        raw = BytesIO()
        Image.new('RGB', (64, 64), 'blue').save(raw, format='HEIF')
        data = normalize_photo(SimpleUploadedFile('phone.heic', raw.getvalue()))
        with Image.open(BytesIO(data)) as image:
            self.assertEqual(image.format, 'JPEG')

    def test_outsider_and_anonymous_denied(self):
        user = get_user_model().objects.create_user(email='photo-outsider@example.com', password=None)
        self.client.force_authenticate(user)
        self.assertEqual(self.upload().status_code, 404)
        self.client.force_authenticate(user=None)
        self.assertIn(self.upload().status_code, (401, 403))
        self.assertFalse(ProductPhoto.objects.exists())

    def test_cashier_cannot_upload(self):
        with patch('inventory.views.get_business_and_role_for_user', return_value=(self.business, 'cashier')):
            self.assertEqual(self.upload().status_code, 403)
        self.assertFalse(ProductPhoto.objects.exists())

    def test_stock_field_cannot_be_smuggled_into_upload(self):
        response = self.client.post(self.photo_url, {'image': image_file(), 'stock': '999'}, format='multipart')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ProductPhoto.objects.exists())

    def test_public_catalogue_and_social_job_use_uploaded_photo(self):
        self.shop.is_published = True
        self.shop.save()
        StorefrontListing.objects.create(storefront=self.shop, product=self.product, is_published=True)
        from storefront.models import SocialChannel
        SocialChannel.objects.create(storefront=self.shop, platform='facebook', auto_publish=True)
        self.upload()
        self.assertIn('/product-photos/', SocialPublishingJob.objects.get().payload['imageUrl'])
        response = self.client.get('/api/shops/' + self.business.slug + '/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('/product-photos/', response.data['results'][0]['imageUrl'])
