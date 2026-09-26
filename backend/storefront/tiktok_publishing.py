"""Owner-approved product videos sent with PULL_FROM_URL; conservative retries."""
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from datetime import timedelta
from urllib.parse import urlsplit
import requests
from django.conf import settings
from django.core import signing
from django.db import transaction
from businesses.models import Business
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from inventory.models import ProductVideo
from inventory.video_urls import product_video_url
from integrations.provider_credentials import get_provider_credential
from .management import owner_business
from .models import TikTokPublication
from .short_video_connections import ConnectionThrottle, safe_response

SALT = 'stockflow-tiktok-media-v1'
API = 'https://open.tiktokapis.com/v2/post/publish/'

def setting(name):
    return str(getattr(settings, name, os.getenv(name, ''))).strip()

def media_base():
    value = setting('STOCKFLOW_TIKTOK_MEDIA_BASE_URL').rstrip('/')
    u = urlsplit(value)
    if u.scheme != 'https' or not u.hostname or u.username or u.password or u.query or u.fragment or u.path:
        raise ValidationError('Configure a verified public HTTPS TikTok media origin before publishing.')
    return value

def credential(business, account=None):
    row, payload = get_provider_credential(business=business, category='social', provider='tiktok')
    if not row or not payload.get('account_id'):
        raise ValidationError('Connect TikTok first.')
    if account and payload['account_id'] != account:
        raise ValidationError('The TikTok account changed. Open a new publishing preview.')
    if not row.access_expires_at or row.access_expires_at <= timezone.now() + timedelta(seconds=60):
        raise ValidationError('Click Verify connection to renew TikTok access, then try again.')
    if 'video.publish' not in payload.get('scope', '').replace(',', ' ').split():
        raise ValidationError('Reconnect TikTok and allow posting.')
    return payload

class RemoteFailure(Exception):
    def __init__(self, message, uncertain=False):
        self.message, self.uncertain = message, uncertain

ERRORS = {
    'unaudited_client_can_only_post_to_private_accounts': 'TikTok requires a private account for this unaudited app. Use a private test account.',
    'url_ownership_unverified': 'Verify the media origin in TikTok URL properties before publishing.',
    'privacy_level_option_mismatch': 'TikTok privacy options changed. Open a new preview.',
    'access_token_invalid': 'TikTok access expired. Verify the connection or reconnect.',
    'scope_not_authorized': 'Reconnect TikTok and approve posting permission.',
    'rate_limit_exceeded': 'TikTok rate limit reached. Wait before checking again.',
    'spam_risk_too_many_posts': 'TikTok daily posting limit reached. Try another day.',
    'reached_active_user_cap': 'TikTok app testing quota reached. Try another day.',
    'spam_risk_user_banned_from_posting': 'TikTok has blocked posting for this account.',
}

def remote(endpoint, payload, body):
    try:
        r = requests.post(API + endpoint, headers={'Authorization': 'Bearer ' + payload['access_token']},
                          json=body, timeout=25, allow_redirects=False)
        data = r.json()
    except (requests.RequestException, ValueError):
        raise RemoteFailure('TikTok did not return a usable response. Check your account before attempting another post.', True)
    if not isinstance(data, dict):
        raise RemoteFailure('TikTok returned an unreadable response.', True)
    code = data.get('error', {}).get('code') if isinstance(data.get('error'), dict) else None
    if r.status_code >= 500:
        raise RemoteFailure('TikTok is temporarily unavailable. The posting outcome may be unknown.', True)
    if r.status_code != 200 or code != 'ok':
        raise RemoteFailure(ERRORS.get(code, 'TikTok rejected this request. Review the account and post settings.'))
    if not isinstance(data.get('data'), dict):
        raise RemoteFailure('TikTok response was incomplete.', True)
    return data['data']

def creator(payload):
    try:
        result = remote('creator_info/query/', payload, {})
    except RemoteFailure as exc:
        raise ValidationError(exc.message)
    keys = ('creator_nickname', 'creator_username', 'privacy_level_options', 'comment_disabled',
            'duet_disabled', 'stitch_disabled', 'max_video_post_duration_sec')
    if not isinstance(result.get('privacy_level_options'), list) or not result.get('creator_nickname'):
        raise ValidationError('TikTok did not return usable creator settings.')
    return {k: result.get(k) for k in keys}

def inspect_video(video):
    executable = setting('STOCKFLOW_FFPROBE_PATH') or shutil.which('ffprobe')
    if not executable:
        raise ValidationError('Install FFmpeg (including ffprobe) on the backend computer to validate videos.')
    # ffprobe reads a local copy only: no remote URL or shell evaluation.
    try:
        with tempfile.TemporaryDirectory(prefix='stockflow_tiktok_') as folder:
            path = os.path.join(folder, 'video.mp4')
            with video.video.storage.open(video.video.name, 'rb') as src, open(path, 'wb') as dst:
                total = 0
                while chunk := src.read(1024 * 1024):
                    total += len(chunk)
                    if total > 100 * 1024 * 1024:
                        raise ValidationError('Select a product video up to 100 MB.')
                    dst.write(chunk)
            proc = subprocess.run([executable, '-v', 'error', '-protocol_whitelist', 'file',
                '-show_entries', 'format=duration:stream=codec_type,width,height', '-of', 'json', path],
                capture_output=True, text=True, timeout=30, check=True)
            info = json.loads(proc.stdout)
            duration = float(info['format']['duration'])
            stream = next(s for s in info['streams'] if s.get('codec_type') == 'video')
            if not math.isfinite(duration) or duration < 3 or not all(360 <= int(stream[k]) <= 4096 for k in ('width', 'height')):
                raise ValidationError('Use a video at least 3 seconds long, with both dimensions between 360 and 4096 pixels.')
            return duration
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, StopIteration):
        raise ValidationError('The stored video could not be validated. Check FFmpeg and the video file.')

def row_data(row):
    status = row.status
    if status == 'submitting' and row.updated_at < timezone.now() - timedelta(minutes=2):
        status = 'unknown'
    return {'id': str(row.pk), 'status': status, 'accountName': row.account_name,
            'message': row.message, 'caption': row.post_info.get('title', ''), 'createdAt': row.created_at.isoformat()}

class PublishInput(serializers.Serializer):
    caption = serializers.CharField(max_length=2200, allow_blank=True, trim_whitespace=False)
    privacy = serializers.ChoiceField(choices=['SELF_ONLY', 'PUBLIC_TO_EVERYONE', 'MUTUAL_FOLLOW_FRIENDS', 'FOLLOWER_OF_CREATOR'])
    comment = serializers.BooleanField(default=False)
    duet = serializers.BooleanField(default=False)
    stitch = serializers.BooleanField(default=False)
    disclosure = serializers.BooleanField(default=False)
    ownBrand = serializers.BooleanField(default=False)
    branded = serializers.BooleanField(default=False)
    aigc = serializers.BooleanField(default=False)
    consent = serializers.BooleanField()

class OwnerView(APIView):
    permission_classes = (IsAuthenticated,)
    throttle_classes = (ConnectionThrottle,)

class TikTokVideosAPIView(OwnerView):
    def get(self, request, business_id):
        business = owner_business(request, business_id)
        videos = ProductVideo.objects.filter(product__business=business, product__is_active=True).select_related('product').order_by('product__name')
        return safe_response({'videos': [{'id': str(v.pk), 'name': v.product.name,
            'previewUrl': product_video_url(v.product, private=True)} for v in videos],
            'posts': [row_data(r) for r in TikTokPublication.objects.filter(business=business).exclude(status='draft')[:20]]})

class TikTokPrepareAPIView(OwnerView):
    def post(self, request, business_id):
        business = owner_business(request, business_id)
        s = serializers.UUIDField()
        video = get_object_or_404(ProductVideo, pk=s.run_validation(request.data.get('videoId')),
                                 product__business=business, product__is_active=True)
        payload = credential(business)
        info = creator(payload)
        duration = inspect_video(video)
        if duration > (info.get('max_video_post_duration_sec') or 0):
            raise ValidationError('This video exceeds the duration TikTok permits for your account.')
        media_base()
        with transaction.atomic():
            Business.objects.select_for_update().get(pk=business.pk)
            related = TikTokPublication.objects.filter(business=business, video=video,
                video_version=video.version, account_id=payload['account_id'])
            if related.filter(status__in=['submitting', 'processing', 'unknown']).exists():
                raise ValidationError('This video already has a pending or uncertain attempt. Check its history and TikTok before another post.')
            row = related.filter(status='draft', created_at__gt=timezone.now()-timedelta(minutes=10)).first()
            if row is None:
                row = TikTokPublication.objects.create(business=business, video=video, video_version=video.version,
                    account_id=payload['account_id'], account_name=info['creator_nickname'])
        return safe_response({'id': str(row.pk), 'creator': info, 'duration': duration,
            'previewUrl': product_video_url(video.product, private=True)})

class TikTokPublishAPIView(OwnerView):
    def post(self, request, business_id, post_id):
        business = owner_business(request, business_id)
        row = get_object_or_404(TikTokPublication, pk=post_id, business=business)
        if row.status != 'draft':
            return safe_response(row_data(row))
        form = PublishInput(data=request.data); form.is_valid(raise_exception=True)
        d = form.validated_data
        if not d['consent']:
            raise ValidationError('Confirm consent before publishing.')
        if len(d['caption'].encode('utf-16-le')) // 2 > 2200:
            raise ValidationError('Caption is longer than TikTok permits.')
        if row.created_at < timezone.now() - timedelta(minutes=10):
            raise ValidationError('Preview expired. Open a new preview.')
        video = get_object_or_404(ProductVideo, pk=row.video_id, version=row.video_version,
                                 product__business=business, product__is_active=True)
        payload = credential(business, row.account_id)
        info = creator(payload)
        if d['privacy'] not in info['privacy_level_options']:
            raise ValidationError('Choose an audience currently allowed by TikTok.')
        for field in ('comment', 'duet', 'stitch'):
            if d[field] and info.get(field + '_disabled') is not False:
                raise ValidationError('TikTok has disabled ' + field + ' for this account.')
        if d['disclosure'] and not (d['ownBrand'] or d['branded']):
            raise ValidationError('Select Your brand or Branded content.')
        if not d['disclosure'] and (d['ownBrand'] or d['branded']):
            raise ValidationError('Enable the commercial content disclosure setting.')
        if d['branded'] and d['privacy'] == 'SELF_ONLY':
            raise ValidationError('Branded content visibility cannot be private.')
        if inspect_video(video) > (info.get('max_video_post_duration_sec') or 0):
            raise ValidationError('The video is too long for this account.')
        token = signing.dumps({'post': str(row.pk), 'version': str(video.version)}, salt=SALT)
        url = media_base() + reverse('storefront:tiktok-media', kwargs={'token': token})
        post = {'title': d['caption'], 'privacy_level': d['privacy'], 'disable_comment': not d['comment'],
                'disable_duet': not d['duet'], 'disable_stitch': not d['stitch'],
                'brand_organic_toggle': d['ownBrand'], 'brand_content_toggle': d['branded'], 'is_aigc': d['aigc']}
        # Atomic claim prevents double submission even when a response is lost.
        claimed = TikTokPublication.objects.filter(pk=row.pk, status='draft').update(
            status='submitting', post_info=post, updated_at=timezone.now())
        if not claimed:
            row.refresh_from_db(); return safe_response(row_data(row))
        try:
            result = remote('video/init/', payload, {'post_info': post,
                'source_info': {'source': 'PULL_FROM_URL', 'video_url': url}})
            publish_id = result.get('publish_id')
            if not isinstance(publish_id, str) or not publish_id or len(publish_id) > 180:
                raise RemoteFailure('TikTok did not return a tracking ID. Check TikTok before another attempt.', True)
            row.publish_id, row.status = publish_id, 'processing'
            row.message = 'TikTok is processing your video. It may take a few minutes.'
        except RemoteFailure as exc:
            row.status = 'unknown' if exc.uncertain else 'failed'
            row.message = exc.message
        row.post_info = post
        row.save(update_fields=['publish_id', 'status', 'message', 'post_info', 'updated_at'])
        return safe_response(row_data(row))

class TikTokStatusAPIView(OwnerView):
    def post(self, request, business_id, post_id):
        business = owner_business(request, business_id)
        row = get_object_or_404(TikTokPublication, pk=post_id, business=business)
        if row.status != 'processing' or not row.publish_id:
            return safe_response(row_data(row))
        payload = credential(business, row.account_id)
        try:
            data = remote('status/fetch/', payload, {'publish_id': row.publish_id})
        except RemoteFailure as exc:
            raise ValidationError(exc.message)
        status = data.get('status')
        if status == 'PUBLISH_COMPLETE':
            row.status, row.message = 'published', 'TikTok confirmed publication.'
        elif status == 'FAILED':
            reason = str(data.get('fail_reason', ''))
            reason = reason if re.fullmatch(r'[a-zA-Z0-9_]{1,100}', reason) else 'processing_failed'
            row.status, row.message = 'failed', 'TikTok could not publish: ' + reason
        row.save(update_fields=['status', 'message', 'updated_at'])
        return safe_response(row_data(row))

class TikTokMediaAPIView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    def get(self, request, token):
        try:
            data = signing.loads(token, salt=SALT, max_age=3600)
            row = TikTokPublication.objects.select_related('video__product').get(pk=data['post'],
                video_version=data['version'], status__in=['submitting', 'processing', 'published', 'unknown'])
            if not row.video or str(row.video.version) != data['version'] or not row.video.product.is_active:
                raise Http404()
            file = row.video.video.storage.open(row.video.video.name, 'rb')
        except (signing.BadSignature, TikTokPublication.DoesNotExist, KeyError, ValueError, OSError):
            raise Http404()
        response = FileResponse(file, content_type=row.video.content_type)
        response['Cache-Control'] = 'no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
