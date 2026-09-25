from datetime import timedelta
from unittest.mock import Mock, patch

import requests
from django.test import TestCase, override_settings
from django.utils import timezone

from integrations.provider_credentials import save_provider_credential

from . import test_listings
from .models import SocialDeliveryAttempt, SocialPublishingJob


@override_settings(
    ALLOWED_HOSTS=['testserver', 'localhost'],
    STOCKFLOW_TIKTOK_MEDIA_BASE_URL='https://verified.stockflow.test',
)
class TikTokProductDeliveryTests(TestCase):
    def setUp(self):
        test_listings.ShopListingApiTests.setUp(self)
        self.shop.is_published = True
        self.shop.save()
        self.social = f'/api/businesses/{self.business.id}/storefront/social/'
        self.assertEqual(
            self.client.patch(
                self.social + 'channels/tiktok/',
                {'autoPublish': True},
                format='json',
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.put(
                self.url,
                {
                    'isPublished': True,
                    'description': 'Quality tile',
                    'imageUrl': '',
                },
                format='json',
            ).status_code,
            201,
        )
        self.job = SocialPublishingJob.objects.get(channel__platform='tiktok')
        self.prepare_url = self.social + 'jobs/' + str(self.job.id) + '/prepare-tiktok/'
        self.publish_url = self.social + 'jobs/' + str(self.job.id) + '/publish-tiktok/'
        self.status_url = self.social + 'jobs/' + str(self.job.id) + '/check-tiktok/'
        save_provider_credential(
            business=self.business,
            category='social',
            provider='tiktok',
            payload={
                'access_token': 'tiktok-access',
                'refresh_token': 'tiktok-refresh',
                'scope': 'user.info.basic,video.publish',
                'account_id': 'OPEN-1',
                'account_name': 'StockFlow_GH',
            },
            created_by=self.owner,
            access_expires_at=timezone.now() + timedelta(hours=2),
            refresh_expires_at=timezone.now() + timedelta(days=30),
        )
        self.creator = {
            'nickname': 'StockFlow_GH',
            'username': 'stockflow_gh',
            'privacyOptions': ['SELF_ONLY'],
            'commentDisabled': False,
        }
        self.form = {
            'title': 'Quality Tile',
            'description': 'GH₵ 25.00',
            'privacy': 'SELF_ONLY',
            'allowComments': False,
            'autoAddMusic': False,
            'disclosure': True,
            'ownBrand': True,
            'branded': False,
            'consent': True,
        }

    @staticmethod
    def response(status_code, payload):
        result = Mock()
        result.status_code = status_code
        result.json.return_value = payload
        return result

    @patch('storefront.tiktok_product_delivery._photo_url_for', return_value='https://verified.stockflow.test/api/storefront/social/tiktok/product-media/?token=x')
    @patch('storefront.tiktok_product_delivery._creator_info')
    def test_prepare_returns_creator_options_and_editable_product_text(self, creator_info, photo_url):
        creator_info.return_value = self.creator
        response = self.client.post(self.prepare_url, {}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['creator']['privacyOptions'], ['SELF_ONLY'])
        self.assertTrue(response.data['title'])
        self.assertIn('Available from', response.data['description'])
        photo_url.assert_called_once()

    @patch('storefront.tiktok_product_delivery._photo_url_for', return_value='https://verified.stockflow.test/api/storefront/social/tiktok/product-media/?token=x')
    @patch('storefront.tiktok_product_delivery._creator_info')
    @patch('storefront.tiktok_product_delivery.requests.post')
    def test_publish_initializes_photo_direct_post_and_records_tracking_id(self, mocked_post, creator_info, _photo_url):
        creator_info.return_value = self.creator
        mocked_post.return_value = self.response(200, {
            'data': {'publish_id': 'p_pub_url~v2.123'},
            'error': {'code': 'ok', 'message': '', 'log_id': 'x'},
        })
        response = self.client.post(self.publish_url, self.form, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['deliveryStatus'], 'in_progress')
        self.assertEqual(response.data['remoteContainerId'], 'p_pub_url~v2.123')
        body = mocked_post.call_args.kwargs['json']
        self.assertEqual(body['media_type'], 'PHOTO')
        self.assertEqual(body['post_mode'], 'DIRECT_POST')
        self.assertEqual(body['source_info']['source'], 'PULL_FROM_URL')
        self.assertEqual(body['source_info']['photo_cover_index'], 0)
        self.assertEqual(body['post_info']['privacy_level'], 'SELF_ONLY')
        self.assertTrue(body['post_info']['brand_organic_toggle'])
        self.assertFalse(body['post_info']['brand_content_toggle'])
        attempt = SocialDeliveryAttempt.objects.get()
        self.assertEqual(attempt.attempt_count, 1)

    @patch('storefront.tiktok_product_delivery._photo_url_for', return_value='https://verified.stockflow.test/api/storefront/social/tiktok/product-media/?token=x')
    @patch('storefront.tiktok_product_delivery._creator_info')
    @patch('storefront.tiktok_product_delivery.requests.post')
    def test_ambiguous_submit_is_not_retried(self, mocked_post, creator_info, _photo_url):
        creator_info.return_value = self.creator
        mocked_post.side_effect = requests.Timeout('timeout')
        first = self.client.post(self.publish_url, self.form, format='json')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data['deliveryStatus'], 'unknown')
        second = self.client.post(self.publish_url, self.form, format='json')
        self.assertEqual(second.status_code, 409)
        self.assertEqual(mocked_post.call_count, 1)

    @patch('storefront.tiktok_product_delivery._photo_url_for', return_value='https://verified.stockflow.test/api/storefront/social/tiktok/product-media/?token=x')
    @patch('storefront.tiktok_product_delivery._creator_info')
    @patch('storefront.tiktok_product_delivery.requests.post')
    def test_status_check_marks_completed_post_succeeded(self, mocked_post, creator_info, _photo_url):
        creator_info.return_value = self.creator
        mocked_post.return_value = self.response(200, {
            'data': {'publish_id': 'p_pub_url~v2.456'},
            'error': {'code': 'ok', 'message': '', 'log_id': 'x'},
        })
        first = self.client.post(self.publish_url, self.form, format='json')
        self.assertEqual(first.data['deliveryStatus'], 'in_progress')

        mocked_post.reset_mock()
        mocked_post.return_value = self.response(200, {
            'data': {
                'status': 'PUBLISH_COMPLETE',
                'publicaly_available_post_id': [],
            },
            'error': {'code': 'ok', 'message': '', 'log_id': 'y'},
        })
        checked = self.client.post(self.status_url, {}, format='json')
        self.assertEqual(checked.status_code, 200)
        self.assertEqual(checked.data['deliveryStatus'], 'succeeded')
        self.assertEqual(SocialDeliveryAttempt.objects.get().status, 'succeeded')

    @patch('storefront.tiktok_product_delivery._photo_url_for', return_value='https://verified.stockflow.test/api/storefront/social/tiktok/product-media/?token=x')
    @patch('storefront.tiktok_product_delivery._creator_info')
    def test_privacy_must_be_selected_from_latest_creator_options(self, creator_info, _photo_url):
        creator_info.return_value = self.creator
        payload = {**self.form, 'privacy': 'PUBLIC_TO_EVERYONE'}
        response = self.client.post(self.publish_url, payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(SocialDeliveryAttempt.objects.exists())

    @patch('storefront.tiktok_product_delivery._photo_url_for', return_value='https://verified.stockflow.test/api/storefront/social/tiktok/product-media/?token=x')
    @patch('storefront.tiktok_product_delivery._creator_info')
    def test_disclosure_and_music_consent_are_required_before_submit(self, creator_info, _photo_url):
        creator_info.return_value = self.creator
        no_consent = {**self.form, 'consent': False}
        response = self.client.post(self.publish_url, no_consent, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(SocialDeliveryAttempt.objects.exists())

        bad_disclosure = {**self.form, 'disclosure': True, 'ownBrand': False}
        response = self.client.post(self.publish_url, bad_disclosure, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(SocialDeliveryAttempt.objects.exists())
