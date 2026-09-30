from datetime import timedelta
import importlib
import logging
from io import StringIO
from unittest.mock import patch
from django.apps import apps
from django.contrib.admin.models import LogEntry,CHANGE
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.management import call_command
from django.db import transaction,DatabaseError,connection
from django.http import JsonResponse
from django.test import TestCase,override_settings
from django.urls import path,include
from django.utils import timezone
from rest_framework.decorators import api_view,permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.test import APIClient
from businesses.models import Business
from .models import PlatformEvent
from .capture import record_event,audited_job,current_request,current_job
from .client import ClientError

@api_view(['GET','POST'])
@permission_classes([AllowAny])
def sample(request,code):
    return Response({'password':'NEVER_STORE_THIS','token':'NEVER_STORE_THIS'},status=code)

@api_view(['GET'])
@permission_classes([AllowAny])
def crash(request): raise RuntimeError('NEVER_STORE_THIS')

urlpatterns=[path('api/platform-admin/',include('accounts.platform_urls')),
 path('api/sample/<int:code>/',sample),path('api/crash/',crash),
 path('api/platform-events/client-error/',ClientError.as_view())]

@override_settings(ROOT_URLCONF='platform_events.tests')
class EventTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(email='owner@example.com',password='TestPass123!')
        self.admin=get_user_model().objects.create_superuser(email='admin@example.com',password='TestPass123!')
        self.business=Business.objects.create(owner=self.user,name='Demo',slug='demo',business_type='boutique')
        self.client=APIClient();cache.clear()
        PlatformEvent.objects.all().delete()

    def test_request_validation_no_payload_or_query_leak(self):
        r=self.client.post('/api/sample/400/?token=NEVER_STORE_THIS',{'password':'NEVER_STORE_THIS'},format='json')
        self.assertEqual(r.status_code,400)
        e=PlatformEvent.objects.get(action='request.invalid')
        self.assertEqual(e.category,'validation');self.assertEqual(e.route,'api/sample/<int:code>/')
        self.assertNotIn('NEVER_STORE_THIS',str(list(PlatformEvent.objects.values())))

    def test_success_reads_and_writes_classified(self):
        self.client.get('/api/sample/200/');self.client.post('/api/sample/201/')
        self.assertEqual(set(PlatformEvent.objects.values_list('category',flat=True)),{'access','business'})

    def test_rate_limit_and_access_denial_are_not_claimed_as_attacks(self):
        self.client.get('/api/sample/429/');self.client.get('/api/sample/403/')
        self.assertEqual(PlatformEvent.objects.filter(category='security').count(),2)
        self.assertFalse(PlatformEvent.objects.filter(summary__icontains='confirmed attack').exists())

    def test_repeats_aggregate_and_ignore_forwarded_ip(self):
        now=timezone.now()
        with patch('platform_events.capture.timezone.now',return_value=now):
            for _ in range(8): self.client.get('/api/sample/401/',HTTP_X_FORWARDED_FOR='203.0.113.123')
        e=PlatformEvent.objects.get(action='request.denied')
        self.assertEqual(e.occurrences,8);self.assertEqual(e.peer_ip,'127.0.0.1')

    def test_probe_logged_without_raw_path(self):
        self.client.get('/.env/NEVER_STORE_THIS')
        e=PlatformEvent.objects.get(action='request.suspected_probe')
        self.assertEqual(e.route,'');self.assertNotIn('NEVER_STORE_THIS',str(e.__dict__))

    def test_server_error_captured_without_exception_text(self):
        self.client.raise_request_exception=False
        self.assertEqual(self.client.get('/api/crash/').status_code,500)
        self.assertTrue(PlatformEvent.objects.filter(action='request.failed',severity='error').exists())
        self.assertNotIn('NEVER_STORE_THIS',str(list(PlatformEvent.objects.values())))
        self.assertIsNone(current_request.get())

    def test_records_only_logged_after_commit_and_rollback_discarded(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.business.name='Changed';self.business.save(update_fields=['name'])
        self.assertTrue(PlatformEvent.objects.filter(action='businesses.business.updated',business_id=str(self.business.pk)).exists())
        PlatformEvent.objects.all().delete()
        with self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    self.business.name='Rollback';self.business.save();raise ValueError()
            except ValueError: pass
        self.assertFalse(PlatformEvent.objects.exists())

    def test_log_store_failure_does_not_break_business_transaction(self):
        with patch('platform_events.capture.PlatformEvent.objects.create',side_effect=DatabaseError('NEVER_STORE_THIS')):
            record_event(category='system',action='test',summary='Test')
        self.assertTrue(get_user_model().objects.filter(pk=self.user.pk).exists())

    def test_background_job_failure_and_context_cleanup(self):
        @audited_job('example_worker')
        def worker(): raise ValueError('NEVER_STORE_THIS')
        with self.assertRaises(ValueError): worker()
        e=PlatformEvent.objects.get(action='job.failed')
        self.assertEqual(e.details['job'],'example_worker');self.assertEqual(e.severity,'error')
        self.assertNotIn('NEVER_STORE_THIS',str(e.__dict__));self.assertEqual(current_job.get(),'')

    def test_logger_omits_raw_messages(self):
        logging.getLogger('inventory.photo_views').error('Secret NEVER_STORE_THIS')
        e=PlatformEvent.objects.get(action='application.error')
        self.assertNotIn('NEVER_STORE_THIS',str(e.__dict__))

    def test_activity_filters_authorization_and_no_self_logging(self):
        record_event(category='security',action='test.security',summary='Safe test alert',severity='warning')
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get('/api/platform-admin/activity/').status_code,403)
        self.client.force_authenticate(self.admin)
        before=PlatformEvent.objects.count()
        r=self.client.get('/api/platform-admin/activity/?category=security&status=warning&q=test.security')
        self.assertEqual(r.status_code,200);self.assertEqual(r.data['count'],1)
        self.assertEqual(PlatformEvent.objects.count(),before)
        self.assertEqual(r['Cache-Control'],'private, no-store')
        self.assertEqual(self.client.get('/api/platform-admin/activity/?from=wrong').status_code,400)

    def test_recent_alerts_appear_in_notifications(self):
        record_event(category='system',action='test.alert',summary='Safe test error',severity='error')
        self.client.force_authenticate(self.admin)
        r=self.client.get('/api/platform-admin/notifications/')
        self.assertEqual(r.data['groups'][0]['key'],'platform-alerts')
        self.assertEqual(r.data['groups'][0]['items'][0]['tab'],'activity')

    def test_browser_reports_require_auth_and_reject_sensitive_fields(self):
        url='/api/platform-events/client-error/'
        self.assertIn(self.client.post(url,{},format='json').status_code,(401,403))
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.post(url,{'kind':'javascript_error','area':'app','password':'NEVER_STORE_THIS'},format='json').status_code,400)
        self.assertEqual(self.client.post(url,{'kind':'javascript_error','area':'app'},format='json').status_code,204)
        e=PlatformEvent.objects.get(action='browser.javascript_error')
        self.assertEqual(e.actor_id,str(self.user.pk));self.assertEqual(e.source,'browser-report')
        self.assertNotIn('NEVER_STORE_THIS',str(list(PlatformEvent.objects.values())))

    def test_check_command_records_result(self):
        call_command('record_system_check',stdout=StringIO())
        self.assertTrue(PlatformEvent.objects.filter(action='check.result').exists())

    def test_failed_system_check_is_recorded(self):
        from django.core.checks import Error
        from django.core.management.base import CommandError
        with patch('platform_events.management.commands.record_system_check.run_checks', return_value=[Error('NEVER_STORE_THIS', id='test.E001')]):
            with self.assertRaises(CommandError):
                call_command('record_system_check', stdout=StringIO())
        event=PlatformEvent.objects.get(action='check.result')
        self.assertEqual(event.severity,'error')
        self.assertEqual(event.details['check_ids'],['test.E001'])
        self.assertNotIn('NEVER_STORE_THIS',str(event.__dict__))

    def test_old_admin_history_import_is_idempotent(self):
        import json
        entry=LogEntry.objects.create(user=self.admin,content_type=ContentType.objects.get_for_model(self.user),object_id=str(self.user.pk),object_repr='Old account',action_flag=CHANGE,change_message=json.dumps({'platformAdmin':True,'targetKind':'users','afterActive':False,'reason':'NEVER_STORE_THIS'}))
        module=importlib.import_module('platform_events.migrations.0002_import_admin_history')
        from types import SimpleNamespace
        editor=SimpleNamespace(connection=connection)
        module.import_history(apps,editor);module.import_history(apps,editor)
        self.assertEqual(PlatformEvent.objects.filter(source='legacy-admin').count(),1)
        self.assertNotIn('NEVER_STORE_THIS',str(list(PlatformEvent.objects.values())))

    def test_retention_is_preview_by_default(self):
        record_event(category='system',action='old',summary='Old event')
        PlatformEvent.objects.update(last_seen_at=timezone.now()-timedelta(days=100))
        call_command('prune_platform_events',stdout=StringIO())
        self.assertEqual(PlatformEvent.objects.count(),1)
