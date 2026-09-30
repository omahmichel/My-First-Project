"""Privileged grants and bug triage; business membership never grants access."""
from django.contrib.auth import get_user_model
from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.views.decorators.debug import sensitive_post_parameters
from django.utils.decorators import method_decorator
from rest_framework import serializers
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from platform_events.models import BugReport
from platform_events.capture import record_event
from .platform_admin import AdminView, page, user_data

User = get_user_model()
class GrantThrottle(UserRateThrottle):
    scope='platform_admin_grant'
    rate='5/min'

class GrantInput(serializers.Serializer):
    userId=serializers.IntegerField(min_value=1)
    confirmEmail=serializers.EmailField()
    password=serializers.CharField(write_only=True, trim_whitespace=False, max_length=1024)

@method_decorator(sensitive_post_parameters('password'), name='dispatch')
class Administrators(AdminView):
    def get(self, request):
        q=request.query_params.get('q','').strip()[:180]
        rows=User.objects.filter(is_active=True).order_by('email','pk')
        if q: rows=rows.filter(Q(email__icontains=q)|Q(full_name__icontains=q))
        else: rows=rows.filter(is_staff=True,is_superuser=True)
        return page(request,rows,lambda u:dict(user_data(u),platformAdmin=u.is_staff and u.is_superuser))
    def get_throttles(self):
        return [GrantThrottle()] if self.request.method=='POST' else []
    @transaction.atomic
    def post(self, request):
        data=GrantInput(data=request.data);data.is_valid(raise_exception=True);data=data.validated_data
        actor=User.objects.select_for_update().get(pk=request.user.pk)
        if not (actor.is_active and actor.is_staff and actor.is_superuser): raise PermissionDenied()
        if not actor.check_password(data['password']):
            record_event(category='security',action='admin.grant_denied',summary='Administrator grant password confirmation failed',severity='warning',actor_id=str(actor.pk))
            # Return directly so the rejection audit is not rolled back.
            return Response({'detail':'Your administrator password is incorrect.'},status=400)
        target=get_object_or_404(User.objects.select_for_update(),pk=data['userId'],is_active=True)
        if target.email.casefold()!=data['confirmEmail'].casefold(): raise ValidationError('The confirmation email does not match the selected account.')
        if target.is_staff and target.is_superuser: return Response({'detail':'This account is already a platform administrator.','changed':False})
        target.is_staff=True;target.is_superuser=True;target.save(update_fields=['is_staff','is_superuser'])
        LogEntry.objects.create(user_id=actor.pk,content_type=ContentType.objects.get_for_model(target),object_id=str(target.pk),object_repr='Account #'+str(target.pk),action_flag=CHANGE,change_message='Platform administrator access granted')
        record_event(category='administration',action='admin.access_granted',summary='Platform administrator access granted',actor_id=str(actor.pk),object_type='accounts.user',object_id=str(target.pk))
        return Response({'detail':'Platform administrator access granted. The account should sign out and sign in again.','changed':True})

class BugInput(serializers.Serializer):
    status=serializers.ChoiceField(choices=BugReport.Status.values)
    expectedStatus=serializers.ChoiceField(choices=BugReport.Status.values)

def bug_data(b):
    e=b.event
    return dict(id=b.pk,title=b.title,description=b.description,source=b.source,status=b.status,
        reporterId=b.reporter_id,businessId=b.business_id,createdAt=b.created_at,updatedAt=b.updated_at,
        event=dict(action=e.action,route=e.route,requestId=e.request_id,severity=e.severity,occurrences=e.occurrences) if e else None)

class Bugs(AdminView):
    def get(self,request):
        rows=BugReport.objects.select_related('event').all()
        status=request.query_params.get('status','')
        if status in BugReport.Status.values: rows=rows.filter(status=status)
        q=request.query_params.get('q','').strip()[:180]
        if q: rows=rows.filter(Q(title__icontains=q)|Q(business_id=q)|Q(reporter_id=q)|Q(event__request_id=q))
        return page(request,rows,bug_data)

class BugStatus(AdminView):
    @transaction.atomic
    def post(self,request,pk):
        data=BugInput(data=request.data);data.is_valid(raise_exception=True);data=data.validated_data
        b=get_object_or_404(BugReport.objects.select_for_update(),pk=pk)
        if b.status!=data['expectedStatus']: return Response({'detail':'This bug changed. Reload the list before trying again.'},status=409)
        if b.status!=data['status']:
            b.status=data['status'];b.save(update_fields=['status','updated_at'])
            LogEntry.objects.create(user_id=request.user.pk,content_type=ContentType.objects.get_for_model(b),object_id=str(b.pk),object_repr='Bug #'+str(b.pk),action_flag=CHANGE,change_message='Bug status changed to '+b.status)
            record_event(category='administration',action='bug.status_changed',summary='Administrator changed bug status',actor_id=str(request.user.pk),object_type='platform_events.bugreport',object_id=str(b.pk),details={'state':b.status})
        return Response(bug_data(b))


class AdminRegistrationInput(serializers.Serializer):
    fullName=serializers.CharField(max_length=150)
    email=serializers.EmailField(max_length=254)
    phone=serializers.CharField(max_length=30,required=False,allow_blank=True,default='')
    newPassword=serializers.CharField(write_only=True,trim_whitespace=False,max_length=1024)
    confirmPassword=serializers.CharField(write_only=True,trim_whitespace=False,max_length=1024)
    adminPassword=serializers.CharField(write_only=True,trim_whitespace=False,max_length=1024)
    confirmAccess=serializers.BooleanField()
    def validate(self,data):
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError
        if not data['confirmAccess']: raise ValidationError('Confirm full platform administrator access.')
        if data['newPassword']!=data['confirmPassword']: raise ValidationError('The new passwords do not match.')
        data['email']=data['email'].strip().lower()
        if User.objects.filter(email__iexact=data['email']).exists():
            raise ValidationError('This email already belongs to an account. Use the existing-account section below to grant access.')
        candidate=User(email=data['email'],full_name=data['fullName'],phone=data['phone'])
        try: validate_password(data['newPassword'],candidate)
        except DjangoValidationError as exc: raise ValidationError({'newPassword':exc.messages})
        return data

@method_decorator(sensitive_post_parameters('newPassword','confirmPassword','adminPassword'),name='dispatch')
class RegisterAdministrator(AdminView):
    throttle_classes=(GrantThrottle,)
    @transaction.atomic
    def post(self,request):
        from django.db import IntegrityError
        # Recheck the authorising account under a row lock.
        actor=User.objects.select_for_update().get(pk=request.user.pk)
        if not (actor.is_active and actor.is_staff and actor.is_superuser): raise PermissionDenied()
        password=request.data.get('adminPassword','')
        if not isinstance(password,str) or len(password)>1024 or not actor.check_password(password):
            record_event(category='security',action='admin.registration_denied',summary='Administrator registration password confirmation failed',severity='warning',actor_id=str(actor.pk))
            return Response({'detail':'Your administrator password is incorrect.'},status=400)
        serializer=AdminRegistrationInput(data=request.data);serializer.is_valid(raise_exception=True)
        data=serializer.validated_data
        try:
            with transaction.atomic():
                target=User.objects.create_superuser(email=data['email'],password=data['newPassword'],full_name=data['fullName'],phone=data['phone'],is_active=True)
        except IntegrityError:
            raise ValidationError('This email is already registered. No administrator was created.')
        LogEntry.objects.create(user_id=actor.pk,content_type=ContentType.objects.get_for_model(target),object_id=str(target.pk),object_repr='Account #'+str(target.pk),action_flag=CHANGE,change_message='New platform administrator registered')
        record_event(category='administration',action='admin.account_created',summary='New platform administrator registered',actor_id=str(actor.pk),object_type='accounts.user',object_id=str(target.pk))
        return Response({'detail':'Administrator created. They can sign in with this email and password and complete the usual login verification. No business setup is required.','user':user_data(target)},status=201)
