"""Owner preferences and pending social publication records.

Delivery adapters and OAuth connections are deliberately not activated here.
"""
import uuid
from django.core.exceptions import ValidationError
from django.db import models


class SocialChannel(models.Model):
    class Platform(models.TextChoices):
        FACEBOOK = 'facebook', 'Facebook'
        INSTAGRAM = 'instagram', 'Instagram'
        TIKTOK = 'tiktok', 'TikTok'
        SNAPCHAT = 'snapchat', 'Snapchat'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    storefront = models.ForeignKey('storefront.Storefront', on_delete=models.CASCADE, related_name='social_channels')
    platform = models.CharField(max_length=20, choices=Platform.choices)
    auto_publish = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=('storefront', 'platform'), name='sf_social_channel_unique')]
        ordering = ('platform',)


class SocialPublishingJob(models.Model):
    class Status(models.TextChoices):
        PENDING_CONNECTION = 'pending_connection', 'Pending connection'
        CANCELLED = 'cancelled', 'Cancelled'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel = models.ForeignKey(SocialChannel, on_delete=models.CASCADE, related_name='jobs')
    listing = models.ForeignKey('storefront.StorefrontListing', on_delete=models.CASCADE, related_name='social_jobs')
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING_CONNECTION)
    payload = models.JSONField(default=dict)
    fingerprint = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # One current publication intent per listing/channel, not delivery history.
        constraints = [models.UniqueConstraint(fields=('channel', 'listing'), name='sf_social_job_unique')]
        ordering = ('-updated_at', '-id')
        indexes = [models.Index(fields=('channel', 'status'), name='sf_social_job_status')]

    def clean(self):
        if self.channel_id and self.listing_id and self.channel.storefront_id != self.listing.storefront_id:
            raise ValidationError('Social channel and listing must belong to the same shop.')

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)
