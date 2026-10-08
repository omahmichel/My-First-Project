from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase
from businesses.branch_access import ensure_main_branch
from businesses.models import Business, BusinessMembership
from inventory.models import Product, BranchInventory, BranchStockMovement
from inventory.branch_service import apply_locked_branch_change
from sales.models import Sale
from sales.services import create_completed_sale
from platform_events.models import PlatformEvent
from .models import OwnerSms, OwnerSmsPreference
from .services import EVENT_TYPES, process_pending, queue_alert


@override_settings(MNOTIFY_API_KEY='fake', MNOTIFY_SENDER_ID='StockFlow', MNOTIFY_API_URL='https://sms.invalid',
                   SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['testserver', 'localhost'],
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class OwnerSmsTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(email='owner@example.com', password='owner-password', full_name='Shop Owner')
        self.other = User.objects.create_user(email='other@example.com', password='other-password')
        self.business = Business.objects.create(owner=self.owner, name='Example Shop', slug='example-shop', business_type='building_materials')
        BusinessMembership.objects.create(business=self.business, user=self.owner, role='owner')
        self.branch = ensure_main_branch(business=self.business, created_by=self.owner)
        self.product = Product.objects.create(business=self.business, name='Cement', sku='CEM', product_type='standard',
            unit='bag', stock=10, low_stock_level=2, cost_price=Decimal('8'), selling_price=Decimal('20'))
        self.inventory = BranchInventory.objects.create(branch=self.branch, product=self.product, stock=10, low_stock_level=2)
        self.pref = OwnerSmsPreference.objects.create(business=self.business, owner=self.owner, enabled=True,
            phone='0244000000', verified_at=timezone.now(), event_types=list(EVENT_TYPES))
        self.url = f'/api/businesses/{self.business.pk}/owner-sms/'
        self.client.force_authenticate(self.owner)

    def change(self, delta, kind='adjustment'):
        self.product.refresh_from_db(); self.inventory.refresh_from_db()
        with transaction.atomic():
            return apply_locked_branch_change(business=self.business, branch=self.branch, product=self.product,
                branch_inventory=self.inventory, stock_delta=delta, movement_type=kind,
                reason='Count corrected', user=self.owner, business_movement_type=kind if kind in ('stock_in', 'adjustment', 'damage', 'return', 'sale') else None)

    def alert(self, key='1', kind='sale'):
        return queue_alert(business_id=self.business.pk, event_type=kind, source_id=key, message='StockFlow: Test alert')

    def test_restock_and_adjustment_queue_once_without_provider_call(self):
        with patch('owner_alerts.services.MNotifySmsProvider.send') as send:
            self.change(5, 'stock_in'); self.change(-1)
        send.assert_not_called()
        self.assertEqual(list(OwnerSms.objects.values_list('event_type', flat=True)), ['restock', 'adjustment'])
        self.assertIn('Count corrected', OwnerSms.objects.get(event_type='adjustment').message)

    def test_low_stock_crossing_and_recovery(self):
        self.change(-8); self.change(-1)
        self.assertEqual(OwnerSms.objects.filter(event_type='low_stock').count(), 1)
        self.change(5, 'stock_in'); self.change(-4)
        self.assertEqual(OwnerSms.objects.filter(event_type='low_stock').count(), 2)

    def test_reserved_quantity_does_not_raise_physical_low_stock(self):
        with transaction.atomic():
            apply_locked_branch_change(business=self.business, branch=self.branch, product=self.product,
                branch_inventory=self.inventory, reserved_delta=9, movement_type='reserve', reason='Payment pending', user=self.owner)
        self.assertFalse(OwnerSms.objects.exists())

    def test_rollback_discards_stock_and_notifications(self):
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                self.change(-8)
                raise RuntimeError('rollback')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)
        self.assertFalse(OwnerSms.objects.exists())

    def test_capture_fault_preserves_stock_operation(self):
        with patch('owner_alerts.signals.queue_alert', side_effect=RuntimeError('notification broken')):
            self.change(2, 'stock_in')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 12)

    def test_real_cash_checkout_and_idempotency(self):
        data = {'items': [{'productId': self.product.pk, 'quantity': 1, 'unitPrice': Decimal('20')}], 'paymentMethod': 'cash',
                'discount': Decimal('0'), 'amountPaid': Decimal('20')}
        sale, replayed = create_completed_sale(business=self.business, user=self.owner, data=data, idempotency_key='sms-sale', branch=self.branch)
        self.assertEqual(OwnerSms.objects.filter(event_type='sale').count(), 1)
        sale.save()
        again, replayed = create_completed_sale(business=self.business, user=self.owner, data=data, idempotency_key='sms-sale', branch=self.branch)
        self.assertTrue(replayed)
        self.assertEqual(again.pk, sale.pk)
        self.assertEqual(OwnerSms.objects.filter(event_type='sale').count(), 1)
        self.assertIn('20.00', OwnerSms.objects.get(event_type='sale').message)

    def test_pending_payment_does_not_alert_until_completed(self):
        sale = Sale.objects.create(business=self.business, branch=self.branch, sale_number='S1', invoice_number='I1',
            idempotency_key='pending-1', payment_method='mobile_money', cashier=self.owner,
            subtotal=20, total=20, outstanding_balance=20)
        self.assertFalse(OwnerSms.objects.exists())
        sale.status='completed'; sale.completed_at=timezone.now(); sale.amount_paid=20; sale.outstanding_balance=0
        sale.save(update_fields=['status','completed_at','amount_paid','outstanding_balance','updated_at'])
        sale.save()
        self.assertEqual(OwnerSms.objects.filter(event_type='sale').count(), 1)

    def test_old_sale_not_replayed_after_opt_in(self):
        self.pref.enabled=False; self.pref.save()
        sale = Sale.objects.create(business=self.business, sale_number='S2', invoice_number='I2',
            idempotency_key='old', payment_method='cash', cashier=self.owner, subtotal=20, total=20,
            amount_paid=20, status='completed', completed_at=timezone.now())
        self.pref.enabled=True; self.pref.save()
        sale.save()
        self.assertFalse(OwnerSms.objects.exists())

    def test_provider_acceptance_and_duplicate_worker_pass(self):
        self.alert(); self.alert()
        with patch('owner_alerts.services.MNotifySmsProvider.send', return_value={'provider_reference':'ok'}) as send:
            process_pending(); process_pending()
        send.assert_called_once()
        self.assertEqual(OwnerSms.objects.get().status, 'sent')

    def test_ambiguous_failure_is_not_automatically_resent(self):
        self.alert()
        with patch('owner_alerts.services.MNotifySmsProvider.send', side_effect=TimeoutError) as send:
            process_pending(); process_pending()
        send.assert_called_once()
        self.assertEqual(OwnerSms.objects.get().status, 'unknown')

    def test_disabled_or_changed_recipient_cancels_pending(self):
        self.alert()
        self.pref.phone='0244111111'; self.pref.save()
        with patch('owner_alerts.services.MNotifySmsProvider.send') as send:
            process_pending()
        send.assert_not_called()
        self.assertEqual(OwnerSms.objects.get().status, 'cancelled')

    def test_owner_transfer_cancels_pending(self):
        self.alert()
        self.business.owner=self.other; self.business.save()
        with patch('owner_alerts.services.MNotifySmsProvider.send') as send:
            process_pending()
        send.assert_not_called()
        self.assertIsNone(self.alert('2'))

    def test_manager_and_other_business_cannot_change_owner_sms(self):
        BusinessMembership.objects.create(business=self.business, user=self.other, role='manager')
        self.client.force_authenticate(self.other)
        for suffix, method, data in [('', 'get', None), ('', 'patch', {'enabled':False,'eventTypes':[]}),
                                    ('request-code/', 'post', {'phone':'0244000000'}), ('verify-code/', 'post', {'code':'123456'})]:
            response = getattr(self.client, method)(self.url+suffix, data, format='json')
            self.assertEqual(response.status_code, 404)

    def test_verification_required_and_phone_normalized(self):
        self.pref.verified_at=None; self.pref.enabled=False; self.pref.save()
        response=self.client.patch(self.url, {'enabled':True,'eventTypes':['sale']}, format='json')
        self.assertEqual(response.status_code, 400)
        with patch('owner_alerts.views.secrets.randbelow', return_value=123456):
            response=self.client.post(self.url+'request-code/', {'phone':'+233244000000'}, format='json')
        self.assertEqual(response.status_code, 202)
        self.pref.refresh_from_db()
        self.assertEqual(self.pref.pending_phone, '0244000000')
        self.assertNotIn('123456', self.pref.code_hash)
        with patch('owner_alerts.services.MNotifySmsProvider.send', return_value={}):
            process_pending()
        self.assertEqual(OwnerSms.objects.get().message, '')
        response=self.client.post(self.url+'verify-code/', {'code':'123456'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['verified'])
        self.assertEqual(self.client.patch(self.url, {'enabled':True,'eventTypes':['sale']}, format='json').status_code,200)
        self.assertEqual(self.client.post(self.url+'verify-code/', {'code':'123456'}, format='json').status_code,400)

    def test_code_request_rate_limit_and_invalid_number(self):
        self.assertEqual(self.client.post(self.url+'request-code/', {'phone':'123'}, format='json').status_code,400)
        self.assertEqual(self.client.post(self.url+'request-code/', {'phone':'0244000000'}, format='json').status_code,202)
        self.assertEqual(self.client.post(self.url+'request-code/', {'phone':'0244000001'}, format='json').status_code,429)

    def test_code_attempt_limit_and_expiry(self):
        self.pref.code_hash=make_password('123456'); self.pref.pending_phone='0244000001'
        self.pref.code_expires_at=timezone.now()+timedelta(minutes=10); self.pref.save()
        for _ in range(5):
            self.assertEqual(self.client.post(self.url+'verify-code/', {'code':'000000'}, format='json').status_code,400)
        self.assertEqual(self.client.post(self.url+'verify-code/', {'code':'123456'}, format='json').status_code,400)
        self.pref.refresh_from_db(); self.pref.code_attempts=0; self.pref.code_expires_at=timezone.now()-timedelta(seconds=1); self.pref.save()
        self.assertEqual(self.client.post(self.url+'verify-code/', {'code':'123456'}, format='json').status_code,400)

    def test_security_alert_is_tenant_scoped_and_limited(self):
        for _ in range(5):
            PlatformEvent.objects.create(category='security', action='request.denied', summary='Denied', http_status=403, business_id=str(self.business.pk))
        PlatformEvent.objects.create(category='security', action='request.denied', summary='Global denied', http_status=403)
        self.assertEqual(OwnerSms.objects.filter(event_type='security').count(),1)

    def test_repeated_login_failure_alert_unknown_email_ignored(self):
        for _ in range(4):
            authenticate(email=self.owner.email, password='wrong')
        self.assertFalse(OwnerSms.objects.exists())
        authenticate(email=self.owner.email,password='wrong')
        self.assertEqual(OwnerSms.objects.filter(event_type='security').count(),1)
        for _ in range(6):
            authenticate(email='unknown@example.com',password='wrong')
        self.assertEqual(OwnerSms.objects.filter(event_type='security').count(),1)

    def test_preference_filter_and_unverified_no_alert(self):
        self.pref.event_types=['restock']; self.pref.save()
        self.assertIsNone(self.alert())
        self.pref.verified_at=None; self.pref.save()
        self.assertIsNone(self.alert(kind='restock'))

    def test_stale_and_in_progress_not_resent(self):
        item=self.alert()
        OwnerSms.objects.filter(pk=item.pk).update(status='sending', attempted_at=timezone.now()-timedelta(minutes=11))
        with patch('owner_alerts.services.MNotifySmsProvider.send') as send:
            process_pending()
        send.assert_not_called()
        item.refresh_from_db(); self.assertEqual(item.status,'unknown')

    @override_settings(MNOTIFY_API_KEY='')
    def test_unconfigured_provider_leaves_queue_pending(self):
        self.alert()
        with patch('owner_alerts.services.MNotifySmsProvider.send') as send:
            self.assertFalse(process_pending()['configured'])
        send.assert_not_called()
        self.assertEqual(OwnerSms.objects.get().status,'pending')

    def test_overlapping_worker_cannot_claim_in_flight_message(self):
        self.alert()
        def nested_worker(**kwargs):
            process_pending()
            return {}
        with patch('owner_alerts.services.MNotifySmsProvider.send', side_effect=nested_worker) as send:
            process_pending()
        send.assert_called_once()

    def test_pausing_cancels_queued_messages(self):
        self.alert()
        response=self.client.patch(self.url, {'enabled':False,'eventTypes':['sale']}, format='json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(OwnerSms.objects.get().status,'cancelled')

    def test_provider_diagnostics_and_verification_sms_hidden_from_history(self):
        self.client.post(self.url+'request-code/', {'phone':'0244000000'}, format='json')
        response=self.client.get(self.url)
        self.assertEqual(response.data['recent'],[])
        self.assertNotIn('code_hash',response.data)

    def test_cancelled_payment_has_no_sale_sms(self):
        sale=Sale.objects.create(business=self.business, sale_number='C1', invoice_number='CI1',
            idempotency_key='cancelled', payment_method='mobile_money', cashier=self.owner,
            subtotal=20, total=20, outstanding_balance=20)
        sale.status='cancelled'; sale.save()
        self.assertFalse(OwnerSms.objects.exists())
