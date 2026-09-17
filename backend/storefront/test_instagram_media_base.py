from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings
from rest_framework.exceptions import ValidationError

from .instagram_delivery import _image_url_for


class InstagramMediaBaseUrlTests(SimpleTestCase):
    @override_settings(
        META_INSTAGRAM_MEDIA_BASE_URL='https://example-tunnel.trycloudflare.com'
    )
    @patch('storefront.instagram_delivery._signed_media_path')
    @patch('storefront.instagram_delivery._product_photo')
    def test_configured_public_base_is_used_for_stockflow_photo(
        self,
        mocked_photo,
        mocked_path,
    ):
        mocked_photo.return_value = SimpleNamespace()
        mocked_path.return_value = (
            '/api/storefront/social/instagram/media/?token=signed-test-token'
        )
        request = Mock()
        request.build_absolute_uri.return_value = (
            'http://localhost:8000/api/storefront/social/instagram/media/'
            '?token=signed-test-token'
        )
        job = SimpleNamespace(
            listing=SimpleNamespace(image_url=''),
            payload={},
        )

        result = _image_url_for(job, request)

        self.assertEqual(
            result,
            'https://example-tunnel.trycloudflare.com'
            '/api/storefront/social/instagram/media/?token=signed-test-token',
        )
        request.build_absolute_uri.assert_not_called()

    @override_settings(META_INSTAGRAM_MEDIA_BASE_URL='')
    @patch('storefront.instagram_delivery._signed_media_path')
    @patch('storefront.instagram_delivery._product_photo')
    def test_without_public_base_local_request_is_rejected(
        self,
        mocked_photo,
        mocked_path,
    ):
        mocked_photo.return_value = SimpleNamespace()
        mocked_path.return_value = (
            '/api/storefront/social/instagram/media/?token=signed-test-token'
        )
        request = Mock()
        request.build_absolute_uri.return_value = (
            'http://localhost:8000/api/storefront/social/instagram/media/'
            '?token=signed-test-token'
        )
        job = SimpleNamespace(
            listing=SimpleNamespace(image_url=''),
            payload={'imageUrl': '/api/product-photos/local-only/'},
        )

        with self.assertRaisesMessage(
            ValidationError,
            'Instagram needs a publicly reachable HTTPS product image',
        ):
            _image_url_for(job, request)
