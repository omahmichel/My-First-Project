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

from .mobile_money_service import initialize_mobile_money_sale
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
