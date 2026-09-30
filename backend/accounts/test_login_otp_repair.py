from datetime import timedelta
from unittest.mock import patch
from django.utils import timezone
from .test_login_otp import LoginOTPAPITests
from .models import PendingLoginChallenge
from . import login_otp_service as service

class LoginOTPRepairTests(LoginOTPAPITests):
    def allow_resend(self, token):
        PendingLoginChallenge.objects.filter(challenge_token=token).update(resend_available_at=timezone.now()-timedelta(seconds=1))

    def test_admin_password_alone_cannot_access_api(self):
        self.user.is_staff = self.user.is_superuser = True
        self.user.save()
        token = self.start_challenge()
        self.client.credentials(HTTP_AUTHORIZATION='Bearer '+token)
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)
        self.client.credentials()
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)

    def test_verified_code_cannot_be_replayed(self):
        token, otp = self.request_code()
        self.assertEqual(self.client.post(self.verify_url, {'challengeId':token,'otp':otp}).status_code,200)
        self.assertEqual(self.client.post(self.verify_url, {'challengeId':token,'otp':otp}).status_code,400)

    def test_delivery_failure_can_recover_after_cooldown(self):
        token = self.start_challenge()
        with patch.object(service, '_send_otp_email', side_effect=TimeoutError):
            self.assertEqual(self.client.post(self.deliver_url, {'challengeId':token}).status_code,503)
        self.assertEqual(self.client.post(self.resend_url, {'challengeId':token}).status_code,400)
        self.assertEqual(self.client.post(self.deliver_url, {'challengeId':token}).status_code,400)
        self.allow_resend(token)
        self.assertEqual(self.client.post(self.resend_url, {'challengeId':token}).status_code,200)

    def test_zero_messages_is_a_delivery_failure(self):
        token = self.start_challenge()
        with patch.object(service, 'send_mail', return_value=0):
            self.assertEqual(self.client.post(self.deliver_url, {'challengeId':token}).status_code,503)

    def test_stalled_sending_can_be_replaced_after_cooldown(self):
        token = self.start_challenge()
        PendingLoginChallenge.objects.filter(challenge_token=token).update(otp_hash='sending$stalled',resend_available_at=timezone.now()+timedelta(seconds=60))
        self.assertEqual(self.client.post(self.resend_url, {'challengeId':token}).status_code,400)
        self.allow_resend(token)
        self.assertEqual(self.client.post(self.resend_url, {'challengeId':token}).status_code,200)

    def test_late_delivery_cannot_overwrite_new_generation(self):
        token = self.start_challenge()
        newer = service._otp_hash(challenge_token=token,otp='345678')
        def newer_delivery(**kwargs):
            PendingLoginChallenge.objects.filter(challenge_token=token).update(otp_hash=newer)
        with patch.object(service, '_send_otp_email',side_effect=newer_delivery):
            self.assertEqual(self.client.post(self.deliver_url, {'challengeId':token}).status_code,400)
        self.assertEqual(PendingLoginChallenge.objects.get(challenge_token=token).otp_hash,newer)

    def test_expired_challenge_cannot_be_resurrected_by_resend(self):
        token, _ = self.request_code()
        self.allow_resend(token)
        PendingLoginChallenge.objects.filter(challenge_token=token).update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.client.post(self.resend_url, {'challengeId':token}).status_code,400)

    def test_pending_and_sending_never_issue_tokens(self):
        token = self.start_challenge()
        for stored_hash in ('pending$unissued','sending$unconfirmed'):
            PendingLoginChallenge.objects.filter(challenge_token=token).update(otp_hash=stored_hash)
            response=self.client.post(self.verify_url, {'challengeId':token,'otp':'123456'})
            self.assertEqual(response.status_code,400)
            self.assertNotIn('access',response.data)

    def test_invalid_old_bearer_does_not_block_password_login(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer old-invalid-token')
        self.start_challenge()

    def test_resend_cooldown_applies_before_first_delivery(self):
        token = self.start_challenge()
        self.assertEqual(self.client.post(self.resend_url, {'challengeId':token}).status_code,400)
        self.assertEqual(self.client.post(self.deliver_url, {'challengeId':token}).status_code,200)
