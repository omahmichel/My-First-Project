import uuid
from django.conf import settings
from django.db import models


class OwnerSmsPreference(models.Model):
    business = models.OneToOneField('businesses.Business', on_delete=models.CASCADE)
    # Verification and consent belong to this owner, not any future business owner.
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    enabled = models.BooleanField(default=False)
    phone = models.CharField(max_length=10, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    event_types = models.JSONField(default=list)
    pending_phone = models.CharField(max_length=10, blank=True)
    challenge = models.UUIDField(null=True, blank=True)
    code_hash = models.CharField(max_length=128, blank=True)
    code_expires_at = models.DateTimeField(null=True, blank=True)
    code_attempts = models.PositiveSmallIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)


class OwnerSms(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Queued'
        SENDING = 'sending', 'Submitting'
        SENT = 'sent', 'Accepted by SMS provider'
        UNKNOWN = 'unknown', 'Delivery unconfirmed'
        CANCELLED = 'cancelled', 'Cancelled'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey('businesses.Business', on_delete=models.CASCADE)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    recipient = models.CharField(max_length=10)
    event_type = models.CharField(max_length=30)
    source_id = models.CharField(max_length=64, blank=True)
    dedupe_key = models.CharField(max_length=200, unique=True)
    message = models.CharField(max_length=160)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    provider_reference = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    attempted_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ['created_at', 'id']
        indexes = [models.Index(fields=['business', 'created_at'], name='owner_sms_business_time')]


class LoginFailure(models.Model):
    business = models.ForeignKey('businesses.Business', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
