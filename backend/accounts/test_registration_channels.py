import re
from datetime import timedelta
from unittest.mock import patch, Mock
from django.test import override_settings
from django.utils import timezone
from django.core import mail
from django.core.cache import cache
from rest_framework.test import APITestCase
from .models import PendingRegistration, User

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class RegistrationChannelTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.payload = dict(email='channels@example.com', full_name='Channel Test', phone='0241234567', password='StrongPass123!', password_confirm='StrongPass123!')
        self.sender_patch = patch('accounts.registration_sms.send_registration_sms')
        self.send = self.sender_patch.start()
        self.addCleanup(patch.stopall)

    def start(self, channel='email'):
        response = self.client.post('/api/auth/register/', {**self.payload, 'channel':channel}, format='json')
        self.assertEqual(response.status_code, 202, response.data)
        self.session = response.data
        return response

    def cooldown(self):
        PendingRegistration.objects.update(resend_available_at=timezone.now()-timedelta(seconds=1))

    def resend(self, channel, **extra):
        return self.client.post('/api/auth/register/resend/', dict(email=self.payload['email'], challengeId=self.session['challengeId'], channel=channel, **extra), format='json')

    def verify(self, code, token=True):
        data=dict(email=self.payload['email'],otp=code)
        if token: data['challengeId']=self.session['challengeId']
        return self.client.post('/api/auth/register/verify/',data,format='json')

    def sms_code(self):
        return re.search(r'\b(\d{6})\b',self.send.call_args.kwargs['message']).group(1)

    def test_sms_signup_marks_phone_only(self):
        self.start('sms')
        self.assertFalse(User.objects.exists())
        self.assertEqual(self.send.call_args.kwargs['recipient'],'0241234567')
        self.assertEqual(self.verify(self.sms_code()).status_code,201)
        user=User.objects.get(email=self.payload['email'])
        self.assertEqual(user.registration_verified_channel,'sms')
        self.assertEqual(user.registration_verified_contact,'0241234567')
        self.assertIsNone(user.email_verified_at)
        self.assertTrue(user.check_password(self.payload['password']))

    def test_switch_invalidates_old_code_and_preserves_details(self):
        self.start()
        old=re.search(r'\b(\d{6})\b',mail.outbox[-1].body).group(1)
        self.cooldown()
        self.assertEqual(self.resend('sms').status_code,200)
        self.assertEqual(self.verify(old).status_code,400)
        self.assertEqual(self.verify(self.sms_code()).status_code,201)
        self.assertEqual(User.objects.get().full_name,self.payload['full_name'])

    def test_sms_requires_session_token(self):
        self.start('sms')
        self.assertEqual(self.verify(self.sms_code(),False).status_code,400)
        self.assertFalse(User.objects.exists())

    def test_sms_switch_requires_token_and_respects_cooldown(self):
        self.start()
        self.assertEqual(self.resend('sms').status_code,400)
        self.cooldown()
        response=self.client.post('/api/auth/register/resend/',dict(email=self.payload['email'],channel='sms'),format='json')
        self.assertEqual(response.status_code,400)
        self.send.assert_not_called()

    def test_failed_sms_switch_keeps_valid_email_code(self):
        self.start()
        old=re.search(r'\b(\d{6})\b',mail.outbox[-1].body).group(1)
        self.cooldown();self.send.side_effect=RuntimeError('provider unavailable')
        self.assertEqual(self.resend('sms').status_code,503)
        self.assertEqual(PendingRegistration.objects.get().delivery_channel,'email')
        self.assertEqual(self.verify(old).status_code,201)
        self.assertIsNotNone(User.objects.get().email_verified_at)

    def test_invalid_phone_and_whatsapp_rejected_before_send(self):
        for data in ({**self.payload,'phone':'123','channel':'sms'}, {**self.payload,'channel':'whatsapp'}):
            self.assertEqual(self.client.post('/api/auth/register/',data,format='json').status_code,400)
        self.send.assert_not_called()

    def test_old_session_token_cannot_verify_replaced_registration(self):
        self.start('sms');old_token=self.session['challengeId'];self.cooldown();self.start('sms')
        self.session['challengeId']=old_token
        self.assertEqual(self.verify(self.sms_code()).status_code,400)

    def test_delivery_failure_does_not_create_account(self):
        self.send.side_effect=RuntimeError('offline')
        response=self.client.post('/api/auth/register/',{**self.payload,'channel':'sms'},format='json')
        self.assertEqual(response.status_code,503)
        self.assertFalse(User.objects.exists());self.assertFalse(PendingRegistration.objects.exists())

    def test_email_recovery_not_sent_to_unverified_address(self):
        self.start('sms');self.verify(self.sms_code())
        before=len(mail.outbox)
        self.client.post('/api/auth/password-reset/request/',{'email':self.payload['email']},format='json')
        self.assertEqual(len(mail.outbox),before)

    def test_otp_sender_marks_sms_type_without_saving_code(self):
        self.sender_patch.stop()
        from .registration_sms import send_registration_sms
        with override_settings(MNOTIFY_API_KEY='fake-test-key',MNOTIFY_SENDER_ID='StockFlow'), patch('accounts.registration_sms.requests.post') as post:
            post.return_value=Mock(status_code=200)
            post.return_value.json.return_value={'status':'success','summary':{}}
            send_registration_sms(recipient='0241234567',message='Your test code: 123456')
            self.assertEqual(post.call_args.kwargs['json']['sms_type'],'otp')
