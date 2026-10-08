import secrets
import uuid
from datetime import timedelta
from django.contrib.auth.hashers import make_password, check_password
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from businesses.models import Business
from integrations.messaging.service import normalize_ghana_phone
from .models import OwnerSms, OwnerSmsPreference
from .services import EVENT_TYPES, provider_ready


class PreferencesInput(serializers.Serializer):
    enabled = serializers.BooleanField(required=True)
    eventTypes = serializers.ListField(child=serializers.ChoiceField(choices=EVENT_TYPES), allow_empty=True)


class PhoneInput(serializers.Serializer):
    phone = serializers.CharField(max_length=30)
    def validate_phone(self, value):
        try:
            return normalize_ghana_phone(value)
        except ValueError:
            raise serializers.ValidationError('Enter a valid Ghana phone number.')


class CodeInput(serializers.Serializer):
    code = serializers.RegexField(r'^\d{6}$')


def preference_for(request, business_id):
    # Actual business owner only. Managers and staff cannot redirect owner alerts.
    business = get_object_or_404(Business.objects.select_for_update(), pk=business_id, owner=request.user)
    p, _ = OwnerSmsPreference.objects.get_or_create(business=business, defaults={'owner': request.user, 'event_types': list(EVENT_TYPES)})
    if p.owner_id != business.owner_id:
        p.owner = request.user
        p.enabled = False
        p.phone = p.pending_phone = p.code_hash = ''
        p.verified_at = p.challenge = p.code_expires_at = None
        p.save()
    return p


def payload(p):
    return {'enabled': p.enabled, 'phone': p.phone, 'verified': bool(p.verified_at),
            'pendingPhone': p.pending_phone, 'eventTypes': p.event_types,
            'smsAvailable': provider_ready()}


class OwnerSmsSettings(APIView):
    permission_classes = [IsAuthenticated]
    @transaction.atomic
    def get(self, request, business_id):
        p = preference_for(request, business_id)
        result = payload(p)
        # Safe status only: never expose provider diagnostics, codes or secrets.
        result['recent'] = list(OwnerSms.objects.filter(business=p.business, owner=request.user).exclude(event_type='verification').order_by('-created_at').values('id', 'event_type', 'status', 'created_at', 'message')[:20])
        return Response(result)

    @transaction.atomic
    def patch(self, request, business_id):
        p = preference_for(request, business_id)
        data = PreferencesInput(data=request.data)
        data.is_valid(raise_exception=True)
        if data.validated_data['enabled'] and (not p.phone or not p.verified_at):
            return Response({'detail': 'Verify your SMS number before enabling alerts.'}, status=400)
        if data.validated_data['enabled'] and not provider_ready():
            return Response({'detail': 'SMS is temporarily unavailable. Please try again later.'}, status=503)
        p.enabled = data.validated_data['enabled']
        p.event_types = list(dict.fromkeys(data.validated_data['eventTypes']))
        p.save(update_fields=['enabled', 'event_types', 'updated_at'])
        if not p.enabled:
            OwnerSms.objects.filter(business=p.business, status='pending').exclude(event_type='verification').update(status='cancelled')
        else:
            OwnerSms.objects.filter(business=p.business, status='pending').exclude(event_type__in=p.event_types + ['verification']).update(status='cancelled')
        return Response(payload(p))


class OwnerSmsRequestCode(APIView):
    permission_classes = [IsAuthenticated]
    @transaction.atomic
    def post(self, request, business_id):
        p = preference_for(request, business_id)
        data = PhoneInput(data=request.data)
        data.is_valid(raise_exception=True)
        if not provider_ready():
            return Response({'detail': 'SMS is temporarily unavailable. Please try again later.'}, status=503)
        now = timezone.now()
        sent = OwnerSms.objects.filter(business=p.business, event_type='verification')
        if sent.filter(created_at__gte=now-timedelta(seconds=60)).exists() or sent.filter(created_at__gte=now-timedelta(hours=1)).count() >= 3:
            return Response({'detail': 'Please wait before requesting another code. Maximum three codes per hour.'}, status=429)
        code = f'{secrets.randbelow(1000000):06d}'
        p.pending_phone = data.validated_data['phone']
        p.challenge = uuid.uuid4()
        p.code_hash = make_password(code)
        p.code_expires_at = now + timedelta(minutes=10)
        p.code_attempts = 0
        p.save()
        OwnerSms.objects.filter(business=p.business, event_type='verification', status='pending').update(status='cancelled', message='')
        OwnerSms.objects.create(business=p.business, owner=request.user, recipient=p.pending_phone,
            event_type='verification', source_id=str(p.challenge), dedupe_key=f'verify:{p.challenge}',
            message=f'StockFlow: Your owner SMS verification code is {code}. Expires in 10 minutes. Do not share this code.')
        return Response({'detail': 'Verification SMS queued. Enter the code when it arrives.', **payload(p)}, status=202)


class OwnerSmsVerifyCode(APIView):
    permission_classes = [IsAuthenticated]
    @transaction.atomic
    def post(self, request, business_id):
        p = preference_for(request, business_id)
        data = CodeInput(data=request.data)
        data.is_valid(raise_exception=True)
        if not p.code_hash or not p.code_expires_at or p.code_expires_at <= timezone.now() or p.code_attempts >= 5:
            return Response({'detail': 'Code expired or unavailable. Request a new code.'}, status=400)
        p.code_attempts += 1
        p.save(update_fields=['code_attempts'])
        if not check_password(data.validated_data['code'], p.code_hash):
            return Response({'detail': 'Incorrect verification code.'}, status=400)
        p.phone = p.pending_phone
        p.verified_at = timezone.now()
        p.pending_phone = p.code_hash = ''
        p.challenge = p.code_expires_at = None
        p.save()
        # Never deliver an older event to a newly chosen phone number.
        OwnerSms.objects.filter(business=p.business, status='pending').exclude(recipient=p.phone).update(status='cancelled', message='')
        return Response(payload(p))
