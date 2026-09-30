from django.db import transaction
from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from .capture import context_fields, record_event

APPS={'accounts','businesses','inventory','customers','sales','storefront','integrations','intelligence'}
EXCLUDE={'pendingregistration','pendingloginchallenge','passwordresetchallenge','documentsequence','intelligencesnapshot','notificationread','socialauthorizationrequest'}

def capture_model(sender, instance, verb, using='default', **kwargs):
    if sender._meta.app_label not in APPS or sender._meta.model_name in EXCLUDE: return
    if kwargs.get('raw'): return
    context=context_fields()
    business=instance.__dict__.get('business_id')
    if sender._meta.label_lower=='businesses.business': business=instance.pk
    if business: context['business_id']=str(business)
    state=''
    try:
        field=sender._meta.get_field('status')
        candidate=instance.__dict__.get('status')
        if candidate in dict(field.flatchoices): state=str(candidate)
    except Exception: pass
    # State-only diagnostics: never serialize credential fields or free-text payloads.
    severity='error' if state in ('failed','error') else 'warning' if state in ('blocked','retry') else 'info'
    details={'state':state} if state else {}
    if kwargs.get('update_fields'):
        details['fields']=sorted(str(f) for f in kwargs['update_fields'])[:30]
    category='authentication' if sender._meta.app_label=='accounts' else 'business'
    if sender._meta.model_name in ('subscriptionpayment','payment','merchantpayout','restockpayment'): category='payment'
    values=dict(category=category,action=sender._meta.label_lower+'.'+verb,
        summary=f'{sender._meta.verbose_name.capitalize()} {verb}',severity=severity,
        object_type=sender._meta.label_lower,object_id=str(instance.pk),details=details,**context)
    transaction.on_commit(lambda:record_event(**values),using=using)

@receiver(post_save,dispatch_uid='platform_event_saved')
def saved(sender,instance,created,**kwargs): capture_model(sender,instance,'created' if created else 'updated',**kwargs)

@receiver(post_delete,dispatch_uid='platform_event_deleted')
def deleted(sender,instance,**kwargs): capture_model(sender,instance,'deleted',**kwargs)

@receiver(m2m_changed,dispatch_uid='platform_event_m2m')
def related(sender,instance,action,using,**kwargs):
    if action in ('post_add','post_remove','post_clear'):
        capture_model(type(instance),instance,'relationships_changed',using=using)

@receiver(post_save, dispatch_uid='platform_event_bug')
def capture_bug(sender, instance, created, raw=False, **kwargs):
    from .models import PlatformEvent, BugReport
    if sender is not PlatformEvent or not created or raw: return
    if instance.category == 'system' and instance.severity in ('error', 'critical'):
        BugReport.objects.get_or_create(event=instance, defaults={
            'title': instance.summary, 'source': 'application',
            'reporter_id': instance.actor_id, 'business_id': instance.business_id,
        })
