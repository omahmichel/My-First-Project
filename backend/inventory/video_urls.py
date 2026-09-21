from urllib.parse import urlencode

from django.core import signing
from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse


VIDEO_PREVIEW_SALT = 'stockflow-product-video-preview-v1'


def product_video_url(product, request=None, *, private=False):
    try:
        video = product.uploaded_video
    except ObjectDoesNotExist:
        return ''

    path = reverse(
        'inventory:product-video-content',
        kwargs={'video_id': video.id, 'version': video.version},
    )
    if private:
        token = signing.dumps(
            {'video': str(video.id), 'version': str(video.version)},
            salt=VIDEO_PREVIEW_SALT,
        )
        path += '?' + urlencode({'preview': token})
    return request.build_absolute_uri(path) if request is not None else path
