import logging
import uuid
from pathlib import Path

from django.core import signing
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from .models import Product, ProductVideo
from .video_urls import VIDEO_PREVIEW_SALT, product_video_url
from .views import BusinessProductAccessMixin

log = logging.getLogger(__name__)

MAX_VIDEO_BYTES = 100 * 1024 * 1024
ALLOWED_VIDEO_TYPES = {
    'video/mp4': 'mp4',
    'video/quicktime': 'mov',
}


class VideoUploadThrottle(UserRateThrottle):
    scope = 'product_video'
    rate = '12/min'


class VideoReadThrottle(UserRateThrottle):
    scope = 'product_video_read'
    rate = '120/min'


def delete_replaced_video(storage, name):
    try:
        storage.delete(name)
    except Exception:
        log.warning('Could not remove replaced product video from storage.', exc_info=True)


def validate_video(upload):
    if not upload or not upload.size:
        raise ValidationError({'video': 'Choose one MP4 or MOV video.'})
    if upload.size > MAX_VIDEO_BYTES:
        raise ValidationError({'video': 'Choose a video no larger than 100 MB.'})

    content_type = str(getattr(upload, 'content_type', '') or '').lower().strip()
    extension = Path(str(getattr(upload, 'name', '') or '')).suffix.lower().lstrip('.')
    expected_extension = ALLOWED_VIDEO_TYPES.get(content_type)
    if expected_extension is None or extension not in {'mp4', 'mov'}:
        raise ValidationError({'video': 'Use an MP4 or MOV video.'})

    upload.seek(0)
    header = upload.read(16)
    upload.seek(0)
    if len(header) < 12 or header[4:8] != b'ftyp':
        raise ValidationError({'video': 'The video file could not be verified as MP4 or MOV.'})

    return content_type, expected_extension


class ProductVideoUploadAPIView(BusinessProductAccessMixin, APIView):
    permission_classes = (IsAuthenticated,)
    parser_classes = (MultiPartParser,)
    throttle_classes = (VideoUploadThrottle,)

    def post(self, request, business_id, product_id):
        _, denied = self.require_inventory_write_access()
        if denied is not None:
            return denied
        product = self.get_product()
        if set(request.data) - {'video', 'branchId'} or len(request.FILES.getlist('video')) != 1:
            raise ValidationError({'video': 'Send exactly one video and an optional branchId.'})

        upload = request.FILES.get('video')
        content_type, extension = validate_video(upload)
        size_bytes = upload.size

        from storefront.models import Storefront, StorefrontListing
        from storefront.social import sync_social_listing

        saved_name = None
        storage = ProductVideo._meta.get_field('video').storage
        try:
            with transaction.atomic():
                Storefront.objects.select_for_update().filter(
                    business_id=product.business_id
                ).first()
                product = Product.objects.select_for_update().get(pk=product.pk)
                video = ProductVideo.objects.filter(product=product).first()
                old_name = video.video.name if video else ''
                video = video or ProductVideo(product=product)
                video.version = uuid.uuid4()
                video.content_type = content_type
                video.extension = extension
                video.size_bytes = size_bytes
                video.uploaded_by = request.user
                video.video.save(
                    f'{video.version}.{extension}',
                    upload,
                    save=False,
                )
                saved_name = video.video.name
                video.save()
                for listing in StorefrontListing.objects.filter(product=product):
                    sync_social_listing(listing)
                if old_name and old_name != saved_name:
                    transaction.on_commit(
                        lambda: delete_replaced_video(storage, old_name)
                    )
        except Exception:
            if saved_name:
                delete_replaced_video(storage, saved_name)
            raise

        product = Product.objects.select_related('uploaded_video').get(pk=product.pk)
        response = Response({
            'productId': str(product.pk),
            'hasVideo': True,
            'videoUrl': product_video_url(product, request, private=True),
        })
        response['Cache-Control'] = 'no-store'
        return response

    def delete(self, request, business_id, product_id):
        _, denied = self.require_inventory_write_access()
        if denied is not None:
            return denied
        product = self.get_product()

        from storefront.models import Storefront, StorefrontListing
        from storefront.social import sync_social_listing

        with transaction.atomic():
            Storefront.objects.select_for_update().filter(
                business_id=product.business_id
            ).first()
            product = Product.objects.select_for_update().get(pk=product.pk)
            video = ProductVideo.objects.filter(product=product).first()
            if video is None:
                response = Response({'productId': str(product.pk), 'hasVideo': False})
                response['Cache-Control'] = 'no-store'
                return response
            storage = video.video.storage
            old_name = video.video.name
            video.delete()
            for listing in StorefrontListing.objects.filter(product=product):
                sync_social_listing(listing)
            if old_name:
                transaction.on_commit(
                    lambda: delete_replaced_video(storage, old_name)
                )

        response = Response({'productId': str(product.pk), 'hasVideo': False})
        response['Cache-Control'] = 'no-store'
        return response


class ProductVideoContentAPIView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    throttle_classes = (VideoReadThrottle,)

    def get(self, request, video_id, version):
        video = get_object_or_404(
            ProductVideo.objects.select_related('product'),
            pk=video_id,
            version=version,
        )

        valid_preview = False
        try:
            token = signing.loads(
                request.query_params.get('preview', ''),
                salt=VIDEO_PREVIEW_SALT,
                max_age=900,
            )
            valid_preview = token == {
                'video': str(video.id),
                'version': str(video.version),
            }
        except signing.BadSignature:
            pass

        if not valid_preview:
            from storefront.models import StorefrontListing
            from storefront.services import require_public_storefront

            listing = (
                StorefrontListing.objects.filter(
                    product=video.product,
                    product__is_active=True,
                    is_published=True,
                    storefront__business_id=video.product.business_id,
                )
                .select_related('storefront__business', 'storefront__branch')
                .first()
            )
            if listing is None:
                raise Http404
            require_public_storefront(listing.storefront)

        try:
            video_file = video.video.storage.open(video.video.name, 'rb')
        except (OSError, ValueError) as exc:
            raise Http404 from exc

        response = FileResponse(video_file, content_type=video.content_type)
        response['Cache-Control'] = 'no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        response['Content-Disposition'] = f'inline; filename="product.{video.extension}"'
        return response
