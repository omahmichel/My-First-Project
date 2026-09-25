"""Controlled TikTok photo posts for StockFlow product publishing jobs.

This module is independent of the separate TikTok product-video publishing flow.
It uses the existing SocialPublishingJob/SocialDeliveryAttempt foundation so
Facebook and Instagram delivery behavior remains untouched.
"""
from __future__ import annotations

import mimetypes
import os
import re
from datetime import timedelta
from urllib.parse import urlsplit

import requests
from django.conf import settings
from django.core import signing
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from integrations.provider_credentials import get_provider_credential, touch_provider_credential

from .management import owner_business
from .models import Storefront, SocialChannel, SocialDeliveryAttempt, SocialPublishingJob
from .short_video_connections import ConnectionThrottle


PROVIDER = 'tiktok'
CATEGORY = 'social'
API = 'https://open.tiktokapis.com/v2/post/publish/'
MEDIA_SALT = 'stockflow.tiktok.product-photo.v1'
MEDIA_MAX_AGE_SECONDS = 7200
PRIVACY_LEVELS = (
    'PUBLIC_TO_EVERYONE',
    'MUTUAL_FOLLOW_FRIENDS',
    'FOLLOWER_OF_CREATOR',
    'SELF_ONLY',
)


class TikTokProductDeliveryConflict(APIException):
    status_code = 409
    default_detail = 'This TikTok product delivery cannot be retried safely yet.'


class TikTokRemoteFailure(Exception):
    def __init__(self, message, *, uncertain=False):
        super().__init__(message)
        self.message = message
        self.uncertain = uncertain


ERRORS = {
    'unaudited_client_can_only_post_to_private_accounts': (
        'TikTok requires a private account for this unaudited app. Use a private test account.'
    ),
    'url_ownership_unverified': (
        'TikTok has not verified the public StockFlow media address. Verify the current URL prefix before publishing.'
    ),
    'privacy_level_option_mismatch': (
        'TikTok privacy options changed. Open the publishing window again and choose an available audience.'
    ),
    'access_token_invalid': 'TikTok access expired. Verify the connection or reconnect.',
    'scope_not_authorized': 'Reconnect TikTok and approve the posting permission.',
    'rate_limit_exceeded': 'TikTok rate limit reached. Wait before trying again.',
    'spam_risk_too_many_posts': 'TikTok daily posting limit reached for this account.',
    'spam_risk_too_many_pending_share': 'TikTok has too many pending shares for this account.',
    'reached_active_user_cap': 'TikTok app testing quota has been reached.',
    'spam_risk_user_banned_from_posting': 'TikTok has blocked posting for this account.',
}


def _setting(name):
    return str(getattr(settings, name, os.getenv(name, '')) or '').strip()


def _media_base():
    value = _setting('STOCKFLOW_TIKTOK_MEDIA_BASE_URL').rstrip('/')
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise ValidationError({'tiktok': 'Configure a verified public HTTPS TikTok media origin before publishing.'}) from exc
    if (
        parsed.scheme != 'https'
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path
    ):
        raise ValidationError({'tiktok': 'Configure a verified public HTTPS TikTok media origin before publishing.'})
    return value


def _connection_for(business):
    row, payload = get_provider_credential(
        business=business,
        category=CATEGORY,
        provider=PROVIDER,
    )
    if row is None or not payload or not payload.get('account_id'):
        raise ValidationError({'tiktok': 'Connect TikTok before publishing.'})
    if not row.access_expires_at or row.access_expires_at <= timezone.now() + timedelta(seconds=60):
        raise ValidationError({'tiktok': 'Verify the TikTok connection to renew access, then try again.'})
    scopes = set(str(payload.get('scope', '')).replace(',', ' ').split())
    if 'video.publish' not in scopes:
        raise ValidationError({'tiktok': 'Reconnect TikTok and approve the posting permission.'})
    return row, payload


def _error_code(data):
    error = data.get('error') if isinstance(data, dict) else None
    return error.get('code') if isinstance(error, dict) else None


def _remote(endpoint, credential_row, credential_payload, body, *, uncertain_on_transport=False):
    try:
        response = requests.post(
            API + endpoint,
            headers={
                'Authorization': 'Bearer ' + credential_payload['access_token'],
                'Content-Type': 'application/json; charset=UTF-8',
            },
            json=body,
            timeout=25,
            allow_redirects=False,
        )
        touch_provider_credential(credential_row)
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise TikTokRemoteFailure(
            'TikTok did not return a usable response. Check TikTok before attempting another product post.'
            if uncertain_on_transport
            else 'TikTok could not be reached. Try again after checking the account connection.',
            uncertain=uncertain_on_transport,
        ) from exc

    if not isinstance(data, dict):
        raise TikTokRemoteFailure(
            'TikTok returned an unreadable response.',
            uncertain=uncertain_on_transport,
        )

    code = _error_code(data)
    if response.status_code >= 500:
        raise TikTokRemoteFailure(
            'TikTok is temporarily unavailable.' + (
                ' The product-post outcome may be unknown.' if uncertain_on_transport else ''
            ),
            uncertain=uncertain_on_transport,
        )
    if response.status_code == 200 and not code:
        raise TikTokRemoteFailure(
            'TikTok returned no request outcome. Check the post status before retrying.',
            uncertain=uncertain_on_transport,
        )
    if response.status_code != 200 or code != 'ok':
        raise TikTokRemoteFailure(
            ERRORS.get(code, 'TikTok rejected this request. Review the account and product-post settings.'),
            uncertain=False,
        )
    result = data.get('data')
    if not isinstance(result, dict):
        raise TikTokRemoteFailure(
            'TikTok returned an incomplete response.',
            uncertain=uncertain_on_transport,
        )
    return result


def _creator_info(credential_row, credential_payload):
    try:
        result = _remote(
            'creator_info/query/',
            credential_row,
            credential_payload,
            {},
        )
    except TikTokRemoteFailure as exc:
        raise ValidationError({'tiktok': exc.message}) from exc

    options = result.get('privacy_level_options')
    nickname = str(result.get('creator_nickname', '')).strip()
    username = str(result.get('creator_username', '')).strip()
    if not isinstance(options, list) or not nickname:
        raise ValidationError({'tiktok': 'TikTok did not return usable creator settings.'})
    clean_options = [str(value) for value in options if str(value) in PRIVACY_LEVELS]
    if not clean_options:
        raise ValidationError({'tiktok': 'TikTok did not return any supported privacy options.'})
    return {
        'nickname': nickname[:180],
        'username': username[:180],
        'privacyOptions': clean_options,
        'commentDisabled': bool(result.get('comment_disabled')),
    }


def _eligible(job, business):
    return (
        job.channel.auto_publish
        and job.channel.storefront.is_published
        and job.channel.storefront.branch.is_active
        and job.listing.is_published
        and job.listing.product.is_active
        and job.listing.product.business_id == business.id
    )


def _job_for(business, job_id):
    job = get_object_or_404(
        SocialPublishingJob.objects.select_related(
            'channel__storefront__business',
            'channel__storefront__branch',
            'listing__product',
            'listing__product__uploaded_photo',
        ),
        pk=job_id,
        channel__storefront__business=business,
        channel__platform=SocialChannel.Platform.TIKTOK,
    )
    if job.status == SocialPublishingJob.Status.CANCELLED:
        raise ValidationError({'tiktok': 'This publishing record is cancelled.'})
    if not _eligible(job, business):
        raise ValidationError({'tiktok': 'This product is not currently eligible for TikTok publishing.'})
    return job


def _product_photo(job):
    try:
        return job.listing.product.uploaded_photo
    except ObjectDoesNotExist:
        return None


def _media_token(job, photo):
    return signing.dumps(
        {
            'job': str(job.id),
            'fingerprint': job.fingerprint,
            'photo': str(photo.id),
            'version': str(photo.version),
        },
        salt=MEDIA_SALT,
        compress=True,
    )


def _photo_url_for(job):
    photo = _product_photo(job)
    if photo is None:
        raise ValidationError({
            'tiktok': 'TikTok product posting requires a saved StockFlow product photo. Add a product photo before publishing.'
        })
    path = reverse('storefront:social-tiktok-product-media') + '?token=' + _media_token(job, photo)
    return _media_base() + path


def _utf16_units(value):
    return len(str(value).encode('utf-16-le')) // 2


def _truncate_utf16(value, limit):
    text = str(value or '')
    while text and _utf16_units(text) > limit:
        text = text[:-1]
    return text


def _default_text(job):
    payload = job.payload if isinstance(job.payload, dict) else {}
    title = _truncate_utf16(' '.join(str(payload.get('name', '')).split()) or 'Product', 90)
    currency = ' '.join(str(payload.get('currency', 'GHS')).split())[:10] or 'GHS'
    price = ' '.join(str(payload.get('price', '')).split())[:40]
    sku = ' '.join(str(payload.get('sku', '')).split())[:100]
    description = str(payload.get('description', '')).strip()
    parts = []
    if price:
        parts.append(f'GH₵ {price}' if currency == 'GHS' else f'{currency} {price}')
    if sku:
        parts.append(f'Product code: {sku}')
    if description:
        parts.append(description)
    parts.append(f'Available from {job.channel.storefront.business.name}.')
    # Keep WhatsApp contact details intact when shortening long captions.
    from .facebook_delivery import _whatsapp_link_for, _ghana_whatsapp_digits

    whatsapp_link = _whatsapp_link_for(job)
    body = '\n\n'.join(parts)
    if whatsapp_link:
        digits = _ghana_whatsapp_digits(job.channel.storefront.whatsapp_phone)
        contact = f'WhatsApp: +{digits}\nEnquire on WhatsApp: {whatsapp_link}'
        remaining = 4000 - _utf16_units(contact) - 2
        if remaining < 0:
            raise ValidationError({'tiktok': 'The WhatsApp enquiry link is too long. Shorten the business or product name.'})
        body = _truncate_utf16(body, remaining).rstrip() + '\n\n' + contact
    return title, _truncate_utf16(body, 4000)


def _attempt_response(attempt):
    return {
        'deliveryStatus': attempt.status,
        'attemptCount': attempt.attempt_count,
        'remotePostId': (
            attempt.provider_post_id
            if attempt.status == SocialDeliveryAttempt.Status.SUCCEEDED
            else ''
        ),
        'remoteContainerId': attempt.provider_container_id,
        'error': attempt.error_message,
        'publishedAt': (
            attempt.completed_at.isoformat()
            if attempt.status == SocialDeliveryAttempt.Status.SUCCEEDED and attempt.completed_at
            else None
        ),
    }


def _finalize_attempt(*, attempt_id, status, provider_post_id='', error_message=''):
    with transaction.atomic():
        attempt = SocialDeliveryAttempt.objects.select_for_update().get(pk=attempt_id)
        attempt.status = status
        attempt.provider_post_id = str(provider_post_id)[:180]
        attempt.error_message = str(error_message)[:500]
        attempt.completed_at = timezone.now() if status in (
            SocialDeliveryAttempt.Status.SUCCEEDED,
            SocialDeliveryAttempt.Status.FAILED,
        ) else None
        attempt.save(update_fields=(
            'status', 'provider_post_id', 'error_message', 'completed_at', 'updated_at',
        ))
        return attempt


def _remember_publish_id(attempt_id, publish_id):
    with transaction.atomic():
        attempt = SocialDeliveryAttempt.objects.select_for_update().get(pk=attempt_id)
        attempt.provider_container_id = str(publish_id)[:180]
        attempt.save(update_fields=('provider_container_id', 'updated_at'))
        return attempt


def _claim_attempt(*, business, job_id):
    probe = get_object_or_404(
        SocialPublishingJob.objects.select_related('channel__storefront'),
        pk=job_id,
        channel__storefront__business=business,
        channel__platform=SocialChannel.Platform.TIKTOK,
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
            )
            .get(pk=probe.pk)
        )
        if job.status == SocialPublishingJob.Status.CANCELLED:
            raise ValidationError({'tiktok': 'This publishing record is cancelled.'})
        if not _eligible(job, business):
            raise ValidationError({'tiktok': 'This product is not currently eligible for TikTok publishing.'})

        attempt, _ = SocialDeliveryAttempt.objects.select_for_update().get_or_create(
            job=job,
            fingerprint=job.fingerprint,
            defaults={'status': SocialDeliveryAttempt.Status.FAILED},
        )
        if attempt.status == SocialDeliveryAttempt.Status.SUCCEEDED:
            return job, attempt, False
        if attempt.status == SocialDeliveryAttempt.Status.IN_PROGRESS:
            raise TikTokProductDeliveryConflict('This TikTok product post is already being processed.')
        if attempt.status == SocialDeliveryAttempt.Status.UNKNOWN:
            raise TikTokProductDeliveryConflict(
                'The previous TikTok product-post outcome is unknown. Check its status before attempting another post.'
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


class TikTokProductPublishInput(serializers.Serializer):
    title = serializers.CharField(allow_blank=True, max_length=4000, trim_whitespace=False)
    description = serializers.CharField(allow_blank=True, max_length=12000, trim_whitespace=False)
    privacy = serializers.ChoiceField(choices=PRIVACY_LEVELS)
    allowComments = serializers.BooleanField(default=False)
    autoAddMusic = serializers.BooleanField(default=False)
    disclosure = serializers.BooleanField(default=False)
    ownBrand = serializers.BooleanField(default=False)
    branded = serializers.BooleanField(default=False)
    consent = serializers.BooleanField()

    def validate(self, attrs):
        if not attrs['consent']:
            raise serializers.ValidationError('Confirm TikTok Music Usage Confirmation before publishing.')
        if _utf16_units(attrs['title']) > 90:
            raise serializers.ValidationError({'title': 'TikTok photo titles can contain at most 90 UTF-16 characters.'})
        if _utf16_units(attrs['description']) > 4000:
            raise serializers.ValidationError({'description': 'TikTok photo descriptions can contain at most 4000 UTF-16 characters.'})
        if attrs['disclosure'] and not (attrs['ownBrand'] or attrs['branded']):
            raise serializers.ValidationError('Choose Your brand, Branded content, or both when content disclosure is enabled.')
        if not attrs['disclosure'] and (attrs['ownBrand'] or attrs['branded']):
            raise serializers.ValidationError('Enable content disclosure before selecting a commercial-content type.')
        if attrs['branded'] and attrs['privacy'] == 'SELF_ONLY':
            raise serializers.ValidationError('Branded content cannot use Only me visibility on TikTok.')
        return attrs


class TikTokProductOwnerView(APIView):
    permission_classes = (IsAuthenticated,)
    throttle_classes = (ConnectionThrottle,)


class TikTokProductPrepareAPIView(TikTokProductOwnerView):
    def post(self, request, business_id, job_id):
        business = owner_business(request, business_id)
        job = _job_for(business, job_id)
        credential_row, credential_payload = _connection_for(business)
        creator = _creator_info(credential_row, credential_payload)
        # Build the signed URL now so a missing product photo or invalid public
        # media origin is discovered before the user reaches the final button.
        photo_url = _photo_url_for(job)
        title, description = _default_text(job)
        response = Response({
            'creator': creator,
            'photoUrl': photo_url,
            'title': title,
            'description': description,
        })
        response['Cache-Control'] = 'no-store'
        return response


class TikTokProductPublishJobAPIView(TikTokProductOwnerView):
    def post(self, request, business_id, job_id):
        business = owner_business(request, business_id)
        form = TikTokProductPublishInput(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data

        job = _job_for(business, job_id)
        credential_row, credential_payload = _connection_for(business)
        creator = _creator_info(credential_row, credential_payload)
        if data['privacy'] not in creator['privacyOptions']:
            raise ValidationError({'privacy': 'Choose an audience currently allowed by TikTok.'})
        if data['allowComments'] and creator['commentDisabled']:
            raise ValidationError({'allowComments': 'TikTok has disabled comments for this account.'})

        photo_url = _photo_url_for(job)
        job, attempt, should_send = _claim_attempt(business=business, job_id=job_id)
        if not should_send:
            response = Response(_attempt_response(attempt))
            response['Cache-Control'] = 'no-store'
            return response

        post_info = {
            'title': data['title'],
            'description': data['description'],
            'privacy_level': data['privacy'],
            'disable_comment': not data['allowComments'],
            'auto_add_music': data['autoAddMusic'],
            'brand_content_toggle': data['branded'],
            'brand_organic_toggle': data['ownBrand'],
        }
        body = {
            'media_type': 'PHOTO',
            'post_mode': 'DIRECT_POST',
            'post_info': post_info,
            'source_info': {
                'source': 'PULL_FROM_URL',
                'photo_images': [photo_url],
                'photo_cover_index': 0,
            },
        }

        try:
            result = _remote(
                'content/init/',
                credential_row,
                credential_payload,
                body,
                uncertain_on_transport=True,
            )
            publish_id = result.get('publish_id')
            if not isinstance(publish_id, str) or not publish_id or len(publish_id) > 64:
                raise TikTokRemoteFailure(
                    'TikTok did not return a valid tracking ID. Check TikTok before attempting another product post.',
                    uncertain=True,
                )
            attempt = _remember_publish_id(attempt.id, publish_id)
        except TikTokRemoteFailure as exc:
            attempt = _finalize_attempt(
                attempt_id=attempt.id,
                status=(
                    SocialDeliveryAttempt.Status.UNKNOWN
                    if exc.uncertain
                    else SocialDeliveryAttempt.Status.FAILED
                ),
                error_message=exc.message,
            )

        response = Response(_attempt_response(attempt))
        response['Cache-Control'] = 'no-store'
        return response


class TikTokProductStatusAPIView(TikTokProductOwnerView):
    def post(self, request, business_id, job_id):
        business = owner_business(request, business_id)
        job = get_object_or_404(
            SocialPublishingJob.objects.select_related('channel__storefront'),
            pk=job_id,
            channel__storefront__business=business,
            channel__platform=SocialChannel.Platform.TIKTOK,
        )
        attempt = (
            SocialDeliveryAttempt.objects.filter(job=job, fingerprint=job.fingerprint)
            .order_by('-updated_at', '-id')
            .first()
        )
        if attempt is None:
            raise ValidationError({'tiktok': 'This product has not been submitted to TikTok yet.'})
        if attempt.status in (SocialDeliveryAttempt.Status.SUCCEEDED, SocialDeliveryAttempt.Status.FAILED):
            response = Response(_attempt_response(attempt))
            response['Cache-Control'] = 'no-store'
            return response
        if not attempt.provider_container_id:
            raise TikTokProductDeliveryConflict(
                'StockFlow does not have a TikTok tracking ID for this uncertain delivery. Check TikTok before posting again.'
            )

        credential_row, credential_payload = _connection_for(business)
        try:
            result = _remote(
                'status/fetch/',
                credential_row,
                credential_payload,
                {'publish_id': attempt.provider_container_id},
            )
        except TikTokRemoteFailure as exc:
            raise ValidationError({'tiktok': exc.message}) from exc

        status = str(result.get('status', '')).strip().upper()
        if status == 'PUBLISH_COMPLETE':
            public_ids = result.get('publicaly_available_post_id')
            post_id = ''
            if isinstance(public_ids, list) and public_ids:
                post_id = str(public_ids[0])
            attempt = _finalize_attempt(
                attempt_id=attempt.id,
                status=SocialDeliveryAttempt.Status.SUCCEEDED,
                provider_post_id=post_id,
            )
        elif status == 'FAILED':
            reason = str(result.get('fail_reason', '')).strip()
            safe_reason = reason if re.fullmatch(r'[a-zA-Z0-9_]{1,100}', reason) else 'processing_failed'
            attempt = _finalize_attempt(
                attempt_id=attempt.id,
                status=SocialDeliveryAttempt.Status.FAILED,
                error_message='TikTok could not publish this product: ' + safe_reason,
            )
        elif status not in {'PROCESSING_DOWNLOAD', 'PROCESSING_UPLOAD'}:
            attempt = _finalize_attempt(
                attempt_id=attempt.id,
                status=SocialDeliveryAttempt.Status.UNKNOWN,
                error_message='TikTok returned an unrecognized processing status. Check TikTok before attempting another product post.',
            )

        response = Response(_attempt_response(attempt))
        response['Cache-Control'] = 'no-store'
        return response


def _tiktok_product_jpeg(photo):
    """Render a delivery copy; never modify the stored product photo."""
    from io import BytesIO
    from PIL import Image, ImageOps

    output = BytesIO()
    with photo.image.storage.open(photo.image.name, 'rb') as source:
        with Image.open(source) as original:
            oriented = ImageOps.exif_transpose(original)
            oriented.thumbnail((1080, 1080), Image.Resampling.LANCZOS)
            if oriented.mode in ('RGBA', 'LA') or 'transparency' in oriented.info:
                rgba = oriented.convert('RGBA')
                converted = Image.new('RGB', rgba.size, 'white')
                converted.paste(rgba, mask=rgba.getchannel('A'))
            else:
                converted = oriented.convert('RGB')
            converted.save(output, format='JPEG', quality=90, optimize=True)
    output.seek(0)
    return output


class TikTokProductMediaAPIView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get(self, request):
        token = str(request.query_params.get('token', '')).strip()
        if not token:
            raise Http404()
        try:
            data = signing.loads(token, salt=MEDIA_SALT, max_age=MEDIA_MAX_AGE_SECONDS)
            job = SocialPublishingJob.objects.select_related(
                'channel__storefront__branch',
                'listing__product',
                'listing__product__uploaded_photo',
            ).get(
                pk=data['job'],
                fingerprint=data['fingerprint'],
                channel__platform=SocialChannel.Platform.TIKTOK,
            )
            photo = _product_photo(job)
            if (
                photo is None
                or str(photo.id) != str(data['photo'])
                or str(photo.version) != str(data['version'])
            ):
                raise Http404()
            eligible = (
                job.channel.auto_publish
                and job.channel.storefront.is_published
                and job.channel.storefront.branch.is_active
                and job.listing.is_published
                and job.listing.product.is_active
            )
            if not eligible:
                raise Http404()
            image_file = _tiktok_product_jpeg(photo)
        except (
            signing.BadSignature,
            SocialPublishingJob.DoesNotExist,
            KeyError,
            ValueError,
            OSError,
        ) as exc:
            raise Http404() from exc

        content_type = 'image/jpeg'
        response = FileResponse(image_file, content_type=content_type)
        response['Cache-Control'] = 'no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
