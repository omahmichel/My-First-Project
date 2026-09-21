import shutil
import tempfile
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.test import TestCase, override_settings
from businesses.models import Business, Branch, BusinessMembership
from storefront import test_listings
from storefront.models import StorefrontListing
from .models import Product, ProductPhoto, ProductVideo
from .photo_urls import product_photo_url


@override_settings(ALLOWED_HOSTS=['testserver', 'localhost'])
class ProductPhotoDeletionTests(TestCase):
    def setUp(self):
        test_listings.ShopListingApiTests.setUp(self)
        directory = tempfile.mkdtemp(prefix='sf-photo-delete-test-')
        self.addCleanup(lambda: shutil.rmtree(directory, ignore_errors=True))
        field = ProductPhoto._meta.get_field('image')
        original = field.storage
        field.storage = FileSystemStorage(location=directory)
        self.addCleanup(lambda: setattr(field, 'storage', original))
        self.listing = StorefrontListing.objects.create(
            storefront=self.shop, product=self.product, is_published=True,
            image_url='https://example.com/old-photo.jpg')
        self.photo = ProductPhoto(product=self.product, uploaded_by=self.owner)
        self.photo.image.save('photo.jpg', ContentFile(b'photo-test'), save=True)
        self.photo_url = product_photo_url(Product.objects.select_related('uploaded_photo').get(pk=self.product.pk))
        self.delete_url = f'/api/businesses/{self.business.pk}/products/{self.product.pk}/photo/'

    def test_owner_deletes_photo_and_fallback_preserving_product_and_video(self):
        video = ProductVideo.objects.create(product=self.product, video='product-videos/retained.mp4')
        storage, name = self.photo.image.storage, self.photo.image.name
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.delete(self.delete_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['imageUrl'], '')
        self.assertFalse(ProductPhoto.objects.filter(product=self.product).exists())
        self.assertFalse(storage.exists(name))
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())
        self.assertTrue(ProductVideo.objects.filter(pk=video.pk).exists())
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.image_url, '')
        self.assertTrue(self.listing.is_published)
        self.assertEqual(self.client.get(self.photo_url).status_code, 404)
        self.assertEqual(self.client.delete(self.delete_url).status_code, 200)

    def test_link_only_photo_is_removed(self):
        self.photo.delete()
        self.assertEqual(self.client.delete(self.delete_url).status_code, 200)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.image_url, '')

    def test_guest_and_cashier_cannot_delete(self):
        self.client.force_authenticate(user=None)
        self.assertIn(self.client.delete(self.delete_url).status_code, (401, 403))
        cashier = get_user_model().objects.create_user(email='photo-cashier@example.com', password=None)
        BusinessMembership.objects.create(business=self.business, user=cashier, role='cashier')
        self.client.force_authenticate(cashier)
        self.assertEqual(self.client.delete(self.delete_url).status_code, 403)
        self.assertTrue(ProductPhoto.objects.filter(pk=self.photo.pk).exists())
        self.listing.refresh_from_db()
        self.assertTrue(self.listing.image_url)

    def test_other_business_owner_cannot_delete(self):
        other = get_user_model().objects.create_user(email='photo-other@example.com', password=None)
        Business.objects.create(owner=other, name='Other', slug='photo-other', business_type='boutique')
        self.client.force_authenticate(other)
        self.assertIn(self.client.delete(self.delete_url).status_code, (403, 404))
        self.assertTrue(ProductPhoto.objects.filter(pk=self.photo.pk).exists())

    def test_foreign_branch_is_rejected(self):
        other = Business.objects.create(owner=self.owner, name='Other', slug='photo-other-branch', business_type='boutique')
        branch = Branch.objects.create(business=other, name='Main', code='MAIN', is_main=True)
        self.assertIn(self.client.delete(self.delete_url + '?branchId=' + str(branch.pk)).status_code, (403, 404))
        self.assertTrue(ProductPhoto.objects.filter(pk=self.photo.pk).exists())
