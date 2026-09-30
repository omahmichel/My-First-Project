"""No request bodies, query strings, tokens, exception messages or arbitrary metadata."""
from contextvars import ContextVar
from functools import wraps
from hashlib import sha256
import ipaddress
import logging
import uuid
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from .models import PlatformEvent

current_request = ContextVar('platform_event_request', default=None)
current_job = ContextVar('platform_event_job', default='')
busy = ContextVar('platform_event_busy', default=False)
SAFE_DETAILS = {'state', 'fields', 'check_ids', 'issue_count', 'exception_type', 'job', 'legacy_id'}

def context_fields():
    request = current_request.get()
    if request is None:
        return {'source': 'job' if current_job.get() else 'application'}
    user = getattr(request, 'user', None)
    actor = str(user.pk) if user is not None and getattr(user, 'is_authenticated', False) else ''
    match = getattr(request, 'resolver_match', None)
    route = str(getattr(match, 'route', '') or '')[:240]
    # Resolver templates contain placeholders; never use the raw request path.
    business = (getattr(match, 'kwargs', {}) or {}).get('business_id', '')
    try: business = str(uuid.UUID(str(business))) if business else ''
    except ValueError: business = ''
    try: peer = str(ipaddress.ip_address(request.META.get('REMOTE_ADDR', '')))
    except ValueError: peer = None
    return dict(actor_id=actor, business_id=business, route=route, method=request.method[:12],
                request_id=getattr(request, '_platform_event_id', ''), peer_ip=peer, source='request')

def record_event(*, category, action, summary, severity='info', aggregate=False, **fields):
    if busy.get(): return
    token = busy.set(True)
    try:
        values = context_fields()
        values.update(fields)
        details = values.pop('details', {})
        values['details'] = {k:v for k,v in details.items() if k in SAFE_DETAILS}
        values.update(category=category, action=action, summary=summary[:240], severity=severity)
        now = timezone.now()
        values.update(occurred_at=now, last_seen_at=now)
        # A savepoint prevents a logging failure from poisoning a business transaction.
        with transaction.atomic():
            if aggregate:
                identity = '|'.join(str(values.get(k, '')) for k in ('category','action','actor_id','business_id','peer_ip','route','http_status','source'))
                identity += '|' + now.strftime('%Y%m%d%H%M')
                key = sha256(identity.encode()).hexdigest()
                event, created = PlatformEvent.objects.get_or_create(dedupe_key=key, defaults=values)
                if not created:
                    PlatformEvent.objects.filter(pk=event.pk).update(occurrences=F('occurrences')+1,last_seen_at=now)
            else:
                PlatformEvent.objects.create(**values)
    except Exception:
        # Constant fallback is intentional: database diagnostics can contain secrets.
        logging.getLogger('platform_events.fallback').warning('Platform activity capture unavailable; event was not persisted.')
    finally:
        busy.reset(token)

def audited_job(name):
    def decorate(fn):
        @wraps(fn)
        def run(*args, **kwargs):
            token = current_job.set(name)
            try:
                record_event(category='system',action='job.started',summary='Background job started',details={'job':name})
                result = fn(*args, **kwargs)
                record_event(category='system',action='job.completed',summary='Background job completed',details={'job':name})
                return result
            except Exception as exc:
                record_event(category='system',action='job.failed',summary='Background job failed',severity='error',details={'job':name,'exception_type':type(exc).__name__})
                raise
            finally: current_job.reset(token)
        return run
    return decorate

class SafeEventHandler(logging.Handler):
    def emit(self, record):
        if busy.get() or record.name.startswith('platform_events'): return
        security = record.name.startswith('django.security')
        if not security and record.levelno < logging.ERROR: return
        record_event(category='security' if security else 'system',
            action='security.rejected' if security else 'application.error',
            summary='Django security check rejected a request' if security else 'Application reported an error',
            severity='critical' if record.levelno >= logging.CRITICAL else 'warning' if security else 'error',
            aggregate=True, details={'exception_type':record.exc_info[0].__name__ if record.exc_info and record.exc_info[0] else ''})

def install_log_handlers():
    for name in ('django.security','accounts','businesses','customers','inventory','sales','storefront','integrations','intelligence'):
        logger = logging.getLogger(name)
        if not any(isinstance(h,SafeEventHandler) for h in logger.handlers):
            handler=SafeEventHandler();handler.setLevel(logging.WARNING);logger.addHandler(handler)
