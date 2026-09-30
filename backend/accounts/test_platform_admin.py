from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.admin.models import LogEntry
from django.test import TestCase
from rest_framework.test import APIClient
from businesses.models import Business, BusinessMembership, SubscriptionPayment
from accounts.serializers import UserSerializer

User = get_user_model()
BASE = '/api/platform-admin/'

class PlatformAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email='platform@example.com', password='SafeTestPass123!', full_name='Admin')
        self.owner = User.objects.create_user(email='owner@example.com', password='SafeTestPass123!', full_name='Owner')
        self.business = Business.objects.create(owner=self.owner, name='Test shop', slug='test-shop', business_type='boutique')
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_all_read_endpoints_require_platform_admin(self):
        staff = User.objects.create_user(email='staff@example.com', is_staff=True)
        for actor in (None, self.owner, staff):
            self.client.force_authenticate(actor)
            for endpoint in ('notifications/', 'overview/', 'users/', 'businesses/', 'subscriptions/', 'activity/', f'users/{self.owner.pk}/', f'businesses/{self.business.pk}/'):
                self.assertIn(self.client.get(BASE+endpoint).status_code, (401,403))
            r=self.client.post(BASE+f'users/{self.owner.pk}/status/', {'active':False,'expectedActive':True,'reason':'Security review'}, format='json')
            self.assertIn(r.status_code,(401,403))
        self.owner.refresh_from_db();self.assertTrue(self.owner.is_active)

    def test_inactive_admin_rejected(self):
        self.admin.is_active=False;self.admin.save()
        self.assertEqual(self.client.get(BASE+'overview/').status_code,403)

    def test_overview_and_private_responses(self):
        r=self.client.get(BASE+'overview/')
        self.assertEqual(r.data['businesses'],1)
        self.assertEqual(r['Cache-Control'],'private, no-store')

    def test_search_pagination_and_safe_user_fields(self):
        User.objects.bulk_create([User(email=f'user{i}@example.com',full_name='Member') for i in range(25)])
        r=self.client.get(BASE+'users/')
        self.assertEqual(len(r.data['results']),20)
        self.assertIsNotNone(r.data['next'])
        r=self.client.get(BASE+'users/?q=owner@example.com')
        self.assertEqual(r.data['count'],1)
        self.assertNotIn('password',r.data['results'][0])

    def test_details_include_related_businesses_and_memberships(self):
        BusinessMembership.objects.create(user=self.owner,business=self.business,role='owner')
        r=self.client.get(BASE+f'users/{self.owner.pk}/')
        self.assertEqual(r.data['ownedBusinessCount'],1)
        r=self.client.get(BASE+f'businesses/{self.business.pk}/')
        self.assertEqual(r.data['memberCount'],1)

    def test_status_change_audited_and_repeated_request_does_not_duplicate(self):
        url=BASE+f'users/{self.owner.pk}/status/'
        data={'active':False,'expectedActive':True,'reason':'Requested account suspension'}
        self.assertEqual(self.client.post(url,data,format='json').status_code,200)
        self.owner.refresh_from_db();self.assertFalse(self.owner.is_active)
        self.assertEqual(LogEntry.objects.count(),1)
        self.assertEqual(self.client.post(url,data,format='json').status_code,409)
        self.assertEqual(LogEntry.objects.count(),1)
        self.assertEqual(self.client.get(BASE+'activity/?q=admin.status_changed').data['count'],1)

    def test_cannot_suspend_self_or_other_administrators(self):
        for u in (self.admin,User.objects.create_user(email='other@example.com',is_staff=True)):
            r=self.client.post(BASE+f'users/{u.pk}/status/',{'active':False,'expectedActive':True,'reason':'Attempt suspension'},format='json')
            self.assertEqual(r.status_code,400)
        self.assertEqual(LogEntry.objects.count(),0)

    def test_status_requires_reason_and_rejects_privilege_fields(self):
        url=BASE+f'users/{self.owner.pk}/status/'
        for data in ({'active':False,'expectedActive':True}, {'active':False,'expectedActive':True,'reason':'Review account','is_superuser':True}):
            self.assertEqual(self.client.post(url,data,format='json').status_code,400)
        self.owner.refresh_from_db();self.assertTrue(self.owner.is_active)

    def test_audit_failure_rolls_back_status(self):
        with patch('accounts.platform_admin.LogEntry.objects.create',side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.client.post(BASE+f'users/{self.owner.pk}/status/',{'active':False,'expectedActive':True,'reason':'Review account'},format='json')
        self.owner.refresh_from_db();self.assertTrue(self.owner.is_active)

    def test_business_suspend_restore_keeps_subscription_dates(self):
        original=self.business.trial_ends_at
        url=BASE+f'businesses/{self.business.pk}/status/'
        for active in (False,True):
            r=self.client.post(url,{'active':active,'expectedActive':not active,'reason':'Business review complete'},format='json')
            self.assertEqual(r.status_code,200)
        self.business.refresh_from_db();self.assertEqual(self.business.trial_ends_at,original)
        self.assertEqual(LogEntry.objects.count(),2)

    def test_subscription_list_contains_no_gateway_secrets(self):
        SubscriptionPayment.objects.create(business=self.business,initiated_by=self.owner,initiated_by_email=self.owner.email,initiated_by_name='Owner')
        r=self.client.get(BASE+'subscriptions/')
        self.assertEqual(r.data['count'],1)
        self.assertNotIn('authorization_url',r.data['results'][0])

    def test_admin_flag_is_read_only(self):
        data=UserSerializer(self.owner,data={'is_platform_admin':True},partial=True)
        self.assertTrue(data.is_valid());data.save()
        self.assertFalse(UserSerializer(self.owner).data['is_platform_admin'])
        self.assertTrue(UserSerializer(self.admin).data['is_platform_admin'])

    def test_existing_jwt_cannot_access_admin_after_suspension(self):
        from rest_framework_simplejwt.tokens import AccessToken
        token=str(AccessToken.for_user(self.admin))
        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer '+token)
        self.assertEqual(self.client.get(BASE+'overview/').status_code,200)
        self.admin.is_active=False;self.admin.save(update_fields=['is_active'])
        self.assertEqual(self.client.get(BASE+'overview/').status_code,401)

    def test_notifications_use_dates_exclude_inactive_businesses_and_bound_lists(self):
        from datetime import timedelta
        from django.utils import timezone
        now = timezone.now()
        for i in range(7):
            Business.objects.create(owner=self.owner, name=f'Paid {i}', slug=f'paid-{i}', business_type='boutique', subscription_status='active', subscription_ends_at=now+timedelta(days=3))
        Business.objects.create(owner=self.owner, name='Suspended', slug='suspended', status='inactive', subscription_status='active', subscription_ends_at=now+timedelta(days=3))
        Business.objects.create(owner=self.owner, name='Ended paid', slug='ended-paid', subscription_status='active', subscription_ends_at=now-timedelta(seconds=1))
        Business.objects.create(owner=self.owner, name='Ending trial', slug='ending-trial', subscription_status='trial', trial_ends_at=now+timedelta(days=2))
        Business.objects.create(owner=self.owner, name='Ended trial', slug='ended-trial', subscription_status='trial', trial_ends_at=now-timedelta(seconds=1))
        SubscriptionPayment.objects.create(business=self.business,initiated_by=self.owner,initiated_by_email=self.owner.email,initiated_by_name='Owner')
        response=self.client.get(BASE+'notifications/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response['Cache-Control'],'private, no-store')
        groups={g['key']:g for g in response.data['groups']}
        self.assertEqual(groups['current']['total'],7)
        self.assertEqual(len(groups['current']['items']),5)
        self.assertEqual(groups['expired']['total'],2)
        self.assertIn('Ending trial',[i['title'] for i in groups['trials']['items']])
        self.assertEqual(groups['pending']['total'],1)
        self.assertEqual(groups['pending']['items'][0]['tab'],'subscriptions')
        self.assertNotIn('authorization_url',str(response.data))
