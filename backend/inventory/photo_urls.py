from urllib.parse import urlencode
from django.core import signing
from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse

PHOTO_SALT = 'stockflow-product-photo-preview-v1'


def product_photo_url(product, request=None, *, private=False):
    try:
        photo = product.uploaded_photo
    except ObjectDoesNotExist:
        return ''
    path = reverse('inventory:product-photo-content', kwargs={'photo_id': photo.id, 'version': photo.version})
    if private:
        token = signing.dumps({'photo': str(photo.id), 'version': str(photo.version)}, salt=PHOTO_SALT)
        path += '?' + urlencode({'preview': token})
    return request.build_absolute_uri(path) if request is not None else path
