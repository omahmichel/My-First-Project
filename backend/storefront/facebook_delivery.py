import hashlib
import hmac
from urllib.parse import quote

import requests
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from integrations.provider_credentials import get_provider_credential, touch_provider_credential

from .management import owner_business
from .public_urls import public_shop_url
from .models import Storefront, SocialChannel, SocialPublishingJob, SocialDeliveryAttempt


PROVIDER = 'facebook'
CATEGORY = 'social'


class FacebookDeliveryConflict(APIException):
    status_code = 409
    default_detail = 'This Facebook delivery cannot be retried safely yet.'


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


def _ghana_whatsapp_digits(raw_phone):
    digits = ''.join(character for character in str(raw_phone or '') if character.isdigit())
    if digits.startswith('00'):
        digits = digits[2:]
    if digits.startswith('0') and len(digits) == 10:
        digits = '233' + digits[1:]
    elif len(digits) == 9:
        digits = '233' + digits
    if not (digits.startswith('233') and len(digits) == 12):
        return ''
    return digits


def _whatsapp_link_for(job):
    shop = job.channel.storefront
    if not shop.whatsapp_enabled or not shop.whatsapp_phone:
        return ''

    digits = _ghana_whatsapp_digits(shop.whatsapp_phone)
    if not digits:
        return ''

    payload = job.payload if isinstance(job.payload, dict) else {}
    name = ' '.join(str(payload.get('name', '')).split())[:180] or 'this product'
    sku = ' '.join(str(payload.get('sku', '')).split())[:100]
    message = f"Hello {shop.business.name}, I'm interested in {name}"
    if sku:
        message += f" (Product code: {sku})"
    message += '. Is it available?'
    return f"https://wa.me/{digits}?text={quote(message, safe='')}"


def _message_for(job):
    payload = job.payload if isinstance(job.payload, dict) else {}
    name = ' '.join(str(payload.get('name', '')).split())[:180] or 'Product'
    currency = ' '.join(str(payload.get('currency', 'GHS')).split())[:10] or 'GHS'
    price = ' '.join(str(payload.get('price', '')).split())[:40]
    sku = ' '.join(str(payload.get('sku', '')).split())[:100]
    description = str(payload.get('description', '')).strip()[:1500]

    parts = [name]
    if price:
        price_label = f'GH₵ {price}' if currency == 'GHS' else f'{currency} {price}'
        parts.append(price_label)
    if sku:
        parts.append(f'Product code: {sku}')
    if description:
        parts.append(description)
    parts.append(f'Available from {job.channel.storefront.business.name}.')

    shop_url = public_shop_url(job.channel.storefront)
    if shop_url:
        parts.extend(['Shop online:', shop_url])

    whatsapp_link = _whatsapp_link_for(job)
    if whatsapp_link:
        parts.extend(['Enquire on WhatsApp:', whatsapp_link])

    return '\n\n'.join(parts)[:4000]


def _connection_for(business):
    row, payload = get_provider_credential(
        business=business,
        category=CATEGORY,
        provider=PROVIDER,
    )
    if row is None or not payload:
        raise ValidationError({'facebook': 'Connect a Facebook Page before publishing.'})
    if row.access_expires_at and row.access_expires_at <= timezone.now():
        raise ValidationError({'facebook': 'The Facebook authorization has expired. Reconnect Facebook.'})

    page_id = str(payload.get('page_id', '')).strip()
    page_token = str(payload.get('page_access_token', '')).strip()
    if not page_id or not page_token:
        raise ValidationError({'facebook': 'Choose a Facebook Page before publishing.'})
    return row, page_id, page_token


def _attempt_response(attempt):
    return {
        'deliveryStatus': attempt.status,
        'attemptCount': attempt.attempt_count,
        'remotePostId': attempt.provider_post_id if attempt.status == SocialDeliveryAttempt.Status.SUCCEEDED else '',
        'remoteContainerId': attempt.provider_container_id,
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
        channel__platform=SocialChannel.Platform.FACEBOOK,
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
            raise ValidationError({'facebook': 'This publishing record is cancelled.'})

        eligible = (
            job.channel.auto_publish
            and job.channel.storefront.is_published
            and job.channel.storefront.branch.is_active
            and job.listing.is_published
            and job.listing.product.is_active
            and job.listing.product.business_id == business.id
        )
        if not eligible:
            raise ValidationError({'facebook': 'This product is not currently eligible for social publishing.'})

        attempt, _ = SocialDeliveryAttempt.objects.select_for_update().get_or_create(
            job=job,
            fingerprint=job.fingerprint,
            defaults={'status': SocialDeliveryAttempt.Status.FAILED},
        )
        if attempt.status == SocialDeliveryAttempt.Status.SUCCEEDED:
            return job, attempt, False
        if attempt.status == SocialDeliveryAttempt.Status.IN_PROGRESS:
            raise FacebookDeliveryConflict('This Facebook post is already being published.')
        if attempt.status == SocialDeliveryAttempt.Status.UNKNOWN:
            raise FacebookDeliveryConflict(
                'The previous Facebook delivery outcome is unknown. StockFlow will not retry automatically because that could create a duplicate post.'
            )

        attempt.status = SocialDeliveryAttempt.Status.IN_PROGRESS
        attempt.attempt_count += 1
        attempt.provider_post_id = ''
        attempt.provider_container_id = ''
        attempt.error_message = ''
        attempt.started_at = timezone.now()
        attempt.completed_at = None
        attempt.save(update_fields=(
            'status',
            'attempt_count',
            'provider_post_id',
            'provider_container_id',
            'error_message',
            'started_at',
            'completed_at',
            'updated_at',
        ))
        return job, attempt, True


def _finalize_attempt(*, attempt_id, status, provider_post_id='', error_message=''):
    with transaction.atomic():
        attempt = SocialDeliveryAttempt.objects.select_for_update().get(pk=attempt_id)
        attempt.status = status
        attempt.provider_post_id = str(provider_post_id)[:180]
        attempt.error_message = str(error_message)[:500]
        attempt.completed_at = timezone.now()
        attempt.save(update_fields=(
            'status',
            'provider_post_id',
            'error_message',
            'completed_at',
            'updated_at',
        ))
        return attempt


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


def _remember_container(attempt_id, container_id):
    with transaction.atomic():
        attempt = SocialDeliveryAttempt.objects.select_for_update().get(pk=attempt_id)
        attempt.provider_container_id = str(container_id)[:180]
        attempt.save(update_fields=('provider_container_id', 'updated_at'))
        return attempt


def _send_to_meta(*, job, page_id, page_token):
    message = _message_for(job)
    common = {
        'access_token': page_token,
        'appsecret_proof': _appsecret_proof(page_token),
    }
    photo = _product_photo(job)

    if photo is None:
        return requests.post(
            _graph_url(f'{page_id}/feed'),
            data={'message': message, **common},
            timeout=20,
            allow_redirects=False,
        ), False

    try:
        image_file = photo.image.storage.open(photo.image.name, 'rb')
    except (OSError, ValueError) as exc:
        raise ValidationError(
            {'facebook': 'The stored product photo could not be opened. Upload the product photo again before publishing.'}
        ) from exc

    with image_file:
        return requests.post(
            _graph_url(f'{page_id}/photos'),
            data={
                'caption': message,
                'published': 'true',
                **common,
            },
            files={
                'source': ('product.jpg', image_file, 'image/jpeg'),
            },
            timeout=30,
            allow_redirects=False,
        ), True



def _publish_video_reel(*, job, attempt, page_id, page_token, credential_row):
    video = _product_video(job)
    if video is None:
        return None

    common = {
        'access_token': page_token,
        'appsecret_proof': _appsecret_proof(page_token),
    }

    try:
        create_response = requests.post(
            _graph_url(f'{page_id}/video_reels'),
            data={'upload_phase': 'start', **common},
            timeout=30,
            allow_redirects=False,
        )
        touch_provider_credential(credential_row)
    except requests.RequestException:
        return _finalize_attempt(
            attempt_id=attempt.id,
            status=SocialDeliveryAttempt.Status.FAILED,
            error_message=(
                'Meta could not confirm creation of the Facebook Reel upload session. '
                'No publish request was sent, so this delivery may be retried.'
            ),
        )

    if not 200 <= create_response.status_code < 300:
        return _finalize_attempt(
            attempt_id=attempt.id,
            status=SocialDeliveryAttempt.Status.FAILED,
            error_message=_safe_meta_error(
                create_response,
                'Meta rejected the Facebook Reel upload session',
            ),
        )

    try:
        create_payload = create_response.json()
    except ValueError:
        create_payload = {}
    video_id = str(create_payload.get('video_id', '')).strip() if isinstance(create_payload, dict) else ''
    if not video_id:
        return _finalize_attempt(
            attempt_id=attempt.id,
            status=SocialDeliveryAttempt.Status.FAILED,
            error_message='Meta returned success without a Facebook Reel video ID. No publish request was sent.',
        )

    _remember_container(attempt.id, video_id)

    try:
        video_file = video.video.storage.open(video.video.name, 'rb')
    except (OSError, ValueError):
        return _finalize_attempt(
            attempt_id=attempt.id,
            status=SocialDeliveryAttempt.Status.FAILED,
            error_message='The stored product video could not be opened. Upload the product video again before publishing.',
        )

    upload_url = f'https://rupload.facebook.com/video-upload/{settings.META_GRAPH_API_VERSION}/{video_id}'
    try:
        with video_file:
            upload_response = requests.post(
                upload_url,
                headers={
                    'Authorization': f'OAuth {page_token}',
                    'offset': '0',
                    'file_size': str(video.size_bytes),
                    'Content-Type': 'application/octet-stream',
                },
                data=video_file,
                timeout=120,
                allow_redirects=False,
            )
        touch_provider_credential(credential_row)
    except requests.RequestException:
        return _finalize_attempt(
            attempt_id=attempt.id,
            status=SocialDeliveryAttempt.Status.FAILED,
            error_message=(
                'Meta could not confirm the Facebook Reel video upload. '
                'No publish request was sent, so this delivery may be retried.'
            ),
        )

    if not 200 <= upload_response.status_code < 300:
        return _finalize_attempt(
            attempt_id=attempt.id,
            status=SocialDeliveryAttempt.Status.FAILED,
            error_message=_safe_meta_error(
                upload_response,
                'Meta rejected the Facebook Reel video upload',
            ),
        )

    payload = job.payload if isinstance(job.payload, dict) else {}
    title = ' '.join(str(payload.get('name', '')).split())[:255] or 'Product'
    try:
        publish_response = requests.post(
            _graph_url(f'{page_id}/video_reels'),
            data={
                'video_id': video_id,
                'upload_phase': 'finish',
                'video_state': 'PUBLISHED',
                'description': _message_for(job),
                'title': title,
                **common,
            },
            timeout=30,
            allow_redirects=False,
        )
        touch_provider_credential(credential_row)
    except requests.RequestException:
        return _finalize_attempt(
            attempt_id=attempt.id,
            status=SocialDeliveryAttempt.Status.UNKNOWN,
            error_message=(
                'Meta did not confirm whether the Facebook Reel was published. '
                'Do not retry automatically.'
            ),
        )

    if not 200 <= publish_response.status_code < 300:
        status = (
            SocialDeliveryAttempt.Status.UNKNOWN
            if publish_response.status_code >= 500
            else SocialDeliveryAttempt.Status.FAILED
        )
        fallback = (
            'Meta returned a server error and the Facebook Reel publish outcome could not be confirmed'
            if status == SocialDeliveryAttempt.Status.UNKNOWN
            else 'Meta rejected the Facebook Reel publish request'
        )
        return _finalize_attempt(
            attempt_id=attempt.id,
            status=status,
            error_message=_safe_meta_error(publish_response, fallback),
        )

    return _finalize_attempt(
        attempt_id=attempt.id,
        status=SocialDeliveryAttempt.Status.SUCCEEDED,
        provider_post_id=video_id,
    )

def publish_facebook_job(*, business, job_id):
    credential_row, page_id, page_token = _connection_for(business)
    job, attempt, should_send = _claim_attempt(business=business, job_id=job_id)
    if not should_send:
        return attempt

    video_attempt = _publish_video_reel(
        job=job,
        attempt=attempt,
        page_id=page_id,
        page_token=page_token,
        credential_row=credential_row,
    )
    if video_attempt is not None:
        return video_attempt

    try:
        response, used_photo = _send_to_meta(
            job=job,
            page_id=page_id,
            page_token=page_token,
        )
        touch_provider_credential(credential_row)
    except ValidationError as exc:
        detail = exc.detail.get('facebook') if isinstance(exc.detail, dict) else exc.detail
        return _finalize_attempt(
            attempt_id=attempt.id,
            status=SocialDeliveryAttempt.Status.FAILED,
            error_message=str(detail),
        )
    except requests.RequestException:
        return _finalize_attempt(
            attempt_id=attempt.id,
            status=SocialDeliveryAttempt.Status.UNKNOWN,
            error_message='Meta did not confirm whether the Facebook post was created. Do not retry automatically.',
        )

    if not 200 <= response.status_code < 300:
        status = SocialDeliveryAttempt.Status.UNKNOWN if response.status_code >= 500 else SocialDeliveryAttempt.Status.FAILED
        fallback = (
            'Meta returned a server error and the delivery outcome could not be confirmed'
            if status == SocialDeliveryAttempt.Status.UNKNOWN
            else 'Meta rejected the Facebook Page post'
        )
        return _finalize_attempt(
            attempt_id=attempt.id,
            status=status,
            error_message=_safe_meta_error(response, fallback),
        )

    try:
        payload = response.json()
    except ValueError:
        payload = {}

    if used_photo:
        post_id = str(payload.get('post_id') or payload.get('id') or '').strip() if isinstance(payload, dict) else ''
    else:
        post_id = str(payload.get('id', '')).strip() if isinstance(payload, dict) else ''

    if not post_id:
        return _finalize_attempt(
            attempt_id=attempt.id,
            status=SocialDeliveryAttempt.Status.UNKNOWN,
            error_message='Meta returned success without a post ID, so StockFlow cannot safely retry this delivery.',
        )

    return _finalize_attempt(
        attempt_id=attempt.id,
        status=SocialDeliveryAttempt.Status.SUCCEEDED,
        provider_post_id=post_id,
    )


class FacebookPublishJobAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, business_id, job_id):
        business = owner_business(request, business_id)
        attempt = publish_facebook_job(business=business, job_id=job_id)
        response = Response(_attempt_response(attempt))
        response['Cache-Control'] = 'no-store'
        return response
