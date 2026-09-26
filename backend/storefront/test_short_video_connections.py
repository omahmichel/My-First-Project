from datetime import timedelta
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from integrations.provider_credentials import get_provider_credential
from . import test_management
from .models import SocialAuthorizationRequest

CONFIG = dict(DEBUG=True,
    STOCKFLOW_TIKTOK_CLIENT_ID='test-client', STOCKFLOW_TIKTOK_CLIENT_SECRET='test-secret',
    STOCKFLOW_TIKTOK_REDIRECT_URI='https://stockflow.example/api/storefront/social/tiktok/callback/',
    STOCKFLOW_SNAPCHAT_CLIENT_ID='snap-client', STOCKFLOW_SNAPCHAT_CLIENT_SECRET='snap-secret',
    STOCKFLOW_SNAPCHAT_REDIRECT_URI='https://stockflow.example/api/storefront/social/snapchat/callback/',
    STOCKFLOW_SOCIAL_RETURN_URL='https://stockflow.example/building-materials/online-shop',
    ALLOWED_HOSTS=['testserver', 'localhost'])

@override_settings(**CONFIG)
class ShortVideoConnectionTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        test_management.ShopSettingsApiTests.setUp(self)
        self.base = f'/api/businesses/{self.business.id}/storefront/social/'

    def start(self, provider='tiktok'):
        r = self.client.post(self.base + provider + '/connect/', {}, format='json')
        self.assertEqual(r.status_code, 200)
        return parse_qs(urlsplit(r.data['authorizeUrl']).query)['state'][0]

    def callback(self, state, provider='tiktok', **kwargs):
        r = self.client.get('/api/storefront/social/' + provider + '/callback/',
                            {'state': state, 'code': 'private-code', **kwargs})
        self.assertEqual(r.status_code, 302)
        self.assertNotIn('private-code', r.url)
        return parse_qs(urlsplit(r.url).query)['sfRequest'][0]

    def finish(self, request_id, provider='tiktok'):
        return self.client.post(self.base + provider + '/finish/', {'requestId': request_id}, format='json')

    @patch('storefront.short_video_connections.provider_request')
    def test_tiktok_connect_finish_encrypted_and_single_use(self, remote):
        request_id = self.callback(self.start())
        remote.side_effect = [
            {'access_token': 'private-access', 'refresh_token': 'private-refresh', 'expires_in': 3600,
             'refresh_expires_in': 86400, 'scope': 'user.info.basic,video.publish', 'open_id': 'creator'},
            {'error': {'code': 'ok'}, 'data': {'user': {'open_id': 'creator', 'display_name': 'Test creator'}}},
        ]
        result = self.finish(request_id)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data['connectionStatus'], 'connected')
        self.assertFalse(result.data['deliveryAvailable'])
        self.assertNotIn('private-access', str(result.data))
        row, payload = get_provider_credential(business=self.business, category='social', provider='tiktok')
        self.assertEqual(payload['account_id'], 'creator')
        self.assertNotIn('private-access', row.encrypted_payload)
        self.assertEqual(self.finish(request_id).status_code, 404)
        self.assertEqual(remote.call_count, 2)

    @patch('storefront.short_video_connections.provider_request')
    def test_snapchat_requires_verified_public_profile(self, remote):
        request_id = self.callback(self.start('snapchat'), 'snapchat')
        remote.side_effect = [
            {'access_token': 'a', 'refresh_token': 'r', 'expires_in': 3600, 'scope': 'snapchat-profile-api'},
            {'request_status': 'SUCCESS', 'public_profile': {'id': 'profile-1', 'display_name': 'Shop profile'}},
        ]
        result = self.finish(request_id, 'snapchat')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data['accountName'], 'Shop profile')
        self.assertFalse(result.data['deliveryAvailable'])

    def test_guest_cannot_start_or_finish(self):
        self.client.force_authenticate(None)
        self.assertIn(self.client.post(self.base + 'tiktok/connect/').status_code, (401, 403))
        self.assertIn(self.finish('invalid').status_code, (401, 403))

    def test_wrong_owner_cannot_finish(self):
        request_id = self.callback(self.start())
        user = get_user_model().objects.create_user(email='other-social@example.com', password=None)
        self.client.force_authenticate(user)
        self.assertIn(self.finish(request_id).status_code, (403, 404))
        self.assertFalse(SocialAuthorizationRequest.objects.get(pk=request_id).consumed)

    def test_expired_and_wrong_provider_states_rejected(self):
        state = self.start()
        url = '/api/storefront/social/'
        self.assertEqual(self.client.get(url + 'snapchat/callback/', {'state': state, 'code': 'a'}).status_code, 400)
        SocialAuthorizationRequest.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.get(url + 'tiktok/callback/', {'state': state, 'code': 'a'}).status_code, 400)

    def test_cancel_and_disconnect_invalidate_pending_requests(self):
        request_id = self.callback(self.start(), error='access_denied')
        self.assertEqual(self.finish(request_id).status_code, 404)
        self.start()
        self.assertEqual(self.client.delete(self.base + 'tiktok/connection/').status_code, 200)
        self.assertFalse(SocialAuthorizationRequest.objects.filter(business=self.business).exists())

    @override_settings(STOCKFLOW_TIKTOK_CLIENT_SECRET='')
    def test_unconfigured_channel_is_honest(self):
        r = self.client.get(self.base + 'tiktok/connection/')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data['configured'])
        self.assertFalse(r.data['deliveryAvailable'])
        self.assertEqual(self.client.post(self.base + 'tiktok/connect/').status_code, 503)

    def test_malformed_request_is_validation_error(self):
        self.assertEqual(self.finish('not-a-uuid').status_code, 400)

    @patch('storefront.short_video_connections.provider_request')
    def test_missing_scope_never_saves_connection(self, remote):
        request_id = self.callback(self.start())
        remote.return_value = {'access_token': 'a', 'refresh_token': 'r', 'expires_in': 3600, 'scope': 'user.info.basic'}
        self.assertEqual(self.finish(request_id).status_code, 400)
        row, _ = get_provider_credential(business=self.business, category='social', provider='tiktok')
        self.assertIsNone(row)
