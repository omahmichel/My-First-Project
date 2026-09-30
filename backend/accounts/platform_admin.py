"""Platform-wide administration. Business roles never grant access here."""
import json
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from datetime import datetime, time
from platform_events.models import PlatformEvent
from platform_events.capture import record_event
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from businesses.models import Business, Branch, BusinessMembership, SubscriptionPayment

User = get_user_model()

class PlatformAdminPermission(BasePermission):
    message = 'Platform administrator access is required.'
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.is_active and u.is_staff and u.is_superuser)

class AdminView(APIView):
    permission_classes = (PlatformAdminPermission,)
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        return response

class Pages(PageNumberPagination):
    page_size = 20


def page(request, rows, convert):
    p = Pages()
    return p.get_paginated_response([convert(x) for x in p.paginate_queryset(rows, request)])


def user_data(u):
    return dict(id=u.pk, name=u.full_name, email=u.email, phone=u.phone,
                active=u.is_active, administrator=u.is_staff or u.is_superuser,
                joinedAt=u.date_joined, lastLogin=u.last_login)


def business_data(b):
    return dict(id=str(b.pk), name=b.name, type=b.get_business_type_display(),
                owner=user_data(b.owner), status=b.status, phone=b.phone, email=b.email,
                location=b.location, joinedAt=b.created_at,
                subscriptionStatus=b.subscription_status,
                trialEndsAt=b.trial_ends_at, subscriptionEndsAt=b.subscription_ends_at,
                subscriptionCurrent=b.has_active_subscription, trialCurrent=b.is_trial_active)


class Overview(AdminView):
    def get(self, request):
        now = timezone.now()
        return Response(dict(users=User.objects.count(), activeUsers=User.objects.filter(is_active=True).count(),
            businesses=Business.objects.count(), activeBusinesses=Business.objects.filter(status='active').count(),
            currentSubscriptions=Business.objects.filter(subscription_status='active', subscription_ends_at__gt=now).count(),
            currentTrials=Business.objects.filter(subscription_status='trial', trial_ends_at__gt=now).count()))


class Users(AdminView):
    def get(self, request):
        rows = User.objects.order_by('-date_joined', '-pk')
        q = request.query_params.get('q', '').strip()[:180]
        if q: rows = rows.filter(Q(full_name__icontains=q) | Q(email__icontains=q) | Q(phone__icontains=q))
        state = request.query_params.get('status')
        if state in ('active', 'inactive'): rows = rows.filter(is_active=state == 'active')
        return page(request, rows, user_data)


class Businesses(AdminView):
    def get(self, request):
        rows = Business.objects.select_related('owner').order_by('-created_at', '-pk')
        q = request.query_params.get('q', '').strip()[:180]
        if q: rows = rows.filter(Q(name__icontains=q) | Q(owner__email__icontains=q) | Q(slug__icontains=q))
        state = request.query_params.get('status')
        if state in ('active', 'inactive'): rows = rows.filter(status=state)
        return page(request, rows, business_data)


class UserDetail(AdminView):
    def get(self, request, pk):
        u = get_object_or_404(User, pk=pk)
        memberships = BusinessMembership.objects.filter(user=u).select_related('business')
        owned = Business.objects.filter(owner=u)
        return Response(dict(**user_data(u), ownedBusinessCount=owned.count(),
            ownedBusinesses=list(owned.values('id', 'name', 'status')[:100]),
            membershipCount=memberships.count(), memberships=[dict(business=m.business.name,
                role=m.get_role_display(), active=m.is_active) for m in memberships[:100]]))


class BusinessDetail(AdminView):
    def get(self, request, pk):
        b = get_object_or_404(Business.objects.select_related('owner'), pk=pk)
        members = b.memberships.select_related('user')
        branches = Branch.objects.filter(business=b)
        return Response(dict(**business_data(b), branchCount=branches.count(),
            branches=list(branches.values('id', 'name', 'is_active')[:100]),
            memberCount=members.count(), members=[dict(name=m.user.full_name, email=m.user.email,
                role=m.get_role_display(), active=m.is_active) for m in members[:100]]))


class Subscriptions(AdminView):
    def get(self, request):
        rows = SubscriptionPayment.objects.select_related('business').order_by('-created_at', '-pk')
        q = request.query_params.get('q', '').strip()[:180]
        if q: rows = rows.filter(Q(business__name__icontains=q) | Q(reference__icontains=q))
        state = request.query_params.get('status')
        if state in SubscriptionPayment.Status.values: rows = rows.filter(status=state)
        return page(request, rows, lambda p: dict(id=str(p.pk), business=p.business.name,
            reference=p.reference, amount=str(p.amount), currency=p.currency, status=p.status,
            durationDays=p.duration_days, createdAt=p.created_at, paidAt=p.paid_at))


class StatusInput(serializers.Serializer):
    active = serializers.BooleanField()
    expectedActive = serializers.BooleanField()
    reason = serializers.CharField(min_length=5, max_length=500)
    def to_internal_value(self, data):
        if set(data) - set(self.fields): raise ValidationError({'detail': 'Unexpected fields supplied.'})
        return super().to_internal_value(data)


class ChangeStatus(AdminView):
    @transaction.atomic
    def post(self, request, kind, pk):
        payload = StatusInput(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        model = User if kind == 'users' else Business
        obj = get_object_or_404(model.objects.select_for_update(), pk=pk)
        if kind == 'users' and (obj.pk == request.user.pk or obj.is_staff or obj.is_superuser):
            raise ValidationError('Administrator accounts cannot be suspended from this dashboard.')
        before = obj.is_active if kind == 'users' else obj.status == 'active'
        if before != data['expectedActive']:
            return Response({'detail': 'This account changed. Refresh and review its current status.'}, status=409)
        if before == data['active']:
            return Response({'changed': False})
        if kind == 'users':
            obj.is_active = data['active']; obj.save(update_fields=['is_active'])
        else:
            obj.status = 'active' if data['active'] else 'inactive'; obj.save(update_fields=['status', 'updated_at'])
        LogEntry.objects.create(user=request.user, content_type=ContentType.objects.get_for_model(obj),
            object_id=str(obj.pk), object_repr=str(obj)[:200], action_flag=CHANGE,
            change_message=json.dumps({'platformAdmin': True, 'targetKind': kind, 'beforeActive': before,
                'afterActive': data['active'], 'reason': data['reason']}))
        record_event(category='administration', action='admin.status_changed', summary='Administrator changed account status', actor_id=str(request.user.pk), object_type=kind, object_id=str(pk), business_id=str(pk) if kind == 'businesses' else '', details={'state':'active' if data['active'] else 'inactive'})
        return Response({'changed': True})


class Activity(AdminView):
    def get(self, request):
        rows = PlatformEvent.objects.order_by('-last_seen_at', '-pk')
        severity = request.query_params.get('status', '')
        category = request.query_params.get('category', '')
        if severity in ('info','warning','error','critical'): rows = rows.filter(severity=severity)
        if category in ('authentication','administration','business','payment','access','validation','system','security'): rows = rows.filter(category=category)
        q=request.query_params.get('q','').strip()[:180]
        if q: rows=rows.filter(Q(summary__icontains=q)|Q(action__icontains=q)|Q(route__icontains=q)|Q(request_id=q)|Q(actor_id=q)|Q(business_id=q))
        start=request.query_params.get('from','')
        end=request.query_params.get('to','')
        for value, lookup in ((start,'last_seen_at__gte'),(end,'last_seen_at__lt')):
            if not value: continue
            try: day=parse_date(value)
            except ValueError: day=None
            if day is None: raise ValidationError('Use a valid YYYY-MM-DD date.')
            if lookup.endswith('__lt'): day += timedelta(days=1)
            boundary=timezone.make_aware(datetime.combine(day,time.min))
            rows=rows.filter(**{lookup:boundary})
        if start and end and start>end: raise ValidationError('Start date must not follow end date.')
        paginator=Pages()
        records=paginator.paginate_queryset(rows,request)
        users={str(u.pk):u.full_name or u.email for u in User.objects.filter(pk__in=[e.actor_id for e in records if e.actor_id.isdigit()])}
        business_ids=[]
        import uuid
        for e in records:
            try: business_ids.append(uuid.UUID(e.business_id))
            except (ValueError,AttributeError): pass
        names={str(b.pk):b.name for b in Business.objects.filter(pk__in=business_ids)}
        return paginator.get_paginated_response([dict(id=e.pk,at=e.occurred_at,lastSeenAt=e.last_seen_at,
            category=e.category,severity=e.severity,action=e.action,summary=e.summary,
            actor=users.get(e.actor_id,'Account #'+e.actor_id if e.actor_id else 'Anonymous / system'),
            business=names.get(e.business_id,e.business_id or 'Platform'),route=e.route,method=e.method,
            httpStatus=e.http_status,requestId=e.request_id,source=e.source,peerIp=e.peer_ip,
            occurrences=e.occurrences,objectType=e.object_type,objectId=e.object_id,details=e.details) for e in records])


class Notifications(AdminView):
    """A bounded status snapshot, not an unread-message or payment-settlement feed."""
    def get(self, request):
        now = timezone.now()
        soon = now + timedelta(days=7)
        businesses = Business.objects.filter(status='active')
        current = businesses.filter(subscription_status='active', subscription_ends_at__gt=now).order_by('subscription_ends_at', 'pk')
        trials = businesses.filter(subscription_status='trial', trial_ends_at__gt=now, trial_ends_at__lte=soon).order_by('trial_ends_at', 'pk')
        expired = businesses.filter(Q(subscription_status='expired') | Q(subscription_status='active', subscription_ends_at__lte=now) | Q(subscription_status='trial', trial_ends_at__lte=now)).order_by('-updated_at', 'pk')
        pending = SubscriptionPayment.objects.filter(status='pending').select_related('business').order_by('-created_at', 'pk')
        def business_item(b, message, at):
            return dict(id=str(b.pk), title=b.name, message=message, at=at, tab='businesses', query=b.name)
        groups = [
            dict(key='current', title='Current subscriptions', total=current.count(), items=[business_item(b, 'Subscription ends within 7 days' if b.subscription_ends_at <= soon else 'Active subscription', b.subscription_ends_at) for b in current[:5]]),
            dict(key='trials', title='Trials ending within 7 days', total=trials.count(), items=[business_item(b, 'Trial ends', b.trial_ends_at) for b in trials[:5]]),
            dict(key='expired', title='Expired access', total=expired.count(), items=[business_item(b, 'Subscription or trial expired', b.trial_ends_at if b.subscription_status == 'trial' else b.subscription_ends_at) for b in expired[:5]]),
            dict(key='pending', title='Pending subscription payments', total=pending.count(), items=[dict(id=str(p.pk), title=p.business.name, message='Awaiting payment confirmation', at=p.created_at, tab='subscriptions', query=p.reference) for p in pending[:5]]),
        ]
        alerts=PlatformEvent.objects.filter(severity__in=['warning','error','critical'],last_seen_at__gte=now-timedelta(hours=24)).order_by('-last_seen_at','-pk')
        groups.insert(0,dict(key='platform-alerts',title='System & security alerts · last 24h',total=alerts.count(),items=[dict(id=str(e.pk),title=e.summary,message=e.severity.upper()+' · '+e.category+(f' · {e.occurrences} occurrences' if e.occurrences>1 else ''),at=e.last_seen_at,tab='activity',query=e.request_id or e.action) for e in alerts[:5]]))
        return Response(dict(generatedAt=now, groups=groups))
