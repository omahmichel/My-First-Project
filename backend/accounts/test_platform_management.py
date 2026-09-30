from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.admin.models import LogEntry
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from platform_events.models import PlatformEvent,BugReport
from platform_events.capture import record_event

User=get_user_model()
class ManagementTests(TestCase):
    def setUp(self):
        cache.clear();self.client=APIClient()
        self.admin=User.objects.create_superuser(email='admin@example.com',password='AdminSecret123!')
        self.user=User.objects.create_user(email='owner@example.com',password='OwnerSecret123!')
    def grant(self,**changes):
        data=dict(userId=self.user.pk,confirmEmail=self.user.email,password='AdminSecret123!');data.update(changes)
        return self.client.post('/api/platform-admin/administrators/',data,format='json')
    def test_business_user_and_staff_cannot_manage(self):
        for staff in (False,True):
            self.user.is_staff=staff;self.user.save()
            self.client.force_authenticate(self.user)
            for url in ('administrators/','bugs/'):
                self.assertEqual(self.client.get('/api/platform-admin/'+url).status_code,403)
            self.assertEqual(self.grant().status_code,403)
    def test_anonymous_denied(self):
        self.assertIn(self.client.get('/api/platform-admin/bugs/').status_code,(401,403))
    def test_grant_requires_correct_password_and_email(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.grant(password='wrong').status_code,400)
        self.assertTrue(PlatformEvent.objects.filter(action='admin.grant_denied').exists())
        self.assertEqual(self.grant(confirmEmail='wrong@example.com').status_code,400)
        self.user.refresh_from_db();self.assertFalse(self.user.is_superuser)
    def test_grant_is_audited_and_idempotent(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.grant().status_code,200)
        self.user.refresh_from_db();self.assertTrue(self.user.is_staff and self.user.is_superuser)
        self.assertTrue(LogEntry.objects.filter(change_message='Platform administrator access granted').exists())
        self.assertTrue(PlatformEvent.objects.filter(action='admin.access_granted',object_id=str(self.user.pk)).exists())
        self.assertFalse(self.grant().data['changed'])
        self.assertNotIn('AdminSecret123!',str(list(PlatformEvent.objects.values())))
    def test_grant_rolls_back_if_durable_audit_fails(self):
        self.client.force_authenticate(self.admin)
        with patch('accounts.platform_management.LogEntry.objects.create',side_effect=RuntimeError('audit offline')):
            with self.assertRaises(RuntimeError):self.grant()
        self.user.refresh_from_db();self.assertFalse(self.user.is_superuser)
    def test_inactive_target_not_promoted(self):
        self.user.is_active=False;self.user.save();self.client.force_authenticate(self.admin)
        self.assertEqual(self.grant().status_code,404)
    def test_grant_rate_limit(self):
        self.client.force_authenticate(self.admin)
        for _ in range(5):self.grant(password='wrong')
        self.assertEqual(self.grant(password='wrong').status_code,429)
    def test_search_uses_id_and_empty_search_lists_admins(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get('/api/platform-admin/administrators/').data['count'],1)
        result=self.client.get('/api/platform-admin/administrators/?q=owner').data['results']
        self.assertEqual(result[0]['id'],self.user.pk)
    def test_errors_create_bugs_but_warnings_do_not(self):
        record_event(category='system',action='example.error',summary='Safe title',severity='error')
        self.assertEqual(BugReport.objects.count(),1)
        record_event(category='security',action='request.denied',summary='Denied',severity='warning')
        self.assertEqual(BugReport.objects.count(),1)
    def test_bug_update_authorization_conflict_audit_and_filters(self):
        bug=BugReport.objects.create(title='Example',source='support',reporter_id=str(self.user.pk))
        url=f'/api/platform-admin/bugs/{bug.pk}/status/'
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.post(url,{'status':'resolved','expectedStatus':'open'}).status_code,403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post(url,{'status':'investigating','expectedStatus':'open'}).status_code,200)
        self.assertEqual(self.client.post(url,{'status':'resolved','expectedStatus':'open'}).status_code,409)
        self.assertEqual(self.client.get('/api/platform-admin/bugs/?status=investigating').data['count'],1)
        self.assertTrue(PlatformEvent.objects.filter(action='bug.status_changed').exists())
