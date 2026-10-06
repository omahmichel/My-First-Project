from datetime import timedelta
from unittest.mock import patch, MagicMock
from django.utils import timezone
from .test_login_otp import LoginOTPAPITests
from .models import PendingLoginChallenge
from . import login_otp_service as service

class LoginOTPDeliveryTests(LoginOTPAPITests):
    def ready(self):
        token, otp = self.request_code()
        PendingLoginChallenge.objects.filter(challenge_token=token).update(resend_available_at=timezone.now()-timedelta(seconds=1),failed_attempts=2)
        return token, otp, PendingLoginChallenge.objects.get(challenge_token=token)

    def test_failed_resend_preserves_old_code_expiry_attempts_and_cooldown(self):
        token, otp, before = self.ready()
        with patch.object(service,'_send_otp_email',side_effect=TimeoutError):
            self.assertEqual(self.client.post(self.resend_url,{'challengeId':token}).status_code,503)
        after=PendingLoginChallenge.objects.get(challenge_token=token)
        self.assertEqual(after.otp_hash,before.otp_hash)
        self.assertEqual(after.expires_at,before.expires_at)
        self.assertEqual(after.failed_attempts,2)
        self.assertEqual(self.client.post(self.resend_url,{'challengeId':token}).status_code,400)
        self.assertEqual(self.client.post(self.verify_url,{'challengeId':token,'otp':otp}).status_code,200)

    def test_failure_does_not_overwrite_newer_generation(self):
        token, otp, before=self.ready()
        newer=service._otp_hash(challenge_token=token,otp='987654')
        def fail(**kwargs):
            PendingLoginChallenge.objects.filter(challenge_token=token).update(otp_hash=newer)
            raise TimeoutError()
        with patch.object(service,'_send_otp_email',side_effect=fail):
            self.assertEqual(self.client.post(self.resend_url,{'challengeId':token}).status_code,503)
        self.assertEqual(PendingLoginChallenge.objects.get(challenge_token=token).otp_hash,newer)

    def test_expiry_during_failed_send_is_not_extended(self):
        token, otp, before=self.ready()
        PendingLoginChallenge.objects.filter(challenge_token=token).update(expires_at=timezone.now()+timedelta(seconds=1))
        later=timezone.now()+timedelta(seconds=5)
        with patch.object(service,'_send_otp_email',side_effect=TimeoutError):
            self.client.post(self.resend_url,{'challengeId':token})
        with patch.object(service.timezone,'now',return_value=later):
            self.assertEqual(self.client.post(self.verify_url,{'challengeId':token,'otp':otp}).status_code,400)

    def test_failed_resend_does_not_reset_exhausted_attempts(self):
        token, otp, before=self.ready()
        PendingLoginChallenge.objects.filter(challenge_token=token).update(failed_attempts=5)
        with patch.object(service,'_send_otp_email',side_effect=TimeoutError):
            self.client.post(self.resend_url,{'challengeId':token})
        self.assertEqual(self.client.post(self.verify_url,{'challengeId':token,'otp':otp}).status_code,400)

    def test_successful_resend_replaces_previous_code(self):
        token, otp, before=self.ready()
        new='654321' if otp!='654321' else '123456'
        with patch.object(service,'_generate_otp',return_value=new):
            self.assertEqual(self.client.post(self.resend_url,{'challengeId':token}).status_code,200)
        self.assertEqual(self.client.post(self.verify_url,{'challengeId':token,'otp':otp}).status_code,400)
        self.assertEqual(self.client.post(self.verify_url,{'challengeId':token,'otp':new}).status_code,200)

    def test_close_failure_after_acceptance_does_not_fail_delivery(self):
        connection=MagicMock()
        connection.close.side_effect=OSError('sensitive provider detail')
        with patch.object(service,'get_connection',return_value=connection), patch.object(service,'send_mail',return_value=1):
            with self.assertLogs(service.__name__,level='WARNING') as logs:
                service._send_otp_email(user=self.user,otp='123456')
        self.assertNotIn('sensitive provider detail',' '.join(logs.output))
        self.assertNotIn('123456',' '.join(logs.output))

    def test_safe_failure_diagnostics_identify_connection_stage(self):
        connection=MagicMock()
        connection.open.side_effect=TimeoutError('secret data')
        with patch.object(service,'get_connection',return_value=connection):
            with self.assertLogs(service.__name__,level='WARNING') as logs:
                with self.assertRaises(TimeoutError):
                    service._send_otp_email(user=self.user,otp='123456')
        output=' '.join(logs.output)
        self.assertIn('stage=connect_auth',output)
        self.assertNotIn('secret data',output)
        self.assertNotIn('123456',output)
