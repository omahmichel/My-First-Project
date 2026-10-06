from unittest.mock import Mock
from django.test import TestCase, override_settings
from . import test_mobile_money_service as sale_fixtures
from .mobile_money_service import initialize_mobile_money_sale,verify_and_finalize_mobile_money_sale
from .merchant_payout_service import process_merchant_payout,handle_paystack_transfer_webhook
from .models import MerchantPayout
from businesses.paystack_client import PaystackConfigurationError

@override_settings(PAYMENT_GATEWAY_SECRET_KEY='sk_test_stockflow',PAYMENT_GATEWAY='paystack')
class SalePaymentModeTests(TestCase):
    setUp=sale_fixtures.MobileMoneySaleInitializationTests.setUp
    payload=sale_fixtures.MobileMoneySaleInitializationTests.payload
    successful_client=sale_fixtures.MobileMoneySaleInitializationTests.successful_client
    verification_client=sale_fixtures.MobileMoneySaleInitializationTests.verification_client

    def payment(self):
        return initialize_mobile_money_sale(business=self.business,user=self.owner,data=self.payload(),idempotency_key='mode-test',client=self.successful_client())[1]

    def test_new_sale_stores_mode(self):
        self.assertEqual(self.payment().gateway_mode,'test')

    def test_test_sale_cannot_be_verified_using_live_key(self):
        p=self.payment();client=self.verification_client(payment=p)
        with override_settings(PAYMENT_GATEWAY_SECRET_KEY='sk_live_isolated'):
            with self.assertRaises(PaystackConfigurationError):verify_and_finalize_mobile_money_sale(reference=p.gateway_reference,client=client)
        client.verify_transaction.assert_not_called()

    def test_test_payout_cannot_initiate_live_transfer(self):
        p=self.payment()
        verify_and_finalize_mobile_money_sale(reference=p.gateway_reference,client=self.verification_client(payment=p))
        payout=MerchantPayout.objects.get(payment=p);client=Mock()
        with override_settings(PAYMENT_GATEWAY_SECRET_KEY='sk_live_isolated'):
            result=process_merchant_payout(payout.id,client=client)
        self.assertEqual(result.status,MerchantPayout.Status.BLOCKED)
        client.initiate_transfer.assert_not_called();client.verify_transfer.assert_not_called();client.create_transfer_recipient.assert_not_called()

    def test_wrong_mode_webhook_cannot_mark_transfer_successful(self):
        p=self.payment()
        verify_and_finalize_mobile_money_sale(reference=p.gateway_reference,client=self.verification_client(payment=p))
        payout=MerchantPayout.objects.get(payment=p)
        self.assertFalse(handle_paystack_transfer_webhook(event_name='transfer.success',event_data={'reference':payout.reference,'domain':'live'}))
        payout.refresh_from_db();self.assertNotEqual(payout.status,MerchantPayout.Status.SUCCESSFUL)

    def test_live_payout_resyncs_old_recipient_before_transfer(self):
        from unittest.mock import patch
        from businesses.models import BusinessPaymentAccount
        from businesses.paystack_client import PaystackRequestError
        account=BusinessPaymentAccount.objects.create(business=self.business,account_type='mobile_money',display_name='Wallet',account_name='Test Owner',network='mtn',encrypted_account_number='test-only',account_last_four='4987',is_active=True,is_default=True,paystack_recipient_code='RCP_old_test',paystack_recipient_mode='test')
        with override_settings(PAYMENT_GATEWAY_SECRET_KEY='sk_live_isolated'):
            p=self.payment()
            verify=self.verification_client(payment=p)
            verify.verify_transaction.return_value['domain']='live'
            verify_and_finalize_mobile_money_sale(reference=p.gateway_reference,client=verify)
            payout=MerchantPayout.objects.get(payment=p)
            client=Mock()
            client.create_transfer_recipient.return_value={'domain':'live','recipient_code':'RCP_new_live','id':321}
            client.verify_transfer.side_effect=PaystackRequestError('Not found',status_code=404)
            client.initiate_transfer.return_value={'domain':'live','status':'pending','transfer_code':'TRF_live'}
            with patch.object(BusinessPaymentAccount,'get_account_number',return_value='0551234987'):
                result=process_merchant_payout(payout.id,client=client)
            self.assertEqual(result.status,MerchantPayout.Status.PROCESSING)
            self.assertEqual(client.initiate_transfer.call_args.kwargs['recipient_code'],'RCP_new_live')
            self.assertEqual(client.initiate_transfer.call_args.kwargs['amount_subunit'],15000)
            account.refresh_from_db();self.assertEqual(account.paystack_recipient_mode,'live')
