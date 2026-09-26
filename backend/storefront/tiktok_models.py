"""Manual TikTok publication audit records. No automatic dispatch."""
import uuid
from django.db import models

class TikTokPublication(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey('businesses.Business', on_delete=models.CASCADE)
    video = models.ForeignKey('inventory.ProductVideo', on_delete=models.SET_NULL, null=True)
    video_version = models.UUIDField()
    account_id = models.CharField(max_length=180)
    account_name = models.CharField(max_length=180)
    status = models.CharField(max_length=24, default='draft')
    publish_id = models.CharField(max_length=180, blank=True)
    message = models.CharField(max_length=500, blank=True)
    post_info = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
