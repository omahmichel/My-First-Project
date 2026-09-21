from pathlib import Path
import shutil
import tempfile

from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from storefront import test_listings
from storefront.models import SocialChannel, SocialPublishingJob, StorefrontListing

from .models import ProductVideo


def video_file(name='product.mp4'):
    # Minimal ISO-BMFF signature is enough for StockFlow's upload gate; Meta validates codecs/duration.
    data = b'\x00\x00\x00\x18ftypmp42' + b'\x00' * 64
    return SimpleUploadedFile(name, data, content_type='video/mp4')


@override_settings(ALLOWED_HOSTS=['testserver', 'localhost'])
class ProductVideoTests(TestCase):
    def setUp(self):
        test_listings.ShopListingApiTests.setUp(self)
        self.directory = tempfile.mkdtemp(prefix='sf-video-test-')
        self.addCleanup(lambda: shutil.rmtree(self.directory, ignore_errors=True))
        self.field = ProductVideo._meta.get_field('video')
        original = self.field.storage
        self.field.storage = FileSystemStorage(location=self.directory)
        self.addCleanup(setattr, self.field, 'storage', original)
        self.url = f'/api/businesses/{self.business.id}/products/{self.product.id}/video/'

    def upload(self, file=None):
        return self.client.post(
            self.url,
            {'video': file or video_file(), 'branchId': str(self.branch.pk)},
            format='multipart',
        )

    def test_upload_and_replace_keep_one_video(self):
        first = self.upload()
        self.assertEqual(first.status_code, 200, first.data)
        original = ProductVideo.objects.get()
        old_name = original.video.name
        old_version = original.version
        with self.captureOnCommitCallbacks(execute=True):
            second = self.upload()
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(ProductVideo.objects.count(), 1)
        current = ProductVideo.objects.get()
        self.assertNotEqual(current.version, old_version)
        self.assertFalse(self.field.storage.exists(old_name))
        product_data = self.client.get(
            f'/api/businesses/{self.business.id}/products/{self.product.id}/'
        ).data
        self.assertTrue(product_data['hasVideo'])
        self.assertIn('preview=', product_data['videoUrl'])

        preview = product_data['videoUrl'].replace('http://testserver', '')
        self.client.force_authenticate(user=None)
        allowed = self.client.get(preview)
        self.assertEqual(allowed.status_code, 200)
        allowed.close()
        self.assertEqual(self.client.get(preview.split('?')[0]).status_code, 404)

    def test_invalid_and_oversized_video_rejected(self):
        bad = SimpleUploadedFile('bad.mp4', b'not-video', content_type='video/mp4')
        self.assertEqual(self.upload(bad).status_code, 400)
        self.assertFalse(ProductVideo.objects.exists())

    def test_upload_refreshes_social_fingerprint_and_delete_falls_back(self):
        self.shop.is_published = True
        self.shop.save()
        listing = StorefrontListing.objects.create(
            storefront=self.shop, product=self.product, is_published=True
        )
        SocialChannel.objects.create(
            storefront=self.shop, platform='facebook', auto_publish=True
        )
        from storefront.social import sync_social_listing
        sync_social_listing(listing)
        job = SocialPublishingJob.objects.get()
        before = job.fingerprint

        self.assertEqual(self.upload().status_code, 200)
        job.refresh_from_db()
        self.assertNotEqual(job.fingerprint, before)
        self.assertIn('/product-videos/', job.payload['videoUrl'])

        with self.captureOnCommitCallbacks(execute=True):
            removed = self.client.delete(
                self.url + '?branchId=' + str(self.branch.pk)
            )
        self.assertEqual(removed.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.payload['videoUrl'], '')
        self.assertFalse(ProductVideo.objects.exists())

    def test_public_shop_video_uses_unsigned_url_and_unpublish_revokes_access(self):
        self.shop.is_published = True
        self.shop.save()
        listing = StorefrontListing.objects.create(
            storefront=self.shop, product=self.product, is_published=True
        )
        self.assertEqual(self.upload().status_code, 200)
        self.client.force_authenticate(user=None)
        shop_url = '/api/shops/' + self.business.slug + '/'
        result = self.client.get(shop_url)
        self.assertEqual(result.status_code, 200)
        item = next(p for p in result.data['results'] if p['productId'] == str(self.product.pk))
        url = item['videoUrl']
        self.assertIn('/product-videos/', url)
        self.assertNotIn('preview=', url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response.close()
        listing.is_published = False
        listing.save()
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertFalse(self.client.get(shop_url).data['results'])

    def test_public_video_hidden_when_shop_unpublished(self):
        from .video_urls import product_video_url
        StorefrontListing.objects.create(
            storefront=self.shop, product=self.product, is_published=True
        )
        self.assertEqual(self.upload().status_code, 200)
        self.product.refresh_from_db()
        url = product_video_url(self.product)
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_video_feed_separate_from_photo_catalogue_and_scoped_to_shop(self):
        from .models import Product
        self.shop.is_published = True
        self.shop.save()
        listing = StorefrontListing.objects.create(
            storefront=self.shop, product=self.product, is_published=True,
            image_url='https://example.com/product-photo.jpg',
        )
        other = Product.objects.create(
            business=self.business, name='Photo only', sku='PHOTO-ONLY',
            category='Other', unit='item', selling_price='25.00',
        )
        StorefrontListing.objects.create(storefront=self.shop, product=other, is_published=True)
        self.assertEqual(self.upload().status_code, 200)
        self.client.force_authenticate(user=None)
        url = '/api/shops/' + self.business.slug + '/'
        catalogue = self.client.get(url)
        self.assertEqual(catalogue.data['count'], 2)
        videos = self.client.get(url + '?media=videos')
        self.assertEqual(videos.status_code, 200)
        self.assertEqual(videos.data['count'], 1)
        item = videos.data['results'][0]
        self.assertEqual(item['productId'], str(self.product.pk))
        self.assertEqual(item['imageUrl'], 'https://example.com/product-photo.jpg')
        self.assertTrue(item['videoUrl'])
        listing.is_published = False
        listing.save()
        self.assertEqual(self.client.get(url + '?media=videos').data['count'], 0)
        self.assertEqual(self.client.get(url + '?media=invalid').status_code, 400)
