import uuid
from django.conf import settings
from django.db import models
from .photo_storage import product_photo_storage


class ProductPhoto(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.OneToOneField('inventory.Product', on_delete=models.CASCADE, related_name='uploaded_photo')
    image = models.FileField(storage=product_photo_storage, upload_to='product-photos/', max_length=255)
    version = models.UUIDField(default=uuid.uuid4, editable=False)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
