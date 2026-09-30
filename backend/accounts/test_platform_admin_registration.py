from unittest.mock import patch
from django.contrib.auth import get_user_model, authenticate
from django.contrib.admin.models import LogEntry
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from businesses.models import Business
from platform_events.models import PlatformEvent

User=get_user_model()
@override_settings(AUTH_PASSWORD_VALIDATORS=[{'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator','OPTIONS':{'min_length':10}}])
class RegistrationTests(TestCase):
    def setUp(self):
        cache.clear();self.client=APIClient()
        self.admin=User.objects.create_superuser(email='admin@example.com',password='AdminSecret123!')
        self.user=User.objects.create_user(email='owner@example.com',password='OwnerSecret123!')
        self.url='/api/platform-admin/administrators/register/'
        self.payload=dict(fullName='New Administrator',email='NewAdmin@Example.com',phone='0240000000',newPassword='NewSecret987!Ab',confirmPassword='NewSecret987!Ab',adminPassword='AdminSecret123!',confirmAccess=True)
    def submit(self,**changes):return self.client.post(self.url,dict(self.payload,**changes),format='json')
    def test_only_full_platform_admin_can_register(self):
        self.assertIn(self.submit().status_code,(401,403))
        for staff in (False,True):
            self.user.is_staff=staff;self.user.save();self.client.force_authenticate(self.user)
            self.assertEqual(self.submit().status_code,403)
        self.assertFalse(User.objects.filter(email__iexact=self.payload['email']).exists())
    def test_register_login_without_business_and_audit(self):
        self.client.force_authenticate(self.admin)
        r=self.submit();self.assertEqual(r.status_code,201)
        u=User.objects.get(email='newadmin@example.com')
        self.assertTrue(u.is_active and u.is_staff and u.is_superuser)
        self.assertEqual(authenticate(email=u.email,password=self.payload['newPassword']).pk,u.pk)
        self.assertFalse(Business.objects.filter(owner=u).exists())
        self.assertTrue(LogEntry.objects.filter(change_message='New platform administrator registered').exists())
        self.assertTrue(PlatformEvent.objects.filter(action='admin.account_created',object_id=str(u.pk)).exists())
        self.assertNotIn(self.payload['newPassword'],str(r.data))
        self.assertNotIn(self.payload['newPassword'],str(list(PlatformEvent.objects.values())))
        self.client.force_authenticate(u)
        self.assertEqual(self.client.get('/api/platform-admin/overview/').status_code,200)
    def test_wrong_authorising_password(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.submit(adminPassword='wrong').status_code,400)
        self.assertFalse(User.objects.filter(email__iexact=self.payload['email']).exists())
        self.assertTrue(PlatformEvent.objects.filter(action='admin.registration_denied').exists())
    def test_duplicate_case_does_not_promote_existing_user(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.submit(email='OWNER@example.com').status_code,400)
        self.user.refresh_from_db();self.assertFalse(self.user.is_superuser)
    def test_validation_and_confirmation(self):
        self.client.force_authenticate(self.admin)
        for changes in [dict(confirmAccess=False),dict(confirmPassword='different'),dict(newPassword='short',confirmPassword='short'),dict(fullName=''),dict(email='bad')]:
            cache.clear();self.assertEqual(self.submit(**changes).status_code,400)
        self.assertFalse(User.objects.filter(email__iexact=self.payload['email']).exists())
    def test_audit_failure_rolls_back_account(self):
        self.client.force_authenticate(self.admin)
        with patch('accounts.platform_management.LogEntry.objects.create',side_effect=RuntimeError('offline')):
            with self.assertRaises(RuntimeError):self.submit()
        self.assertFalse(User.objects.filter(email__iexact=self.payload['email']).exists())
    def test_registration_is_rate_limited(self):
        self.client.force_authenticate(self.admin)
        for _ in range(5):self.submit(adminPassword='wrong')
        self.assertEqual(self.submit().status_code,429)
