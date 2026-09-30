from django.db import models
from django.utils import timezone

class PlatformEvent(models.Model):
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    last_seen_at = models.DateTimeField(default=timezone.now)
    category = models.CharField(max_length=32, db_index=True)
    severity = models.CharField(max_length=12, default='info', db_index=True)
    action = models.CharField(max_length=100)
    summary = models.CharField(max_length=240)
    actor_id = models.CharField(max_length=64, blank=True)
    business_id = models.CharField(max_length=64, blank=True, db_index=True)
    object_type = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=64, blank=True)
    route = models.CharField(max_length=240, blank=True)
    method = models.CharField(max_length=12, blank=True)
    http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    request_id = models.CharField(max_length=36, blank=True, db_index=True)
    source = models.CharField(max_length=32, default='application')
    peer_ip = models.GenericIPAddressField(null=True, blank=True)
    occurrences = models.PositiveIntegerField(default=1)
    # Only explicitly safe, enumerated diagnostics; never request or model payloads.
    details = models.JSONField(default=dict)
    dedupe_key = models.CharField(max_length=64, unique=True, null=True, blank=True)
    class Meta:
        ordering = ['-occurred_at', '-pk']
        indexes = [models.Index(fields=['severity', '-occurred_at'], name='pe_severity_time')]

class BugReport(models.Model):
    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        INVESTIGATING = 'investigating', 'Investigating'
        RESOLVED = 'resolved', 'Resolved'
    event = models.OneToOneField(PlatformEvent, null=True, blank=True, on_delete=models.SET_NULL)
    source = models.CharField(max_length=20, default='application')
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    reporter_id = models.CharField(max_length=64, blank=True)
    business_id = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ['-created_at', '-pk']
