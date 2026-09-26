from datetime import timedelta
from unittest.mock import patch
import uuid
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from django.core import signing
from inventory.models import Product, ProductVideo
from integrations.provider_credentials import save_provider_credential
from . import test_management
from .models import TikTokPublication
from .tiktok_publishing import SALT, RemoteFailure

INFO = {'creator_nickname': 'StockFlow_GH', 'creator_username': 'stockflow_gh',
    'privacy_level_options': ['SELF_ONLY', 'PUBLIC_TO_EVERYONE'], 'comment_disabled': False,
    'duet_disabled': True, 'stitch_disabled': True, 'max_video_post_duration_sec': 60}

@override_settings(DEBUG=True, ALLOWED_HOSTS=['testserver', 'localhost'],
                   STOCKFLOW_TIKTOK_MEDIA_BASE_URL='https://media.example.com')
class TikTokPublishingTests(TestCase):
    def setUp(self):
        test_management.ShopSettingsApiTests.setUp(self)
        from django.core.cache import cache
        cache.clear()
        self.product = Product.objects.create(business=self.business, name='Product', sku='TT-1', category='General')
        self.video = ProductVideo.objects.create(product=self.product, video='product-videos/test.mp4')
        self.payload = {'account_id': 'creator', 'account_name': 'StockFlow_GH',
                        'access_token': 'private-token', 'refresh_token': 'private-refresh', 'scope': 'video.publish'}
        self.save_credential()
        self.base = f'/api/businesses/{self.business.pk}/storefront/social/tiktok/'
        self.form = {'caption': 'My product', 'privacy': 'SELF_ONLY', 'consent': True}
    def save_credential(self):
        save_provider_credential(business=self.business, category='social', provider='tiktok',
            payload=self.payload, created_by=self.owner, access_expires_at=timezone.now()+timedelta(hours=1))
    def draft(self):
        return TikTokPublication.objects.create(business=self.business, video=self.video, video_version=self.video.version,
            account_id='creator', account_name='StockFlow_GH')
    def publish(self, row, **extra):
        return self.client.post(self.base+f'posts/{row.pk}/publish/', {**self.form, **extra}, format='json')

    @patch('storefront.tiktok_publishing.inspect_video', return_value=12)
    @patch('storefront.tiktok_publishing.creator', return_value=INFO)
    @patch('storefront.tiktok_publishing.remote', return_value={'publish_id': 'pub-1'})
    def test_submission_is_single_use_and_processing_not_success(self, remote, creator, inspect):
        row = self.draft()
        result = self.publish(row)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data['status'], 'processing')
        self.publish(row)
        self.assertEqual(remote.call_count, 1)
        body = remote.call_args.args[2]
        self.assertEqual(body['source_info']['source'], 'PULL_FROM_URL')
        self.assertTrue(body['source_info']['video_url'].startswith('https://media.example.com/'))
        self.assertTrue(body['post_info']['disable_comment'])
        self.assertNotIn('private-token', str(result.data))

    @patch('storefront.tiktok_publishing.inspect_video', return_value=12)
    @patch('storefront.tiktok_publishing.creator', return_value=INFO)
    @patch('storefront.tiktok_publishing.remote')
    def test_consent_privacy_interactions_disclosure_enforced(self, remote, creator, inspect):
        for extra in [{'consent': False}, {'privacy': 'FOLLOWER_OF_CREATOR'}, {'duet': True},
                      {'disclosure': True}, {'disclosure': True, 'branded': True}, {'ownBrand': True},
                      {'caption': '😀'*1101}]:
            self.assertEqual(self.publish(self.draft(), **extra).status_code, 400)
        remote.assert_not_called()

    @patch('storefront.tiktok_publishing.inspect_video', return_value=12)
    @patch('storefront.tiktok_publishing.creator', return_value=INFO)
    @patch('storefront.tiktok_publishing.remote', side_effect=RemoteFailure('Timeout', True))
    def test_timeout_is_unknown_and_never_automatically_retried(self, remote, creator, inspect):
        row=self.draft()
        self.assertEqual(self.publish(row).data['status'], 'unknown')
        self.publish(row)
        self.assertEqual(remote.call_count, 1)

    @patch('storefront.tiktok_publishing.remote', return_value={'status':'PUBLISH_COMPLETE'})
    def test_status_uses_saved_tracking_id(self, remote):
        row=self.draft(); row.status='processing'; row.publish_id='pub-1'; row.save()
        result=self.client.post(self.base+f'posts/{row.pk}/status/', {}, format='json')
        self.assertEqual(result.data['status'], 'published')
        self.assertEqual(remote.call_args.args[2], {'publish_id':'pub-1'})

    def test_owner_bound_and_anonymous_denied(self):
        row=self.draft()
        self.client.force_authenticate(None)
        self.assertIn(self.publish(row).status_code, (401,403))
        other=get_user_model().objects.create_user(email='outsider@example.com', password=None)
        self.client.force_authenticate(other)
        self.assertIn(self.publish(row).status_code, (403,404))
        self.assertIn(self.client.get(self.base+'videos/').status_code, (403,404))

    def test_changed_video_and_account_rejected(self):
        row=self.draft()
        self.video.version=uuid.uuid4(); self.video.save()
        self.assertEqual(self.publish(row).status_code,404)
        row=self.draft(); self.payload['account_id']='changed'; self.save_credential()
        self.assertEqual(self.publish(row).status_code,400)

    @patch('storefront.tiktok_publishing.inspect_video', return_value=61)
    @patch('storefront.tiktok_publishing.creator', return_value=INFO)
    def test_duration_checked_before_preparation(self, creator, inspect):
        result=self.client.post(self.base+'prepare/', {'videoId':str(self.video.pk)}, format='json')
        self.assertEqual(result.status_code,400)
        self.assertFalse(TikTokPublication.objects.exists())

    def test_media_requires_valid_signature_and_consented_attempt(self):
        row=self.draft()
        token=signing.dumps({'post':str(row.pk),'version':str(self.video.version)},salt=SALT)
        self.assertEqual(self.client.get('/api/storefront/social/tiktok/media/'+token+'/video.mp4').status_code,404)
        self.assertEqual(self.client.get('/api/storefront/social/tiktok/media/bad/video.mp4').status_code,404)

    @patch('storefront.tiktok_publishing.inspect_video', return_value=12)
    @patch('storefront.tiktok_publishing.creator', return_value=INFO)
    def test_previews_reuse_draft_and_block_uncertain_duplicate(self, creator, inspect):
        data={'videoId':str(self.video.pk)}
        first=self.client.post(self.base+'prepare/',data,format='json')
        second=self.client.post(self.base+'prepare/',data,format='json')
        self.assertEqual(first.status_code,200)
        self.assertEqual(first.data['id'],second.data['id'])
        TikTokPublication.objects.update(status='unknown')
        self.assertEqual(self.client.post(self.base+'prepare/',data,format='json').status_code,400)

    @patch('storefront.tiktok_publishing.remote')
    def test_expired_preview_does_not_call_tiktok(self, remote):
        row=self.draft()
        TikTokPublication.objects.filter(pk=row.pk).update(created_at=timezone.now()-timedelta(minutes=11))
        self.assertEqual(self.publish(row).status_code,400)
        remote.assert_not_called()
