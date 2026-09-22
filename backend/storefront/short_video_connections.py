"""TikTok and Snapchat OAuth connections. Publishing is a separate capability."""
import os
import uuid
import secrets
from datetime import timedelta
from urllib.parse import urlencode, urlsplit
import requests
from django.conf import settings
from django.core import signing
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView
from integrations.provider_credentials import (
    encrypt_provider_payload, decrypt_provider_payload, get_provider_credential,
    save_provider_credential, delete_provider_credential,
)
from .management import owner_business
from .models import SocialAuthorizationRequest

PROVIDERS = {
    'tiktok': ('https://www.tiktok.com/v2/auth/authorize/', 'https://open.tiktokapis.com/v2/oauth/token/', 'user.info.basic,video.publish'),
    'snapchat': ('https://accounts.snapchat.com/login/oauth2/authorize', 'https://accounts.snapchat.com/login/oauth2/access_token', 'snapchat-profile-api'),
}
SALT = 'stockflow.short-video.oauth.v1'

class ConnectionUnavailable(APIException):
    status_code = 503
    default_detail = 'This connection is not configured yet. Please contact StockFlow support.'

class ConnectionThrottle(UserRateThrottle):
    scope = 'short_video_connection'
    rate = '20/min'

def config(provider):
    if provider not in PROVIDERS:
        raise ValidationError('Unknown social connection.')
    prefix = 'STOCKFLOW_' + provider.upper()
    values = {key: str(getattr(settings, prefix + suffix, os.getenv(prefix + suffix, ''))).strip()
              for key, suffix in [('client_id', '_CLIENT_ID'), ('client_secret', '_CLIENT_SECRET'), ('redirect_uri', '_REDIRECT_URI')]}
    values['return_url'] = str(getattr(settings, 'STOCKFLOW_SOCIAL_RETURN_URL', os.getenv('STOCKFLOW_SOCIAL_RETURN_URL', ''))).strip()
    if not all(values.values()):
        raise ConnectionUnavailable()
    for key in ('redirect_uri', 'return_url'):
        url = urlsplit(values[key])
        if url.scheme != 'https' or not url.hostname or url.username or url.password or url.fragment or url.query:
            raise ConnectionUnavailable()
    return values

def safe_response(data, status=200):
    response = Response(data, status=status)
    response['Cache-Control'] = 'no-store'
    return response

def provider_request(method, url, **kwargs):
    try:
        result = requests.request(method, url, timeout=20, allow_redirects=False, **kwargs)
        data = result.json()
    except (requests.RequestException, ValueError) as exc:
        raise ValidationError('The provider could not be reached. Please reconnect and try again.') from exc
    if not 200 <= result.status_code < 300 or not isinstance(data, dict):
        raise ValidationError('The provider rejected this connection. Check your account access and reconnect.')
    error = data.get('error')
    if error and (not isinstance(error, dict) or error.get('code') not in (None, '', 'ok')):
        raise ValidationError('The provider could not authorize this request. Please reconnect.')
    return data

def profile(provider, access_token):
    headers = {'Authorization': 'Bearer ' + access_token}
    if provider == 'tiktok':
        data = provider_request('GET', 'https://open.tiktokapis.com/v2/user/info/', headers=headers,
                                params={'fields': 'open_id,display_name'})
        user = data.get('data', {}).get('user', {})
        identity, name = user.get('open_id'), user.get('display_name')
    else:
        data = provider_request('GET', 'https://businessapi.snapchat.com/v1/public_profiles/my_profile', headers=headers)
        if data.get('request_status') != 'SUCCESS':
            raise ValidationError('Snapchat Public Profile access could not be verified.')
        user = data.get('public_profile', {})
        identity, name = user.get('id'), user.get('display_name') or user.get('snap_user_name')
    if not isinstance(identity, str) or not identity or not isinstance(name, str) or not name:
        raise ValidationError('The provider did not return a usable account. Snapchat requires a Public Profile.')
    return {'account_id': identity[:180], 'account_name': name[:180]}

def expiry(seconds):
    try:
        seconds = int(seconds)
        if seconds <= 0 or seconds > 366 * 24 * 3600:
            raise ValueError()
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError('The provider returned an invalid token expiry.') from exc
    return timezone.now() + timedelta(seconds=seconds)

def token_pair(provider, data, previous=None):
    previous = previous or {}
    access = data.get('access_token')
    refresh = data.get('refresh_token') or previous.get('refresh_token')
    scope = data.get('scope', previous.get('scope', ''))
    if not isinstance(access, str) or not access or not isinstance(refresh, str) or not refresh or not isinstance(scope, str):
        raise ValidationError('The provider did not grant a complete connection. Please reconnect.')
    scopes = set(scope.replace(',', ' ').split())
    if not set(PROVIDERS[provider][2].replace(',', ' ').split()) <= scopes:
        raise ValidationError('Required account permissions were not granted. Please reconnect and approve them.')
    return {'access_token': access, 'refresh_token': refresh, 'scope': scope}, expiry(data.get('expires_in'))

def summary(business, provider):
    try:
        config(provider)
        configured = True
    except ConnectionUnavailable:
        configured = False
    row, payload = get_provider_credential(business=business, category='social', provider=provider)
    state = 'not_connected'
    if row and payload and payload.get('account_id'):
        state = 'expired' if not row.access_expires_at or row.access_expires_at <= timezone.now() else 'connected'
    return {'platform': provider, 'configured': configured, 'connectionStatus': state,
            'accountName': payload.get('account_name', '') if row and payload else '',
            'deliveryAvailable': False,
            'publishingStatus': 'not_enabled',
            'message': 'Account connection only. Publishing is not enabled yet.'}

class ShortVideoConnectAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    throttle_classes = (ConnectionThrottle,)

    def post(self, request, business_id, provider):
        business = owner_business(request, business_id)
        cfg = config(provider)
        # Check encryption configuration before sending anyone to the provider.
        encrypt_provider_payload({'check': True})
        with transaction.atomic():
            SocialAuthorizationRequest.objects.filter(expires_at__lte=timezone.now()).delete()
            SocialAuthorizationRequest.objects.filter(business=business, provider=provider, user=request.user).delete()
            row = SocialAuthorizationRequest.objects.create(business=business, user=request.user,
                provider=provider, nonce=secrets.token_urlsafe(32), expires_at=timezone.now() + timedelta(minutes=10))
        state = signing.dumps({'id': str(row.id), 'nonce': row.nonce, 'provider': provider}, salt=SALT)
        params = {'client_key' if provider == 'tiktok' else 'client_id': cfg['client_id'],
                  'redirect_uri': cfg['redirect_uri'], 'response_type': 'code', 'scope': PROVIDERS[provider][2], 'state': state}
        if provider == 'tiktok':
            params['disable_auto_auth'] = 1
        return safe_response({'authorizeUrl': PROVIDERS[provider][0] + '?' + urlencode(params)})

class ShortVideoCallbackAPIView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get(self, request, provider):
        cfg = config(provider)
        try:
            state = signing.loads(request.query_params.get('state', ''), salt=SALT, max_age=600)
            if state.get('provider') != provider:
                raise ValueError()
            row = SocialAuthorizationRequest.objects.get(id=state['id'], nonce=state['nonce'], provider=provider,
                expires_at__gt=timezone.now(), received=False, consumed=False)
        except (signing.BadSignature, SocialAuthorizationRequest.DoesNotExist, ValueError, KeyError, TypeError):
            raise ValidationError('This connection request is invalid or expired. Start again from StockFlow.')
        code = request.query_params.get('code', '')
        cancelled = bool(request.query_params.get('error'))
        if not cancelled and (not code or len(code) > 4096):
            raise ValidationError('The provider did not return an authorization code.')
        changed = SocialAuthorizationRequest.objects.filter(pk=row.pk, received=False, consumed=False).update(
            received=True, encrypted_code=encrypt_provider_payload({'code': code}) if not cancelled else '', consumed=cancelled)
        if not changed:
            raise ValidationError('This connection request has already been used.')
        # No provider code or token is placed in the frontend URL. Saving tokens
        # requires a subsequent authenticated request by this same business owner.
        response = HttpResponseRedirect(cfg['return_url'] + '?' + urlencode({
            'sfProvider': provider, 'sfRequest': str(row.pk), 'sfBusiness': str(row.business_id),
            'sfResult': 'cancelled' if cancelled else 'authorized'}))
        response['Cache-Control'] = 'no-store'
        response['Referrer-Policy'] = 'no-referrer'
        return response

class ShortVideoFinishAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    throttle_classes = (ConnectionThrottle,)

    def post(self, request, business_id, provider):
        business = owner_business(request, business_id)
        cfg = config(provider)
        try:
            request_id = uuid.UUID(str(request.data.get('requestId', '')))
        except (ValueError, TypeError, AttributeError):
            raise ValidationError('Choose a valid connection request.')
        with transaction.atomic():
            row = get_object_or_404(SocialAuthorizationRequest.objects.select_for_update(),
                id=request_id, business=business, user=request.user, provider=provider,
                received=True, consumed=False, expires_at__gt=timezone.now())
            code = decrypt_provider_payload(row.encrypted_code).get('code', '')
            row.consumed, row.encrypted_code = True, ''
            row.save(update_fields=['consumed', 'encrypted_code'])
        data = provider_request('POST', PROVIDERS[provider][1], data={
            'client_key' if provider == 'tiktok' else 'client_id': cfg['client_id'],
            'client_secret': cfg['client_secret'], 'code': code,
            'grant_type': 'authorization_code', 'redirect_uri': cfg['redirect_uri']})
        payload, access_expiry = token_pair(provider, data)
        payload.update(profile(provider, payload['access_token']))
        if provider == 'tiktok' and data.get('open_id') != payload['account_id']:
            raise ValidationError('The authorized account could not be verified.')
        refresh_expiry = expiry(data['refresh_expires_in']) if data.get('refresh_expires_in') else None
        with transaction.atomic():
            # Disconnect/new authorization invalidates an in-flight exchange.
            current = get_object_or_404(SocialAuthorizationRequest.objects.select_for_update(), pk=row.pk)
            owner_business(request, business_id)
            save_provider_credential(business=business, category='social', provider=provider,
                payload=payload, created_by=request.user, access_expires_at=access_expiry, refresh_expires_at=refresh_expiry)
            current.delete()
        return safe_response(summary(business, provider))

class ShortVideoConnectionAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    throttle_classes = (ConnectionThrottle,)

    def get(self, request, business_id, provider):
        business = owner_business(request, business_id)
        if provider not in PROVIDERS:
            raise ValidationError('Unknown social connection.')
        return safe_response(summary(business, provider))

    def post(self, request, business_id, provider):
        business = owner_business(request, business_id)
        cfg = config(provider)
        from integrations.models import ProviderCredential
        # Serialize refresh/reconnect/disconnect access to this credential row.
        with transaction.atomic():
            row, payload = get_provider_credential(business=business, category='social', provider=provider)
            if not row:
                raise ValidationError('Connect your account first.')
            ProviderCredential.objects.select_for_update().get(pk=row.pk)
            row, payload = get_provider_credential(business=business, category='social', provider=provider)
            if not row.access_expires_at or row.access_expires_at <= timezone.now() + timedelta(seconds=60):
                if row.refresh_expires_at and row.refresh_expires_at <= timezone.now():
                    raise ValidationError('This connection has expired. Please reconnect.')
                data = provider_request('POST', PROVIDERS[provider][1], data={
                    'client_key' if provider == 'tiktok' else 'client_id': cfg['client_id'],
                    'client_secret': cfg['client_secret'], 'grant_type': 'refresh_token',
                    'refresh_token': payload.get('refresh_token', '')})
                pair, access_expiry = token_pair(provider, data, payload)
                payload.update(pair)
                refresh_expiry = expiry(data['refresh_expires_in']) if data.get('refresh_expires_in') else row.refresh_expires_at
                save_provider_credential(business=business, category='social', provider=provider, payload=payload,
                    created_by=request.user, access_expires_at=access_expiry, refresh_expires_at=refresh_expiry)
        # A rotated token must remain saved even if the subsequent profile lookup fails.
        verified = profile(provider, payload['access_token'])
        if verified['account_id'] != payload['account_id']:
            raise ValidationError('The connected account changed. Please reconnect.')
        return safe_response(summary(business, provider))

    def delete(self, request, business_id, provider):
        business = owner_business(request, business_id)
        if provider not in PROVIDERS:
            raise ValidationError('Unknown social connection.')
        with transaction.atomic():
            SocialAuthorizationRequest.objects.filter(business=business, provider=provider).delete()
            delete_provider_credential(business=business, category='social', provider=provider)
        return safe_response({'connectionStatus': 'not_connected'})
