"""Durable owner SMS outbox. No network calls from transaction signals."""
import logging
import string
import unicodedata
from datetime import timedelta
from functools import wraps
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from integrations.messaging.sms import MNotifySmsProvider
from .models import OwnerSms, OwnerSmsPreference

EVENT_TYPES = ('restock', 'adjustment', 'low_stock', 'sale', 'security')
logger = logging.getLogger('owner_alerts')


def safe_capture(fn):
    @wraps(fn)
    def run(*args, **kwargs):
        try:
            # Savepoint isolates a notification fault from the business transaction.
            with transaction.atomic():
                return fn(*args, **kwargs)
        except Exception:
            logger.error('Owner SMS event capture failed; business operation was preserved.')
    return run


def compact(value, limit=30):
    # ASCII messages avoid surprising Unicode SMS segmentation/charges.
    allowed = string.ascii_letters + string.digits + " !\"#%&'()*+,-./:;<=>?_$@"
    raw = ' '.join(unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode().split())
    return ''.join(c if c in allowed else '?' for c in raw)[:limit]


def active_preference(business_id, event_type):
    p = OwnerSmsPreference.objects.select_related('business').filter(
        business_id=business_id, enabled=True, verified_at__isnull=False,
    ).first()
    if not p or p.owner_id != p.business.owner_id or not p.phone or event_type not in p.event_types:
        return None
    return p


def queue_alert(*, business_id, event_type, source_id, message, dedupe=None):
    p = active_preference(business_id, event_type)
    if not p:
        return None
    # A recipient change does not replay historical events.
    item, _ = OwnerSms.objects.get_or_create(
        dedupe_key=dedupe or f'{business_id}:{event_type}:{source_id}',
        defaults=dict(business_id=business_id, owner_id=p.owner_id,
                      recipient=p.phone, event_type=event_type, source_id=str(source_id),
                      message=compact(message, 160)),
    )
    return item


def security_alert(business_id, *, login=False):
    now = timezone.now()
    text = ('Repeated failed sign-ins to an account linked to your business.' if login else
            'An access request to your business was blocked.')
    p = active_preference(business_id, 'security')
    if p:
        # Serialize per-business security notifications, including across worker processes.
        OwnerSmsPreference.objects.select_for_update().get(pk=p.pk)
        if OwnerSms.objects.filter(business_id=business_id, event_type='security', created_at__gte=now-timedelta(hours=1)).exists():
            return
        queue_alert(business_id=business_id, event_type='security', source_id='',
            dedupe=f'{business_id}:security:{now:%Y%m%d%H}',
            message=f'StockFlow {compact(p.business.name, 25)}: {text} Review account access if unexpected. {now:%d/%m %H:%M} UTC')


def provider_ready():
    return all(str(getattr(settings, key, '') or '').strip() for key in
               ('MNOTIFY_API_KEY', 'MNOTIFY_SENDER_ID', 'MNOTIFY_API_URL'))


def process_pending(limit=100):
    now = timezone.now()
    # A crash after submission has an ambiguous outcome. Never blindly resend it.
    OwnerSms.objects.filter(status='sending', attempted_at__lt=now-timedelta(minutes=10)).update(status='unknown', message='')
    OwnerSms.objects.filter(status='pending', created_at__lt=now-timedelta(hours=24)).update(status='cancelled', message='')
    if not provider_ready():
        return {'accepted': 0, 'unconfirmed': 0, 'cancelled': 0, 'configured': False}
    counts = {'accepted': 0, 'unconfirmed': 0, 'cancelled': 0, 'configured': True}
    ids = list(OwnerSms.objects.filter(status='pending').values_list('pk', flat=True)[:limit])
    for pk in ids:
        with transaction.atomic():
            # Conditional claim protects against overlapping workers on PostgreSQL and SQLite.
            if not OwnerSms.objects.filter(pk=pk, status='pending').update(status='sending', attempted_at=timezone.now()):
                continue
            item = OwnerSms.objects.select_related('business').get(pk=pk)
            p = OwnerSmsPreference.objects.filter(business_id=item.business_id).first()
            valid = bool(p and p.owner_id == item.owner_id == item.business.owner_id)
            if item.event_type == 'verification':
                valid = valid and str(p.challenge) == item.source_id and p.pending_phone == item.recipient and bool(p.code_expires_at and p.code_expires_at > timezone.now())
            else:
                valid = valid and p.enabled and bool(p.verified_at) and p.phone == item.recipient and item.event_type in p.event_types
            if not valid:
                OwnerSms.objects.filter(pk=pk).update(status='cancelled', message='')
                counts['cancelled'] += 1
                continue
        try:
            result = MNotifySmsProvider().send(recipient=item.recipient, message=item.message)
        except Exception:
            # Includes timeouts where the provider may have accepted the SMS.
            OwnerSms.objects.filter(pk=pk).update(status='unknown', message='' if item.event_type == 'verification' else item.message)
            logger.warning('Owner SMS submission unconfirmed; automatic retry suppressed.')
            counts['unconfirmed'] += 1
        else:
            OwnerSms.objects.filter(pk=pk).update(status='sent', sent_at=timezone.now(),
                provider_reference=str(result.get('provider_reference', ''))[:120],
                message='' if item.event_type == 'verification' else item.message)
            counts['accepted'] += 1
    return counts
