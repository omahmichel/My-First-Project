from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_login_failed
from django.db.models import Q
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from businesses.models import Business
from inventory.models import BranchInventory, BranchStockMovement, StockMovement
from sales.models import Sale
from platform_events.models import PlatformEvent
from .models import LoginFailure
from .services import compact, queue_alert, safe_capture, security_alert, active_preference


@receiver(post_save, sender=BranchStockMovement, dispatch_uid='owner_sms_branch_stock')
@safe_capture
def branch_stock(sender, instance, created, raw=False, **kwargs):
    if not created or raw:
        return
    m = instance
    business, branch = compact(m.business.name, 12), compact(m.branch.name, 12)
    name, actor = compact(m.product_name, 18), compact(m.created_by_name, 12)
    stamp = m.created_at.strftime('%d/%m %H:%M') + ' UTC'
    kind = 'restock' if m.movement_type == 'stock_in' else 'adjustment' if m.movement_type in ('adjustment', 'damage', 'return') else None
    if kind:
        message = (f'StockFlow {business}/{branch}: {"Restock" if kind == "restock" else "Adjustment"} {name} '
                   f'{m.previous_stock}->{m.new_stock} ({m.quantity:+d}). By {actor}. {stamp}')
        if kind == 'adjustment':
            message += f' Reason: {compact(m.reason, 18)}'
        queue_alert(business_id=m.business_id, event_type=kind, source_id=m.pk, message=message)
    threshold = BranchInventory.objects.filter(branch_id=m.branch_id, product_id=m.product_id).values_list('low_stock_level', flat=True).first()
    # Physical stock crossing only: pending-payment reservations aren't completed sales.
    if threshold is not None and m.previous_stock > threshold >= m.new_stock:
        queue_alert(business_id=m.business_id, event_type='low_stock', source_id=m.pk,
            message=f'StockFlow {business}/{branch}: Low stock - {name}: {m.new_stock} {compact(m.unit, 12)} left (limit {threshold}). Plan a restock. {stamp}')


@receiver(post_save, sender=StockMovement, dispatch_uid='owner_sms_legacy_stock')
@safe_capture
def legacy_stock(sender, instance, created, raw=False, **kwargs):
    # Branch movements cover modern routes; this covers older branchless stock operations.
    if not created or raw or instance.branch_id:
        return
    m = instance
    kind = 'restock' if m.movement_type == 'stock_in' else 'adjustment' if m.movement_type in ('adjustment', 'damage', 'return') else None
    if kind:
        queue_alert(business_id=m.business_id, event_type=kind, source_id=m.pk,
            message=f'StockFlow {compact(m.business.name, 20)}: {kind} {compact(m.product_name, 30)} {m.previous_stock}->{m.new_stock}. By {compact(m.created_by_name, 20)}. Reason: {compact(m.reason, 18)}')
    if m.previous_stock > m.product.low_stock_level >= m.new_stock:
        queue_alert(business_id=m.business_id, event_type='low_stock', source_id=m.pk,
            message=f'StockFlow {compact(m.business.name)}: Low stock - {compact(m.product_name)}: {m.new_stock} left. Plan a restock.')


@receiver(pre_save, sender=Sale, dispatch_uid='owner_sms_sale_transition')
@safe_capture
def sale_transition(sender, instance, raw=False, update_fields=None, **kwargs):
    instance._owner_sms_new_completion = False
    if raw or not instance.completed_at or instance.status not in ('completed', 'partially_paid'):
        return
    if update_fields is not None and 'completed_at' not in update_fields:
        return
    previous = None if instance._state.adding else Sale.objects.filter(pk=instance.pk).values('completed_at').first()
    instance._owner_sms_new_completion = previous is None or previous['completed_at'] is None


@receiver(post_save, sender=Sale, dispatch_uid='owner_sms_sale')
@safe_capture
def sale_saved(sender, instance, raw=False, **kwargs):
    s = instance
    if raw or not getattr(s, '_owner_sms_new_completion', False):
        return
    queue_alert(business_id=s.business_id, event_type='sale', source_id=s.pk,
        message=f'StockFlow {compact(s.business.name, 20)}/{compact(s.branch.name if s.branch_id else "Main", 18)}: Sale {compact(s.sale_number, 22)} GHS {s.total:.2f}, paid {s.amount_paid:.2f}. By {compact(s.cashier_name, 20)}. {s.completed_at:%d/%m %H:%M} UTC')


@receiver(post_save, sender=PlatformEvent, dispatch_uid='owner_sms_denied')
@safe_capture
def denied(sender, instance, created, raw=False, **kwargs):
    e = instance
    if raw or not created or e.action != 'request.denied' or e.http_status != 403:
        return
    # Never assign global/anonymous probes to unrelated business owners.
    if e.business_id and Business.objects.filter(pk=e.business_id).exists():
        security_alert(e.business_id)


@receiver(user_login_failed, dispatch_uid='owner_sms_login_failed')
@safe_capture
def login_failed(sender, credentials, **kwargs):
    email = str(credentials.get('email') or credentials.get('username') or '').strip()
    user = get_user_model().objects.filter(email__iexact=email, is_active=True).first()
    if not user:
        return
    businesses = Business.objects.filter(Q(owner=user) | Q(memberships__user=user, memberships__is_active=True)).distinct()
    for business in businesses:
        if not active_preference(business.pk, 'security'):
            continue
        LoginFailure.objects.create(business=business)
        if LoginFailure.objects.filter(business=business, created_at__gte=timezone.now()-timedelta(minutes=15)).count() >= 5:
            security_alert(business.pk, login=True)
