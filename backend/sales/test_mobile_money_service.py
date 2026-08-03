from datetime import timedelta
from decimal import Decimal
from unittest.mock import ANY, Mock

from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from businesses.models import Business
from businesses.paystack_client import PaystackRequestError
from customers.models import Customer
from inventory.models import Product, StockMovement

from .mobile_money_service import (
    MobileMoneyPaymentError,
    initialize_mobile_money_debt_payment,
    initialize_mobile_money_sale,
    verify_and_finalize_mobile_money_debt_payment,
    verify_and_finalize_mobile_money_sale,
)
from .models import Payment, Sale


@override_settings(
    PAYMENT_GATEWAY="paystack",
    PAYMENT_GATEWAY_SECRET_KEY="sk_test_stockflow",
    MOBILE_MONEY_RESERVATION_MINUTES=5,
)
class MobileMoneySaleInitializationTests(TestCase):
    """Protects pending sales, stock reservations and gateway prompts."""

    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner.momo@stockflow.test",
            password="StrongPass123!",
            full_name="Mobile Money Owner",
        )
        self.business = Business.objects.create(
            owner=self.owner,
            name="Mobile Money Test Shop",
            slug="mobile-money-test-shop",
            business_type="building_materials",
            email="shop@stockflow.test",
            invoice_prefix="INV",
            receipt_prefix="RCT",
        )
        self.product = Product.objects.create(
            business=self.business,
            name="Premium Floor Tile",
            sku="TILE-MOMO-01",
            category="Tiles",
            unit="box",
            stock=10,
            reserved_stock=0,
            cost_price=Decimal("100.00"),
            selling_price=Decimal("150.00"),
        )
        self.customer = Customer.objects.create(
            business=self.business,
            name="Ama Mobile",
            phone="0241234567",
            email="ama.mobile@example.com",
            created_by=self.owner,
        )

    def payload(self):
        # Returns one full GHS 150 Mobile Money checkout.
        return {
            "items": [
                {
                    "productId": self.product.id,
                    "quantity": 1,
                    "unitPrice": Decimal("150.00"),
                }
            ],
            "customerId": self.customer.id,
            "discount": Decimal("0.00"),
            "amountPaid": Decimal("150.00"),
            "paymentMethod": "mobile_money",
            "amountPaidMethod": "",
            "mobileMoneyNetwork": "mtn",
            "mobileMoneyNumber": "0241234567",
        }

    def successful_client(self):
        # Returns one deterministic Paystack prompt response.
        client = Mock()
        client.create_mobile_money_charge.return_value = {
            "reference": "ignored-by-mock-assertion",
            "status": "pay_offline",
            "display_text": "Approve the payment on your phone.",
        }

        def response_with_reference(**kwargs):
            return {
                "reference": kwargs["reference"],
                "status": "pay_offline",
                "display_text": "Approve the payment on your phone.",
            }

        client.create_mobile_money_charge.side_effect = (
            response_with_reference
        )
        return client

    def test_initialization_reserves_stock_without_completing_sale(self):
        # No stock, receipt or customer balance changes before verification.
        client = self.successful_client()
        before = timezone.now()

        sale, payment, replayed = initialize_mobile_money_sale(
            business=self.business,
            user=self.owner,
            data=self.payload(),
            idempotency_key="momo-sale-001",
            client=client,
        )

        self.assertFalse(replayed)
        self.assertEqual(sale.status, Sale.Status.PENDING_PAYMENT)
        self.assertEqual(sale.amount_paid, Decimal("0.00"))
        self.assertEqual(sale.outstanding_balance, Decimal("150.00"))
        self.assertGreaterEqual(
            sale.reservation_expires_at,
            before + timedelta(minutes=5),
        )
        self.assertLessEqual(
            sale.reservation_expires_at,
            timezone.now() + timedelta(minutes=5),
        )

        self.product.refresh_from_db()
        self.customer.refresh_from_db()
        self.assertEqual(self.product.stock, 10)
        self.assertEqual(self.product.reserved_stock, 1)
        self.assertEqual(
            self.customer.outstanding_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.customer.total_purchases,
            Decimal("0.00"),
        )
        self.assertEqual(StockMovement.objects.count(), 0)

        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertEqual(payment.amount, Decimal("150.00"))
        self.assertEqual(payment.gateway, "paystack")
        self.assertTrue(
            payment.gateway_reference.startswith("STF-SALE-")
        )
        self.assertEqual(payment.receipt_number, "")
        self.assertEqual(
            payment.note,
            "Approve the payment on your phone.",
        )

        client.create_mobile_money_charge.assert_called_once_with(
            email="ama.mobile@example.com",
            amount_subunit=15000,
            reference=payment.gateway_reference,
            phone="0241234567",
            provider="mtn",
            currency="GHS",
            metadata={
                "business_id": str(self.business.id),
                "sale_id": str(sale.id),
                "payment_id": str(payment.id),
                "payment_type": Payment.PaymentType.SALE_PAYMENT,
            },
        )

    def test_idempotent_replay_does_not_send_second_prompt(self):
        # Retrying the same checkout cannot reserve or charge twice.
        first_client = self.successful_client()
        first_sale, first_payment, _ = initialize_mobile_money_sale(
            business=self.business,
            user=self.owner,
            data=self.payload(),
            idempotency_key="momo-sale-replay",
            client=first_client,
        )
        second_client = Mock()

        sale, payment, replayed = initialize_mobile_money_sale(
            business=self.business,
            user=self.owner,
            data=self.payload(),
            idempotency_key="momo-sale-replay",
            client=second_client,
        )

        self.assertTrue(replayed)
        self.assertEqual(sale.id, first_sale.id)
        self.assertEqual(payment.id, first_payment.id)
        second_client.create_mobile_money_charge.assert_not_called()

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)
        self.assertEqual(self.product.reserved_stock, 1)
        self.assertEqual(Sale.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 1)

    def test_definitive_gateway_rejection_releases_stock(self):
        # A rejected request leaves an audit trail but no stock hold.
        client = Mock()
        client.create_mobile_money_charge.side_effect = (
            PaystackRequestError(
                "The charge request was rejected.",
                code="paystack_request_rejected",
                status_code=400,
            )
        )

        with self.assertRaises(PaystackRequestError):
            initialize_mobile_money_sale(
                business=self.business,
                user=self.owner,
                data=self.payload(),
                idempotency_key="momo-sale-rejected",
                client=client,
            )

        self.product.refresh_from_db()
        sale = Sale.objects.get(
            idempotency_key="momo-sale-rejected"
        )
        payment = Payment.objects.get(sale=sale)

        self.assertEqual(self.product.stock, 10)
        self.assertEqual(self.product.reserved_stock, 0)
        self.assertEqual(sale.status, Sale.Status.FAILED)
        self.assertIsNone(sale.reservation_expires_at)
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_uncertain_timeout_keeps_reservation_for_verification(self):
        # A timeout may still produce a Paystack charge and must stay safe.
        client = Mock()
        client.create_mobile_money_charge.side_effect = (
            PaystackRequestError(
                "Paystack did not respond in time.",
                code="paystack_timeout",
            )
        )

        with self.assertRaises(PaystackRequestError):
            initialize_mobile_money_sale(
                business=self.business,
                user=self.owner,
                data=self.payload(),
                idempotency_key="momo-sale-timeout",
                client=client,
            )

        self.product.refresh_from_db()
        sale = Sale.objects.get(
            idempotency_key="momo-sale-timeout"
        )
        payment = Payment.objects.get(sale=sale)

        self.assertEqual(self.product.stock, 10)
        self.assertEqual(self.product.reserved_stock, 1)
        self.assertEqual(
            sale.status,
            Sale.Status.PENDING_PAYMENT,
        )
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertIn(
            "Verify this payment before retrying.",
            payment.note,
        )
        self.assertEqual(StockMovement.objects.count(), 0)

    def verification_client(
        self,
        *,
        payment,
        status="success",
        amount=15000,
        transaction_id=900001,
    ):
        # Returns a deterministic server-side Paystack verification.
        client = Mock()
        client.verify_transaction.return_value = {
            "id": transaction_id,
            "status": status,
            "reference": payment.gateway_reference,
            "amount": amount,
            "currency": "GHS",
            "channel": "mobile_money",
        }
        return client

    def test_successful_verification_finalizes_sale_once(self):
        # Verified money deducts stock and creates one receipt and movement.
        sale, payment, _ = initialize_mobile_money_sale(
            business=self.business,
            user=self.owner,
            data=self.payload(),
            idempotency_key="momo-verify-success",
            client=self.successful_client(),
        )
        client = self.verification_client(payment=payment)

        verified_payment, verified_sale, fulfilled = (
            verify_and_finalize_mobile_money_sale(
                reference=payment.gateway_reference,
                client=client,
            )
        )

        self.assertTrue(fulfilled)
        self.assertEqual(
            verified_payment.status,
            Payment.Status.SUCCESSFUL,
        )
        self.assertEqual(
            verified_payment.provider_reference,
            "900001",
        )
        self.assertEqual(
            verified_payment.receipt_number,
            "RCT-00001",
        )
        self.assertIsNotNone(verified_payment.verified_at)
        self.assertEqual(
            verified_sale.status,
            Sale.Status.COMPLETED,
        )
        self.assertEqual(
            verified_sale.amount_paid,
            Decimal("150.00"),
        )
        self.assertEqual(
            verified_sale.outstanding_balance,
            Decimal("0.00"),
        )
        self.assertIsNone(verified_sale.reservation_expires_at)
        self.assertIsNotNone(verified_sale.completed_at)

        self.product.refresh_from_db()
        self.customer.refresh_from_db()
        self.assertEqual(self.product.stock, 9)
        self.assertEqual(self.product.reserved_stock, 0)
        self.assertEqual(
            self.customer.total_purchases,
            Decimal("150.00"),
        )
        self.assertEqual(
            self.customer.outstanding_balance,
            Decimal("0.00"),
        )

        movement = StockMovement.objects.get()
        self.assertEqual(movement.quantity, -1)
        self.assertEqual(movement.previous_stock, 10)
        self.assertEqual(movement.new_stock, 9)
        client.verify_transaction.assert_called_once_with(
            payment.gateway_reference
        )

    def test_duplicate_success_verification_delivers_nothing_twice(self):
        # A callback and webhook cannot create duplicate financial changes.
        sale, payment, _ = initialize_mobile_money_sale(
            business=self.business,
            user=self.owner,
            data=self.payload(),
            idempotency_key="momo-verify-replay",
            client=self.successful_client(),
        )
        first_client = self.verification_client(payment=payment)
        verify_and_finalize_mobile_money_sale(
            reference=payment.gateway_reference,
            client=first_client,
        )
        second_client = Mock()

        replay_payment, replay_sale, fulfilled = (
            verify_and_finalize_mobile_money_sale(
                reference=payment.gateway_reference,
                client=second_client,
            )
        )

        self.assertFalse(fulfilled)
        self.assertEqual(replay_payment.id, payment.id)
        self.assertEqual(replay_sale.id, sale.id)
        second_client.verify_transaction.assert_not_called()

        self.product.refresh_from_db()
        self.customer.refresh_from_db()
        self.assertEqual(self.product.stock, 9)
        self.assertEqual(self.product.reserved_stock, 0)
        self.assertEqual(
            self.customer.total_purchases,
            Decimal("150.00"),
        )
        self.assertEqual(StockMovement.objects.count(), 1)
        self.assertEqual(
            Payment.objects.exclude(receipt_number="").count(),
            1,
        )

    def test_pending_verification_keeps_stock_reserved(self):
        # A non-final Paystack state cannot deliver or release the sale.
        sale, payment, _ = initialize_mobile_money_sale(
            business=self.business,
            user=self.owner,
            data=self.payload(),
            idempotency_key="momo-verify-pending",
            client=self.successful_client(),
        )
        client = self.verification_client(
            payment=payment,
            status="pending",
        )

        with self.assertRaisesRegex(
            MobileMoneyPaymentError,
            "still pending",
        ):
            verify_and_finalize_mobile_money_sale(
                reference=payment.gateway_reference,
                client=client,
            )

        self.product.refresh_from_db()
        self.customer.refresh_from_db()
        sale.refresh_from_db()
        payment.refresh_from_db()

        self.assertEqual(self.product.stock, 10)
        self.assertEqual(self.product.reserved_stock, 1)
        self.assertEqual(sale.status, Sale.Status.PENDING_PAYMENT)
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertEqual(StockMovement.objects.count(), 0)
        self.assertEqual(
            self.customer.total_purchases,
            Decimal("0.00"),
        )

    def test_terminal_failure_releases_reserved_stock(self):
        # A final failed gateway state frees stock without creating value.
        sale, payment, _ = initialize_mobile_money_sale(
            business=self.business,
            user=self.owner,
            data=self.payload(),
            idempotency_key="momo-verify-failed",
            client=self.successful_client(),
        )
        client = self.verification_client(
            payment=payment,
            status="failed",
        )

        with self.assertRaises(MobileMoneyPaymentError):
            verify_and_finalize_mobile_money_sale(
                reference=payment.gateway_reference,
                client=client,
            )

        self.product.refresh_from_db()
        self.customer.refresh_from_db()
        sale.refresh_from_db()
        payment.refresh_from_db()

        self.assertEqual(self.product.stock, 10)
        self.assertEqual(self.product.reserved_stock, 0)
        self.assertEqual(sale.status, Sale.Status.FAILED)
        self.assertIsNone(sale.reservation_expires_at)
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertEqual(StockMovement.objects.count(), 0)
        self.assertEqual(
            self.customer.total_purchases,
            Decimal("0.00"),
        )

    def test_wrong_verified_amount_is_rejected_and_released(self):
        # Paid value must match the server-controlled payment amount.
        sale, payment, _ = initialize_mobile_money_sale(
            business=self.business,
            user=self.owner,
            data=self.payload(),
            idempotency_key="momo-verify-mismatch",
            client=self.successful_client(),
        )
        client = self.verification_client(
            payment=payment,
            amount=14900,
        )

        with self.assertRaisesRegex(
            MobileMoneyPaymentError,
            "did not match",
        ):
            verify_and_finalize_mobile_money_sale(
                reference=payment.gateway_reference,
                client=client,
            )

        self.product.refresh_from_db()
        sale.refresh_from_db()
        payment.refresh_from_db()

        self.assertEqual(self.product.stock, 10)
        self.assertEqual(self.product.reserved_stock, 0)
        self.assertEqual(sale.status, Sale.Status.FAILED)
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertEqual(payment.receipt_number, "")
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_verified_part_payment_creates_customer_debt(self):
        # A verified credit deposit records the sale and remaining balance.
        data = self.payload()
        data["paymentMethod"] = Sale.PaymentMethod.CREDIT
        data["amountPaidMethod"] = Payment.Method.MOBILE_MONEY
        data["amountPaid"] = Decimal("50.00")

        sale, payment, _ = initialize_mobile_money_sale(
            business=self.business,
            user=self.owner,
            data=data,
            idempotency_key="momo-verify-part-payment",
            client=self.successful_client(),
        )
        client = self.verification_client(
            payment=payment,
            amount=5000,
            transaction_id=900002,
        )

        verified_payment, verified_sale, fulfilled = (
            verify_and_finalize_mobile_money_sale(
                reference=payment.gateway_reference,
                client=client,
            )
        )

        self.assertTrue(fulfilled)
        self.assertEqual(
            verified_payment.amount,
            Decimal("50.00"),
        )
        self.assertEqual(
            verified_sale.status,
            Sale.Status.PARTIALLY_PAID,
        )
        self.assertEqual(
            verified_sale.amount_paid,
            Decimal("50.00"),
        )
        self.assertEqual(
            verified_sale.outstanding_balance,
            Decimal("100.00"),
        )

        self.product.refresh_from_db()
        self.customer.refresh_from_db()
        self.assertEqual(self.product.stock, 9)
        self.assertEqual(self.product.reserved_stock, 0)
        self.assertEqual(
            self.customer.total_purchases,
            Decimal("150.00"),
        )
        self.assertEqual(
            self.customer.outstanding_balance,
            Decimal("100.00"),
        )
        self.assertEqual(StockMovement.objects.count(), 1)

@override_settings(
    PAYMENT_GATEWAY="paystack",
    PAYMENT_GATEWAY_SECRET_KEY="sk_test_stockflow",
)
class MobileMoneyDebtPaymentTests(TestCase):
    """Protects pending customer debt payments and verified settlement."""

    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner.debt.momo@stockflow.test",
            password="StrongPass123!",
            full_name="Debt Mobile Money Owner",
        )
        self.business = Business.objects.create(
            owner=self.owner,
            name="Debt Mobile Money Test Shop",
            slug="debt-mobile-money-test-shop",
            business_type="building_materials",
            email="debt.shop@stockflow.test",
            invoice_prefix="INV",
            receipt_prefix="RCT",
        )
        self.customer = Customer.objects.create(
            business=self.business,
            name="Ama Debt",
            phone="0241234567",
            email="ama.debt@example.com",
            outstanding_balance=Decimal("100.00"),
            total_purchases=Decimal("140.00"),
            created_by=self.owner,
        )
        self.sale = Sale.objects.create(
            business=self.business,
            customer=self.customer,
            sale_number="SAL-00001",
            invoice_number="INV-00001",
            payment_method=Sale.PaymentMethod.CREDIT,
            status=Sale.Status.PARTIALLY_PAID,
            subtotal=Decimal("150.00"),
            discount=Decimal("10.00"),
            total=Decimal("140.00"),
            amount_paid=Decimal("40.00"),
            outstanding_balance=Decimal("100.00"),
            cashier=self.owner,
        )

    def payload(self, amount=Decimal("60.00")):
        # Returns one normalized Mobile Money debt request.
        return {
            "amount": amount,
            "saleId": self.sale.id,
            "paymentMethod": Payment.Method.MOBILE_MONEY,
            "reference": "CUSTOMER-DEBT-001",
            "note": "Customer debt settlement.",
            "mobileMoneyNetwork": "mtn",
            "mobileMoneyNumber": "0241234567",
        }

    def prompt_client(self):
        # Returns one deterministic Paystack prompt response.
        client = Mock()
        client.create_mobile_money_charge.side_effect = lambda **kwargs: {
            "reference": kwargs["reference"],
            "status": "pay_offline",
            "display_text": "Approve the payment on your phone.",
        }
        return client

    def verification_client(
        self,
        payment,
        *,
        status="success",
        amount=6000,
        transaction_id=700001,
    ):
        # Returns one deterministic server-side verification.
        client = Mock()
        client.verify_transaction.return_value = {
            "id": transaction_id,
            "status": status,
            "reference": payment.gateway_reference,
            "amount": amount,
            "currency": "GHS",
            "channel": "mobile_money",
        }
        return client

    def initialize(self, key, *, amount=Decimal("60.00"), client=None):
        # Starts one pending debt payment through the public service.
        return initialize_mobile_money_debt_payment(
            business=self.business,
            customer_id=self.customer.id,
            user=self.owner,
            data=self.payload(amount),
            idempotency_key=key,
            client=client or self.prompt_client(),
        )

    def assert_balances(self, *, sale_paid="40.00", outstanding="100.00"):
        # Reloads and checks both linked financial balances.
        self.sale.refresh_from_db()
        self.customer.refresh_from_db()
        self.assertEqual(self.sale.amount_paid, Decimal(sale_paid))
        self.assertEqual(self.sale.outstanding_balance, Decimal(outstanding))
        self.assertEqual(
            self.customer.outstanding_balance,
            Decimal(outstanding),
        )

    def test_initialization_is_pending_and_does_not_change_balances(self):
        # No receipt or balance change occurs before verification.
        client = self.prompt_client()
        payment, replayed = self.initialize("momo-debt-001", client=client)

        self.assertFalse(replayed)
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertEqual(payment.receipt_number, "")
        self.assertTrue(payment.gateway_reference.startswith("STF-DEBT-"))
        self.assert_balances()
        client.create_mobile_money_charge.assert_called_once_with(
            email="ama.debt@example.com",
            amount_subunit=6000,
            reference=payment.gateway_reference,
            phone="0241234567",
            provider="mtn",
            currency="GHS",
            metadata={
                "business_id": str(self.business.id),
                "sale_id": str(self.sale.id),
                "customer_id": str(self.customer.id),
                "payment_id": str(payment.id),
                "payment_type": Payment.PaymentType.DEBT_PAYMENT,
            },
        )

    def test_idempotent_replay_sends_no_second_prompt(self):
        # Reusing one key returns the original pending payment.
        first, _ = self.initialize("momo-debt-replay")
        second_client = Mock()
        replay, replayed = self.initialize(
            "momo-debt-replay",
            client=second_client,
        )
        self.assertTrue(replayed)
        self.assertEqual(replay.id, first.id)
        second_client.create_mobile_money_charge.assert_not_called()
        self.assertEqual(Payment.objects.count(), 1)

    def test_definitive_rejection_and_timeout_do_not_change_balances(self):
        # Definite rejection fails; uncertain timeout remains pending.
        rejected = Mock()
        rejected.create_mobile_money_charge.side_effect = PaystackRequestError(
            "The charge request was rejected.",
            code="paystack_request_rejected",
            status_code=400,
        )
        with self.assertRaises(PaystackRequestError):
            self.initialize("momo-debt-rejected", client=rejected)
        failed_payment = Payment.objects.get(
            idempotency_key="momo-debt-rejected"
        )
        self.assertEqual(failed_payment.status, Payment.Status.FAILED)
        self.assert_balances()

        timeout = Mock()
        timeout.create_mobile_money_charge.side_effect = PaystackRequestError(
            "Paystack did not respond in time.",
            code="paystack_timeout",
        )
        with self.assertRaises(PaystackRequestError):
            self.initialize("momo-debt-timeout", client=timeout)
        pending_payment = Payment.objects.get(
            idempotency_key="momo-debt-timeout"
        )
        self.assertEqual(pending_payment.status, Payment.Status.PENDING)
        self.assertIn("Verify this payment", pending_payment.note)
        self.assert_balances()

    def test_successful_verification_updates_balances_once(self):
        # Verified value creates one receipt and cannot be applied twice.
        payment, _ = self.initialize("momo-debt-success")
        verified, sale, customer, finalized = (
            verify_and_finalize_mobile_money_debt_payment(
                reference=payment.gateway_reference,
                client=self.verification_client(payment),
            )
        )
        self.assertTrue(finalized)
        self.assertEqual(verified.status, Payment.Status.SUCCESSFUL)
        self.assertEqual(verified.receipt_number, "RCT-00001")
        self.assertEqual(sale.amount_paid, Decimal("100.00"))
        self.assertEqual(sale.outstanding_balance, Decimal("40.00"))
        self.assertEqual(customer.outstanding_balance, Decimal("40.00"))

        replay_client = Mock()
        _, replay_sale, replay_customer, finalized_again = (
            verify_and_finalize_mobile_money_debt_payment(
                reference=payment.gateway_reference,
                client=replay_client,
            )
        )
        self.assertFalse(finalized_again)
        self.assertEqual(replay_sale.outstanding_balance, Decimal("40.00"))
        self.assertEqual(
            replay_customer.outstanding_balance,
            Decimal("40.00"),
        )
        replay_client.verify_transaction.assert_not_called()
        self.assertEqual(
            Payment.objects.exclude(receipt_number="").count(),
            1,
        )

    def test_pending_failure_and_wrong_amount_change_no_balance(self):
        # Pending, terminal failure, and mismatch cannot settle debt.
        pending, _ = self.initialize("momo-debt-pending")
        with self.assertRaisesRegex(MobileMoneyPaymentError, "still pending"):
            verify_and_finalize_mobile_money_debt_payment(
                reference=pending.gateway_reference,
                client=self.verification_client(
                    pending,
                    status="pending",
                ),
            )
        pending.refresh_from_db()
        self.assertEqual(pending.status, Payment.Status.PENDING)
        self.assert_balances()

        failed, _ = self.initialize("momo-debt-failed")
        with self.assertRaises(MobileMoneyPaymentError):
            verify_and_finalize_mobile_money_debt_payment(
                reference=failed.gateway_reference,
                client=self.verification_client(
                    failed,
                    status="failed",
                    transaction_id=700002,
                ),
            )
        failed.refresh_from_db()
        self.assertEqual(failed.status, Payment.Status.FAILED)
        self.assert_balances()

        mismatch, _ = self.initialize("momo-debt-mismatch")
        with self.assertRaisesRegex(MobileMoneyPaymentError, "did not match"):
            verify_and_finalize_mobile_money_debt_payment(
                reference=mismatch.gateway_reference,
                client=self.verification_client(
                    mismatch,
                    amount=5900,
                    transaction_id=700003,
                ),
            )
        mismatch.refresh_from_db()
        self.assertEqual(mismatch.status, Payment.Status.FAILED)
        self.assert_balances()

    def test_full_settlement_and_reused_transaction_protection(self):
        # Full payment closes the invoice; reused provider IDs are rejected.
        payment, _ = self.initialize(
            "momo-debt-full",
            amount=Decimal("100.00"),
        )
        _, sale, customer, finalized = (
            verify_and_finalize_mobile_money_debt_payment(
                reference=payment.gateway_reference,
                client=self.verification_client(
                    payment,
                    amount=10000,
                    transaction_id=700004,
                ),
            )
        )
        self.assertTrue(finalized)
        self.assertEqual(sale.status, Sale.Status.COMPLETED)
        self.assertEqual(sale.outstanding_balance, Decimal("0.00"))
        self.assertEqual(customer.outstanding_balance, Decimal("0.00"))

        second_customer = Customer.objects.create(
            business=self.business,
            name="Second Debt Customer",
            phone="0200000000",
            email="second.debt@example.com",
            outstanding_balance=Decimal("20.00"),
            total_purchases=Decimal("20.00"),
            created_by=self.owner,
        )
        second_sale = Sale.objects.create(
            business=self.business,
            customer=second_customer,
            sale_number="SAL-00002",
            invoice_number="INV-00002",
            payment_method=Sale.PaymentMethod.CREDIT,
            status=Sale.Status.PARTIALLY_PAID,
            subtotal=Decimal("20.00"),
            discount=Decimal("0.00"),
            total=Decimal("20.00"),
            amount_paid=Decimal("0.00"),
            outstanding_balance=Decimal("20.00"),
            cashier=self.owner,
        )
        data = self.payload(Decimal("20.00"))
        data["saleId"] = second_sale.id
        reused, _ = initialize_mobile_money_debt_payment(
            business=self.business,
            customer_id=second_customer.id,
            user=self.owner,
            data=data,
            idempotency_key="momo-debt-reused",
            client=self.prompt_client(),
        )
        with self.assertRaisesRegex(
            MobileMoneyPaymentError,
            "already been processed",
        ):
            verify_and_finalize_mobile_money_debt_payment(
                reference=reused.gateway_reference,
                client=self.verification_client(
                    reused,
                    amount=2000,
                    transaction_id=700004,
                ),
            )
        reused.refresh_from_db()
        second_sale.refresh_from_db()
        second_customer.refresh_from_db()
        self.assertEqual(reused.status, Payment.Status.FAILED)
        self.assertEqual(second_sale.outstanding_balance, Decimal("20.00"))
        self.assertEqual(
            second_customer.outstanding_balance,
            Decimal("20.00"),
        )
