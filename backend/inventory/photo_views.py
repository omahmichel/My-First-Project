import logging
import uuid
from django.core import signing
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView
from .models import Product, ProductPhoto
from .photo_images import normalize_photo
from .photo_urls import PHOTO_SALT, product_photo_url
from .views import BusinessProductAccessMixin

log = logging.getLogger(__name__)


class PhotoUploadThrottle(UserRateThrottle):
    scope = 'product_photo'
    rate = '30/min'


def delete_replaced_file(storage, name):
    try:
        storage.delete(name)
    except Exception:
        log.warning('Could not remove replaced product photo from storage.', exc_info=True)


class ProductPhotoUploadAPIView(BusinessProductAccessMixin, APIView):
    permission_classes = (IsAuthenticated,)
    parser_classes = (MultiPartParser,)
    throttle_classes = (PhotoUploadThrottle,)

    def post(self, request, business_id, product_id, prepare=False):
        _, denied = self.require_inventory_write_access()
        if denied is not None:
            return denied
        product = self.get_product()  # Includes business and branch authorization.
        if set(request.data) - {'image', 'branchId'} or len(request.FILES.getlist('image')) != 1:
            raise ValidationError({'image': 'Send exactly one image and an optional branchId.'})
        data = normalize_photo(request.FILES.get('image'))
        if prepare:
            response = HttpResponse(data, content_type='image/jpeg')
            response['Cache-Control'] = 'no-store'
            response['X-Content-Type-Options'] = 'nosniff'
            return response

        from storefront.models import Storefront, StorefrontListing
        from storefront.social import sync_social_listing
        saved_name = None
        storage = ProductPhoto._meta.get_field('image').storage
        try:
            with transaction.atomic():
                # Same lock order as storefront publishing: shop, then product.
                Storefront.objects.select_for_update().filter(business_id=product.business_id).first()
                product = Product.objects.select_for_update().get(pk=product.pk)
                photo = ProductPhoto.objects.filter(product=product).first()
                old_name = photo.image.name if photo else ''
                photo = photo or ProductPhoto(product=product)
                photo.version = uuid.uuid4()
                photo.uploaded_by = request.user
                photo.image.save(str(photo.version) + '.jpg', ContentFile(data), save=False)
                saved_name = photo.image.name
                photo.save()
                for listing in StorefrontListing.objects.filter(product=product):
                    sync_social_listing(listing)
                if old_name and old_name != saved_name:
                    transaction.on_commit(lambda: delete_replaced_file(storage, old_name))
        except Exception:
            if saved_name:
                delete_replaced_file(storage, saved_name)
            raise
        # Reload to avoid a cached reverse relation after replacing the photo.
        product = Product.objects.select_related('uploaded_photo').get(pk=product.pk)
        response = Response({'productId': str(product.pk), 'imageUrl': product_photo_url(product, request, private=True)})
        response['Cache-Control'] = 'no-store'
        return response


class ProductPhotoContentAPIView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get(self, request, photo_id, version):
        photo = get_object_or_404(ProductPhoto.objects.select_related('product'), pk=photo_id, version=version)
        valid_preview = False
        try:
            token = signing.loads(request.query_params.get('preview', ''), salt=PHOTO_SALT, max_age=900)
            valid_preview = token == {'photo': str(photo.id), 'version': str(photo.version)}
        except signing.BadSignature:
            pass
        if not valid_preview:
            from storefront.models import StorefrontListing
            from storefront.services import require_public_storefront
            listing = StorefrontListing.objects.filter(
                product=photo.product, product__is_active=True, is_published=True,
                storefront__business_id=photo.product.business_id,
            ).select_related('storefront__business', 'storefront__branch').first()
            if listing is None:
                raise Http404
            require_public_storefront(listing.storefront)
        try:
            response = FileResponse(photo.image.open('rb'), content_type='image/jpeg')
        except (OSError, ValueError):
            raise Http404
        response['Cache-Control'] = 'no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        response['Content-Disposition'] = 'inline; filename="product.jpg"'
        return response
