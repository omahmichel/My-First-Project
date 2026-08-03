from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from businesses.models import Business
from businesses.paystack_client import PaystackRequestError
from customers.models import Customer
from inventory.models import Product

from .mobile_money_service import (
    cleanup_expired_mobile_money_reservations,
    initialize_mobile_money_sale,
)
from .models import Payment, Sale


@override_settings(
    PAYMENT_GATEWAY="paystack",
    PAYMENT_GATEWAY_SECRET_KEY="sk_test_stockflow",
    MOBILE_MONEY_RESERVATION_MINUTES=5,
)
class MobileMoneyReservationCleanupTests(TestCase):
    # Protects expired reservations from unsafe or duplicate release.

    def setUp(self):
        self.owner = User.objects.create_user(
            email="cleanup.owner@stockflow.test",
            password="StrongPass123!",
            full_name="Cleanup Owner",
        )
        self.business = Business.objects.create(
            owner=self.owner,
            name="Cleanup Test Shop",
            slug="cleanup-test-shop",
            business_type="building_materials",
            email="cleanup.shop@stockflow.test",
            invoice_prefix="INV",
            receipt_prefix="RCT",
        )
        self.product = Product.objects.create(
            business=self.business,
            name="Cleanup Floor Tile",
            sku="CLEANUP-TILE-01",
            category="Tiles",
            unit="box",
            stock=10,
            reserved_stock=0,
            cost_price=Decimal("100.00"),
            selling_price=Decimal("150.00"),
        )
        self.customer = Customer.objects.create(
            business=self.business,
            name="Cleanup Customer",
            phone="0241234567",
            email="cleanup.customer@example.com",
            created_by=self.owner,
        )

    def payload(self):
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
            "paymentMethod": Sale.PaymentMethod.MOBILE_MONEY,
            "amountPaidMethod": "",
            "mobileMoneyNetwork": "mtn",
            "mobileMoneyNumber": "0241234567",
        }

    def prompt_client(self):
        client = Mock()

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

    def create_expired_attempt(self, *, key):
        sale, payment, _ = initialize_mobile_money_sale(
            business=self.business,
            user=self.owner,
            data=self.payload(),
            idempotency_key=key,
            client=self.prompt_client(),
        )
        checked_at = timezone.now()
        sale.reservation_expires_at = checked_at - timedelta(seconds=1)
        sale.save(update_fields=("reservation_expires_at", "updated_at"))
        return sale, payment, checked_at

    def verification_client(
        self,
        *,
        payment,
        provider_status,
        amount=15000,
        transaction_id=700001,
    ):
        client = Mock()
        client.verify_transaction.return_value = {
            "id": transaction_id,
            "status": provider_status,
            "reference": payment.gateway_reference,
            "amount": amount,
            "currency": "GHS",
            "channel": "mobile_money",
        }
        return client

    def test_expired_success_is_finalized_before_stock_release(self):
        # Confirmed money delivers the sale instead of cancelling it.
        sale, payment, checked_at = self.create_expired_attempt(
            key="cleanup-success-001"
        )
        client = self.verification_client(
            payment=payment,
            provider_status="success",
        )

        summary = cleanup_expired_mobile_money_reservations(
            checked_at=checked_at,
            client=client,
        )

        sale.refresh_from_db()
        payment.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(
            summary,
            {
                "scanned": 1,
                "finalized": 1,
                "released": 0,
                "deferred": 0,
                "skipped": 0,
            },
        )
        self.assertEqual(sale.status, Sale.Status.COMPLETED)
        self.assertEqual(payment.status, Payment.Status.SUCCESSFUL)
        self.assertEqual(self.product.stock, 9)
        self.assertEqual(self.product.reserved_stock, 0)
        self.assertEqual(payment.receipt_number, "RCT-00001")

    def test_expired_pending_payment_releases_reservation(self):
        # An unresolved provider state after expiry frees held stock.
        sale, payment, checked_at = self.create_expired_attempt(
            key="cleanup-pending-001"
        )
        client = self.verification_client(
            payment=payment,
            provider_status="pending",
        )

        summary = cleanup_expired_mobile_money_reservations(
            checked_at=checked_at,
            client=client,
        )

        sale.refresh_from_db()
        payment.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(summary["released"], 1)
        self.assertEqual(sale.status, Sale.Status.FAILED)
        self.assertIsNone(sale.reservation_expires_at)
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertEqual(payment.receipt_number, "")
        self.assertEqual(self.product.stock, 10)
        self.assertEqual(self.product.reserved_stock, 0)
        self.assertIn("expired", payment.failure_reason.lower())

    def test_terminal_failure_is_counted_after_verified_release(self):
        # Existing terminal-failure logic remains the source of truth.
        sale, payment, checked_at = self.create_expired_attempt(
            key="cleanup-failed-001"
        )
        client = self.verification_client(
            payment=payment,
            provider_status="failed",
        )

        summary = cleanup_expired_mobile_money_reservations(
            checked_at=checked_at,
            client=client,
        )

        sale.refresh_from_db()
        payment.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(summary["released"], 1)
        self.assertEqual(sale.status, Sale.Status.FAILED)
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertEqual(self.product.stock, 10)
        self.assertEqual(self.product.reserved_stock, 0)

    def test_gateway_outage_defers_without_releasing_stock(self):
        # A network error cannot guess the payment result.
        sale, payment, checked_at = self.create_expired_attempt(
            key="cleanup-timeout-001"
        )
        client = Mock()
        client.verify_transaction.side_effect = PaystackRequestError(
            "Paystack did not respond in time.",
            code="paystack_timeout",
        )

        summary = cleanup_expired_mobile_money_reservations(
            checked_at=checked_at,
            client=client,
        )

        sale.refresh_from_db()
        payment.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(summary["deferred"], 1)
        self.assertEqual(sale.status, Sale.Status.PENDING_PAYMENT)
        self.assertIsNotNone(sale.reservation_expires_at)
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertEqual(self.product.stock, 10)
        self.assertEqual(self.product.reserved_stock, 1)

    def test_non_expired_and_second_cleanup_are_safe(self):
        # Future reservations are ignored and released records are not repeated.
        sale, payment, checked_at = self.create_expired_attempt(
            key="cleanup-replay-001"
        )
        sale.reservation_expires_at = checked_at + timedelta(minutes=1)
        sale.save(update_fields=("reservation_expires_at", "updated_at"))
        client = Mock()

        first_summary = cleanup_expired_mobile_money_reservations(
            checked_at=checked_at,
            client=client,
        )

        self.assertEqual(first_summary["scanned"], 0)
        client.verify_transaction.assert_not_called()

        sale.reservation_expires_at = checked_at - timedelta(seconds=1)
        sale.save(update_fields=("reservation_expires_at", "updated_at"))
        pending_client = self.verification_client(
            payment=payment,
            provider_status="pending",
        )
        cleanup_expired_mobile_money_reservations(
            checked_at=checked_at,
            client=pending_client,
        )
        second_summary = cleanup_expired_mobile_money_reservations(
            checked_at=checked_at,
            client=Mock(),
        )

        self.product.refresh_from_db()
        self.assertEqual(second_summary["scanned"], 0)
        self.assertEqual(self.product.stock, 10)
        self.assertEqual(self.product.reserved_stock, 0)


class MobileMoneyReservationCleanupCommandTests(TestCase):
    # Protects the operator-facing management command contract.

    @patch(
        "sales.management.commands.cleanup_mobile_money_reservations."
        "cleanup_expired_mobile_money_reservations"
    )
    def test_command_uses_limit_and_reports_summary(self, cleanup_mock):
        cleanup_mock.return_value = {
            "scanned": 3,
            "finalized": 1,
            "released": 1,
            "deferred": 1,
            "skipped": 0,
        }
        stdout = StringIO()

        call_command(
            "cleanup_mobile_money_reservations",
            "--limit",
            "25",
            stdout=stdout,
        )

        cleanup_mock.assert_called_once_with(batch_size=25)
        output = stdout.getvalue()
        self.assertIn("scanned=3", output)
        self.assertIn("finalized=1", output)
        self.assertIn("released=1", output)
        self.assertIn("deferred=1", output)
