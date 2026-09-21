import hashlib
import hmac
import ipaddress
import time
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.core import signing
from django.core.exceptions import ObjectDoesNotExist
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.db import transaction
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from integrations.provider_credentials import get_provider_credential, touch_provider_credential
from inventory.video_urls import product_video_url

from .facebook_delivery import _whatsapp_link_for
from .management import owner_business
from .public_urls import public_shop_url
from .models import Storefront, SocialChannel, SocialDeliveryAttempt, SocialPublishingJob


PROVIDER = 'facebook'
CATEGORY = 'social'
MEDIA_SALT = 'stockflow.instagram.product-media.v1'
MEDIA_MAX_AGE_SECONDS = 1800
CONTAINER_STATUS_MAX_ATTEMPTS = 6
VIDEO_CONTAINER_STATUS_MAX_ATTEMPTS = 30
CONTAINER_STATUS_DELAY_SECONDS = 2


class InstagramDeliveryConflict(APIException):
    status_code = 409
    default_detail = 'This Instagram delivery cannot be retried safely yet.'


def _graph_url(path):
    return f"https://graph.facebook.com/{settings.META_GRAPH_API_VERSION}/{path.lstrip('/')}"


def _appsecret_proof(access_token):
    secret = settings.META_APP_SECRET.encode('utf-8')
    return hmac.new(secret, str(access_token).encode('utf-8'), hashlib.sha256).hexdigest()


def _safe_meta_error(response, fallback):
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    error = payload.get('error') if isinstance(payload, dict) else None
    code = error.get('code') if isinstance(error, dict) else None
    return f"{fallback}{f' (Meta code {code})' if code is not None else ''}."


def _connection_for(business):
    row, payload = get_provider_credential(
        business=business,
        category=CATEGORY,
        provider=PROVIDER,
    )
    if row is None or not payload:
        raise ValidationError({'instagram': 'Connect Instagram before publishing.'})
    if row.access_expires_at and row.access_expires_at <= timezone.now():
        raise ValidationError({'instagram': 'The Meta authorization has expired. Reconnect Instagram.'})

    account_id = str(payload.get('instagram_account_id', '')).strip()
    page_token = str(payload.get('page_access_token', '')).strip()
    if not account_id or not page_token:
        raise ValidationError({'instagram': 'Connect a linked Instagram professional account before publishing.'})
    return row, account_id, page_token


def _caption_for(job):
    payload = job.payload if isinstance(job.payload, dict) else {}
    name = ' '.join(str(payload.get('name', '')).split())[:180] or 'Product'
    currency = ' '.join(str(payload.get('currency', 'GHS')).split())[:10] or 'GHS'
    price = ' '.join(str(payload.get('price', '')).split())[:40]
    sku = ' '.join(str(payload.get('sku', '')).split())[:100]
    description = str(payload.get('description', '')).strip()[:1500]

    parts = [name]
    if price:
        parts.append(f'GH₵ {price}' if currency == 'GHS' else f'{currency} {price}')
    if sku:
        parts.append(f'Product code: {sku}')
    if description:
        parts.append(description)
    parts.append(f'Available from {job.channel.storefront.business.name}.')

    base_caption = '\n\n'.join(parts)
    has_shop_link = bool(public_shop_url(job.channel.storefront))
    has_whatsapp = bool(_whatsapp_link_for(job))

    if has_shop_link and has_whatsapp:
        suffix = '\n\nShop online or enquire on WhatsApp using the links in our profile.'
    elif has_shop_link:
        suffix = '\n\nShop online using the link in our profile.'
    elif has_whatsapp:
        suffix = '\n\nEnquire on WhatsApp — tap the WhatsApp link in our profile.'
    else:
        return base_caption[:2200]

    available = max(0, 2200 - len(suffix))
    return base_caption[:available].rstrip() + suffix


def _product_photo(job):
    try:
        return job.listing.product.uploaded_photo
    except ObjectDoesNotExist:
        return None


def _product_video(job):
    try:
        return job.listing.product.uploaded_video
    except ObjectDoesNotExist:
        return None


def _is_public_https_url(raw_url):
    try:
        parsed = urlparse(str(raw_url or '').strip())
    except ValueError:
        return False
    if parsed.scheme.lower() != 'https' or not parsed.hostname:
        return False

    hostname = parsed.hostname.lower().rstrip('.')
    if hostname == 'localhost' or hostname.endswith('.localhost') or hostname.endswith('.local'):
        return False
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return True
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_unspecified
    )


def _signed_media_path(job, photo):
    token = signing.dumps(
        {
            'job': str(job.id),
            'fingerprint': job.fingerprint,
            'photo': str(photo.id),
            'version': str(photo.version),
        },
        salt=MEDIA_SALT,
        compress=True,
    )
    return reverse('storefront:social-instagram-media') + '?token=' + token


def _image_url_for(job, request):
    photo = _product_photo(job)
    if photo is not None:
        media_path = _signed_media_path(job, photo)
        configured_base = str(
            getattr(settings, 'META_INSTAGRAM_MEDIA_BASE_URL', '') or ''
        ).strip().rstrip('/')
        if configured_base:
            candidate = configured_base + media_path
            if _is_public_https_url(candidate):
                return candidate

        candidate = request.build_absolute_uri(media_path)
        if _is_public_https_url(candidate):
            return candidate

    listing_url = str(job.listing.image_url or '').strip()
    if _is_public_https_url(listing_url):
        return listing_url

    payload = job.payload if isinstance(job.payload, dict) else {}
    payload_url = str(payload.get('imageUrl', '')).strip()
    if _is_public_https_url(payload_url):
        return payload_url

    raise ValidationError({
        'instagram': (
            'Instagram needs a publicly reachable HTTPS product image. '
            'This StockFlow photo is only reachable locally right now. '
            'Use a public StockFlow HTTPS address or an external HTTPS listing image before publishing.'
        )
    })



def _video_url_for(job, request):
    video = _product_video(job)
    if video is None:
        return ''

    path = product_video_url(job.listing.product)
    configured_base = str(
        getattr(settings, 'META_INSTAGRAM_MEDIA_BASE_URL', '') or ''
    ).strip().rstrip('/')
    if configured_base:
        candidate = configured_base + path
        if _is_public_https_url(candidate):
            return candidate

    candidate = request.build_absolute_uri(path)
    if _is_public_https_url(candidate):
        return candidate

    raise ValidationError({
        'instagram': (
            'Instagram needs a publicly reachable HTTPS product video. '
            'This StockFlow video is only reachable locally right now. '
            'Use a public StockFlow HTTPS address before publishing the Reel.'
        )
    })

def _attempt_response(attempt):
    return {
        'deliveryStatus': attempt.status,
        'attemptCount': attempt.attempt_count,
        'remoteContainerId': attempt.provider_container_id,
        'remotePostId': attempt.provider_post_id if attempt.status == SocialDeliveryAttempt.Status.SUCCEEDED else '',
        'error': attempt.error_message,
        'publishedAt': (
            attempt.completed_at.isoformat()
            if attempt.status == SocialDeliveryAttempt.Status.SUCCEEDED and attempt.completed_at
            else None
        ),
    }


def _claim_attempt(*, business, job_id):
    probe = get_object_or_404(
        SocialPublishingJob.objects.select_related('channel__storefront'),
        pk=job_id,
        channel__storefront__business=business,
        channel__platform=SocialChannel.Platform.INSTAGRAM,
    )

    with transaction.atomic():
        Storefront.objects.select_for_update().get(pk=probe.channel.storefront_id)
        job = (
            SocialPublishingJob.objects.select_for_update()
            .select_related(
                'channel__storefront__business',
                'channel__storefront__branch',
                'listing__product',
                'listing__product__uploaded_photo',
                'listing__product__uploaded_video',
            )
            .get(pk=probe.pk)
        )
        if job.status == SocialPublishingJob.Status.CANCELLED:
            raise ValidationError({'instagram': 'This publishing record is cancelled.'})

        eligible = (
            job.channel.auto_publish
            and job.channel.storefront.is_published
            and job.channel.storefront.branch.is_active
            and job.listing.is_published
            and job.listing.product.is_active
            and job.listing.product.business_id == business.id
        )
        if not eligible:
            raise ValidationError({'instagram': 'This product is not currently eligible for social publishing.'})

        attempt, _ = SocialDeliveryAttempt.objects.select_for_update().get_or_create(
            job=job,
            fingerprint=job.fingerprint,
            defaults={'status': SocialDeliveryAttempt.Status.FAILED},
        )
        if attempt.status == SocialDeliveryAttempt.Status.SUCCEEDED:
            return job, attempt, False
        if attempt.status == SocialDeliveryAttempt.Status.IN_PROGRESS:
            raise InstagramDeliveryConflict('This Instagram post is already being published.')
        if attempt.status == SocialDeliveryAttempt.Status.UNKNOWN:
            raise InstagramDeliveryConflict(
                'The previous Instagram delivery outcome is unknown. StockFlow will not retry automatically because that could create a duplicate post.'
            )

        attempt.status = SocialDeliveryAttempt.Status.IN_PROGRESS
        attempt.attempt_count += 1
        attempt.provider_post_id = ''
        attempt.provider_container_id = ''
        attempt.error_message = ''
        attempt.started_at = timezone.now()
        attempt.completed_at = None
        attempt.save(update_fields=(
            'status', 'attempt_count', 'provider_post_id', 'provider_container_id',
            'error_message', 'started_at', 'completed_at', 'updated_at',
        ))
        return job, attempt, True


def _remember_container(attempt_id, container_id):
    with transaction.atomic():
        attempt = SocialDeliveryAttempt.objects.select_for_update().get(pk=attempt_id)
        attempt.provider_container_id = str(container_id)[:180]
        attempt.save(update_fields=('provider_container_id', 'updated_at'))
        return attempt


def _finalize_attempt(*, attempt_id, status, provider_post_id='', error_message=''):
    with transaction.atomic():
        attempt = SocialDeliveryAttempt.objects.select_for_update().get(pk=attempt_id)
        attempt.status = status
        attempt.provider_post_id = str(provider_post_id)[:180]
        attempt.error_message = str(error_message)[:500]
        attempt.completed_at = timezone.now()
        attempt.save(update_fields=(
            'status', 'provider_post_id', 'error_message', 'completed_at', 'updated_at',
        ))
        return attempt



def _wait_for_container_ready(*, container_id, page_token, credential_row, max_attempts=None):
    max_attempts = max_attempts or CONTAINER_STATUS_MAX_ATTEMPTS
    common = {
        'access_token': page_token,
        'appsecret_proof': _appsecret_proof(page_token),
    }

    for attempt_number in range(1, max_attempts + 1):
        try:
            response = requests.get(
                _graph_url(container_id),
                params={'fields': 'status_code,status', **common},
                timeout=15,
                allow_redirects=False,
            )
            touch_provider_credential(credential_row)
        except requests.RequestException:
            if attempt_number < max_attempts:
                time.sleep(CONTAINER_STATUS_DELAY_SECONDS)
                continue
            return (
                'failed',
                'Meta could not confirm that the Instagram media container finished processing. '
                'No publish request was sent, so this delivery may be retried.',
            )

        if not 200 <= response.status_code < 300:
            if response.status_code >= 500 and attempt_number < max_attempts:
                time.sleep(CONTAINER_STATUS_DELAY_SECONDS)
                continue
            return (
                'failed',
                _safe_meta_error(
                    response,
                    'Meta could not confirm the Instagram media container status',
                ),
            )

        try:
            payload = response.json()
        except ValueError:
            payload = {}

        status_code = (
            str(payload.get('status_code', '')).strip().upper()
            if isinstance(payload, dict)
            else ''
        )

        if status_code == 'FINISHED':
            return 'ready', ''

        if status_code in {'ERROR', 'EXPIRED'}:
            return (
                'failed',
                f'Meta reported Instagram media container status {status_code}. '
                'No publish request was sent, so this delivery may be retried.',
            )

        if status_code == 'PUBLISHED':
            return (
                'unknown',
                'Meta reports that this Instagram media container is already published. '
                'StockFlow will not retry because that could create a duplicate post.',
            )

        if status_code not in {'', 'IN_PROGRESS'}:
            return (
                'unknown',
                f'Meta returned an unrecognized Instagram media container status '
                f'{status_code}. StockFlow will not retry automatically.',
            )

        if attempt_number < max_attempts:
            time.sleep(CONTAINER_STATUS_DELAY_SECONDS)

    return (
        'failed',
        'The Instagram media container is still processing. '
        'No publish request was sent, so this delivery may be retried.',
    )


def publish_instagram_job(*, business, job_id, request):
    credential_row, account_id, page_token = _connection_for(business)
    job, attempt, should_send = _claim_attempt(business=business, job_id=job_id)
    if not should_send:
        return attempt

    try:
        video_url = _video_url_for(job, request)
        image_url = '' if video_url else _image_url_for(job, request)
    except ValidationError as exc:
        detail = exc.detail.get('instagram') if isinstance(exc.detail, dict) else exc.detail
        return _finalize_attempt(
            attempt_id=attempt.id,
            status=SocialDeliveryAttempt.Status.FAILED,
            error_message=str(detail),
        )

    common = {
        'access_token': page_token,
        'appsecret_proof': _appsecret_proof(page_token),
    }

    try:
        media_data = {'caption': _caption_for(job), **common}
        if video_url:
            media_data.update({
                'media_type': 'REELS',
                'video_url': video_url,
                'share_to_feed': 'true',
            })
        else:
            media_data['image_url'] = image_url

        create_response = requests.post(
            _graph_url(f'{account_id}/media'),
            data=media_data,
            timeout=30,
            allow_redirects=False,
        )
        touch_provider_credential(credential_row)
    except requests.RequestException:
        return _finalize_attempt(
            attempt_id=attempt.id,
            status=SocialDeliveryAttempt.Status.FAILED,
            error_message='Meta could not confirm creation of the Instagram media container. No publish request was sent, so this delivery may be retried.',
        )

    if not 200 <= create_response.status_code < 300:
        return _finalize_attempt(
            attempt_id=attempt.id,
            status=SocialDeliveryAttempt.Status.FAILED,
            error_message=_safe_meta_error(create_response, 'Meta rejected the Instagram media container'),
        )

    try:
        create_payload = create_response.json()
    except ValueError:
        create_payload = {}
    container_id = str(create_payload.get('id', '')).strip() if isinstance(create_payload, dict) else ''
    if not container_id:
        return _finalize_attempt(
            attempt_id=attempt.id,
            status=SocialDeliveryAttempt.Status.FAILED,
            error_message='Meta returned success without an Instagram media container ID. No publish request was sent.',
        )

    _remember_container(attempt.id, container_id)

    readiness, readiness_error = _wait_for_container_ready(
        container_id=container_id,
        page_token=page_token,
        credential_row=credential_row,
        max_attempts=(VIDEO_CONTAINER_STATUS_MAX_ATTEMPTS if video_url else None),
    )
    if readiness != 'ready':
        return _finalize_attempt(
            attempt_id=attempt.id,
            status=(
                SocialDeliveryAttempt.Status.UNKNOWN
                if readiness == 'unknown'
                else SocialDeliveryAttempt.Status.FAILED
            ),
            error_message=readiness_error,
        )

    try:
        publish_response = requests.post(
            _graph_url(f'{account_id}/media_publish'),
            data={'creation_id': container_id, **common},
            timeout=30,
            allow_redirects=False,
        )
        touch_provider_credential(credential_row)
    except requests.RequestException:
        return _finalize_attempt(
            attempt_id=attempt.id,
            status=SocialDeliveryAttempt.Status.UNKNOWN,
            error_message='Meta did not confirm whether the Instagram post was published. Do not retry automatically.',
        )

    if not 200 <= publish_response.status_code < 300:
        status = SocialDeliveryAttempt.Status.UNKNOWN if publish_response.status_code >= 500 else SocialDeliveryAttempt.Status.FAILED
        fallback = (
            'Meta returned a server error and the Instagram publish outcome could not be confirmed'
            if status == SocialDeliveryAttempt.Status.UNKNOWN
            else 'Meta rejected the Instagram publish request'
        )
        return _finalize_attempt(
            attempt_id=attempt.id,
            status=status,
            error_message=_safe_meta_error(publish_response, fallback),
        )

    try:
        publish_payload = publish_response.json()
    except ValueError:
        publish_payload = {}
    media_id = str(publish_payload.get('id', '')).strip() if isinstance(publish_payload, dict) else ''
    if not media_id:
        return _finalize_attempt(
            attempt_id=attempt.id,
            status=SocialDeliveryAttempt.Status.UNKNOWN,
            error_message='Meta returned success without an Instagram media ID, so StockFlow cannot safely retry this delivery.',
        )

    return _finalize_attempt(
        attempt_id=attempt.id,
        status=SocialDeliveryAttempt.Status.SUCCEEDED,
        provider_post_id=media_id,
    )


class InstagramPublishJobAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, business_id, job_id):
        business = owner_business(request, business_id)
        attempt = publish_instagram_job(
            business=business,
            job_id=job_id,
            request=request,
        )
        response = Response(_attempt_response(attempt))
        response['Cache-Control'] = 'no-store'
        return response


class InstagramMediaAPIView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get(self, request):
        token = str(request.query_params.get('token', '')).strip()
        if not token:
            raise ValidationError({'token': 'A valid Instagram media token is required.'})
        try:
            data = signing.loads(token, salt=MEDIA_SALT, max_age=MEDIA_MAX_AGE_SECONDS)
        except signing.BadSignature:
            raise ValidationError({'token': 'This Instagram media link is invalid or expired.'})

        job = get_object_or_404(
            SocialPublishingJob.objects.select_related(
                'channel__storefront__branch',
                'listing__product',
                'listing__product__uploaded_photo',
                'listing__product__uploaded_video',
            ),
            pk=data.get('job'),
            fingerprint=data.get('fingerprint'),
            channel__platform=SocialChannel.Platform.INSTAGRAM,
        )
        photo = _product_photo(job)
        if (
            photo is None
            or str(photo.id) != str(data.get('photo'))
            or str(photo.version) != str(data.get('version'))
        ):
            raise ValidationError({'token': 'This Instagram media link no longer matches the product photo.'})

        eligible = (
            job.channel.auto_publish
            and job.channel.storefront.is_published
            and job.channel.storefront.branch.is_active
            and job.listing.is_published
            and job.listing.product.is_active
        )
        if not eligible:
            raise ValidationError({'token': 'This product is no longer eligible for Instagram publishing.'})

        try:
            image_file = photo.image.storage.open(photo.image.name, 'rb')
        except (OSError, ValueError) as exc:
            raise ValidationError({'token': 'The stored product photo is unavailable.'}) from exc

        response = FileResponse(image_file, content_type='image/jpeg')
        response['Cache-Control'] = 'private, max-age=300'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
