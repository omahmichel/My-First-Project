from decimal import Decimal
from unittest.mock import Mock
from django.test import SimpleTestCase, TestCase, override_settings
from businesses.payment_fees import customer_payment_fee, payment_fee, CUSTOMER_FEE_PERCENT, SUBSCRIPTION_FEE_PERCENT
from businesses.models import SubscriptionPayment
from businesses.subscription_service import verify_and_fulfill_subscription_payment, SubscriptionPaymentError
from businesses import test_subscription_service as subscription_helpers
from sales import test_mobile_money_service as sale_helpers
from sales.mobile_money_service import initialize_mobile_money_sale, verify_and_finalize_mobile_money_sale, MobileMoneyPaymentError
from sales.models import MerchantPayout
from sales.serializers import PaymentSerializer

class FeeRoundingTests(SimpleTestCase):
    def test_approved_rates_and_half_pesewa_rounding(self):
        self.assertEqual(payment_fee(Decimal('99'), SUBSCRIPTION_FEE_PERCENT), Decimal('2.48'))
        self.assertEqual(payment_fee(Decimal('100'), CUSTOMER_FEE_PERCENT), Decimal('1.30'))
        self.assertEqual(payment_fee(Decimal('5.00'), CUSTOMER_FEE_PERCENT), Decimal('0.07'))
        self.assertEqual(payment_fee(Decimal('0.01'), CUSTOMER_FEE_PERCENT), Decimal('0.00'))

    def test_customer_example_220(self):
        self.assertEqual(payment_fee(Decimal('220'), CUSTOMER_FEE_PERCENT), Decimal('2.86'))

    def test_cap_and_rounding_boundaries(self):
        cases = [('220','2.86'), ('1000','13.00'), ('1538.07','19.99'),
                 ('1538.08','20.00'), ('1538.46','20.00'), ('1538.47','20.00'),
                 ('2000','20.00'), ('10000','20.00')]
        for amount, fee in cases:
            with self.subTest(amount=amount):
                self.assertEqual(customer_payment_fee(Decimal(amount)), Decimal(fee))
        self.assertEqual(payment_fee(Decimal('2000'), SUBSCRIPTION_FEE_PERCENT), Decimal('50.00'))

@override_settings(PAYMENT_GATEWAY="paystack", PAYMENT_GATEWAY_SECRET_KEY="sk_test_stockflow")
class SubscriptionFeeTests(TestCase):
    setUp = subscription_helpers.SubscriptionPaymentServiceTests.setUp
    initialize_payment = subscription_helpers.SubscriptionPaymentServiceTests.initialize_payment
    mock_manager_create = subscription_helpers.SubscriptionPaymentServiceTests.mock_manager_create
    successful_verification = subscription_helpers.SubscriptionPaymentServiceTests.successful_verification

    def test_new_checkout_snapshots_fee_and_sends_gross_total(self):
        p = self.initialize_payment()
        self.assertEqual((p.amount,p.fee_amount,p.charged_amount), (Decimal('150'),Decimal('3.75'),Decimal('153.75')))
        self.assertEqual(self.client.initialize_transaction.call_args.kwargs['amount_subunit'],15375)

    def test_base_only_payment_cannot_activate_subscription(self):
        p = self.initialize_payment()
        self.client.verify_transaction.return_value=self.successful_verification(p,amount=15000)
        with self.assertRaises(SubscriptionPaymentError):
            verify_and_fulfill_subscription_payment(reference=p.reference,client=self.client)
        p.refresh_from_db()
        self.assertIsNone(p.fulfilled_at)

    def test_existing_fee_free_attempt_still_verifies_at_original_amount(self):
        p=SubscriptionPayment.objects.create(amount=Decimal("99.00"), amount_subunit=9900, business=self.business,initiated_by=self.owner,initiated_by_email=self.owner.email,initiated_by_name=self.owner.full_name)
        self.assertEqual(p.fee_amount,Decimal('0'))
        self.client.verify_transaction.return_value=self.successful_verification(p)
        p,_,activated=verify_and_fulfill_subscription_payment(reference=p.reference,client=self.client)
        self.assertTrue(activated)
        self.assertEqual(p.amount_subunit,9900)

    def test_previous_99_plus_fee_checkout_keeps_its_terms(self):
        p=SubscriptionPayment.objects.create(amount=Decimal("99.00"), amount_subunit=10148,
            fee_percent=Decimal("2.50"), fee_amount=Decimal("2.48"), business=self.business,
            initiated_by=self.owner, initiated_by_email=self.owner.email, initiated_by_name=self.owner.full_name)
        self.client.verify_transaction.return_value=self.successful_verification(p)
        p,_,activated=verify_and_fulfill_subscription_payment(reference=p.reference,client=self.client)
        self.assertTrue(activated)
        self.assertEqual(p.charged_amount, Decimal("101.48"))

@override_settings(PAYMENT_GATEWAY="paystack", PAYMENT_GATEWAY_SECRET_KEY="sk_test_stockflow")
class CustomerFeeTests(TestCase):
    setUp = sale_helpers.MobileMoneySaleInitializationTests.setUp
    payload = sale_helpers.MobileMoneySaleInitializationTests.payload
    successful_client = sale_helpers.MobileMoneySaleInitializationTests.successful_client
    verification_client = sale_helpers.MobileMoneySaleInitializationTests.verification_client

    def start(self,key):
        return initialize_mobile_money_sale(business=self.business,user=self.owner,data=self.payload(),idempotency_key=key,client=self.successful_client())

    def test_fee_is_not_business_income_and_payout_is_full_and_once(self):
        sale,p,_=self.start('fee-payout')
        self.assertEqual(p.fee_amount,Decimal('1.95'))
        self.assertEqual(p.charged_amount,Decimal('151.95'))
        client=self.verification_client(payment=p)
        verify_and_finalize_mobile_money_sale(reference=p.gateway_reference,client=client)
        verify_and_finalize_mobile_money_sale(reference=p.gateway_reference,client=client)
        sale.refresh_from_db()
        self.assertEqual(sale.amount_paid,Decimal('150'))
        self.assertEqual(sale.outstanding_balance,Decimal('0'))
        payouts=MerchantPayout.objects.filter(payment=p)
        self.assertEqual(payouts.count(),1)
        self.assertEqual(payouts.get().amount,Decimal('150'))
        data=PaymentSerializer(p).data
        self.assertEqual(data['feeAmount'],'1.95')
        self.assertEqual(data['chargedAmount'],'151.95')

    def test_base_only_verification_rejected(self):
        sale,p,_=self.start('fee-underpayment')
        with self.assertRaises(MobileMoneyPaymentError):
            verify_and_finalize_mobile_money_sale(reference=p.gateway_reference,client=self.verification_client(payment=p,amount=15000))
        self.assertFalse(MerchantPayout.objects.filter(payment=p).exists())

    def test_existing_two_percent_attempt_keeps_its_original_total(self):
        _,payment,_ = self.start('old-fee-attempt')
        # Simulates a pending record created before this rate change.
        payment.fee_percent = Decimal('2.00')
        payment.fee_amount = Decimal('3.00')
        payment.save(update_fields=['fee_percent', 'fee_amount'])
        _,replayed_payment,replayed = self.start('old-fee-attempt')
        self.assertTrue(replayed)
        self.assertEqual(replayed_payment.charged_amount, Decimal('153.00'))
        verify_and_finalize_mobile_money_sale(reference=payment.gateway_reference,
            client=self.verification_client(payment=payment, amount=15300))
        self.assertEqual(MerchantPayout.objects.get(payment=payment).amount, Decimal('150.00'))

    def test_capped_charge_and_full_business_payout(self):
        data=self.payload()
        data['items'][0]['unitPrice']=Decimal('2000.00')
        data['amountPaid']=Decimal('2000.00')
        client=self.successful_client()
        sale,p,_=initialize_mobile_money_sale(business=self.business,user=self.owner,
            data=data,idempotency_key='capped-large-sale',client=client)
        self.assertEqual(p.fee_amount,Decimal('20.00'))
        self.assertEqual(client.create_mobile_money_charge.call_args.kwargs['amount_subunit'],202000)
        verify_and_finalize_mobile_money_sale(reference=p.gateway_reference,
            client=self.verification_client(payment=p,amount=202000))
        self.assertEqual(MerchantPayout.objects.get(payment=p).amount,Decimal('2000.00'))

    def test_existing_uncapped_attempt_keeps_stored_fee(self):
        _,p,_=self.start('old-uncapped')
        p.amount=Decimal('2000.00')
        p.fee_amount=Decimal('26.00')
        p.save(update_fields=['amount','fee_amount'])
        _,old,replayed=self.start('old-uncapped')
        self.assertTrue(replayed)
        self.assertEqual(old.charged_amount,Decimal('2026.00'))

    def test_replay_does_not_add_fee_again(self):
        _,first,_=self.start('fee-replay')
        _,second,replayed=self.start('fee-replay')
        self.assertTrue(replayed)
        self.assertEqual(first.pk,second.pk)
        self.assertEqual(second.charged_amount,Decimal('151.95'))
