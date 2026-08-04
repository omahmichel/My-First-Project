from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock

from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from businesses.models import Business
from customers.models import Customer

from .mobile_money_service import (
    initialize_mobile_money_debt_payment,
    verify_and_finalize_mobile_money_debt_payment,
)
from .models import (
    DebtOverdueCharge,
    DebtPaymentAllocation,
    Payment,
    Sale,
)
from .services import (
    ensure_current_overdue_charges,
    overdue_tier_percentage_for_days,
    record_customer_debt_payment,
)


@override_settings(
    PAYMENT_GATEWAY="paystack",
    PAYMENT_GATEWAY_SECRET_KEY="sk_test_stockflow",
)
class DebtOverdueServiceTests(TestCase):
    # Protects tier creation and charge-first settlement across payment paths.

    def setUp(self):
        self.owner = User.objects.create_user(
            email="overdue.service@stockflow.test",
            password="StrongPass123!",
            full_name="Overdue Service Owner",
        )
        self.business = Business.objects.create(
            owner=self.owner,
            name="Overdue Service Shop",
            slug="overdue-service-shop",
            business_type="building_materials",
            email="overdue.shop@stockflow.test",
            invoice_prefix="INV",
            receipt_prefix="RCT",
        )
        self.customer = Customer.objects.create(
            business=self.business,
            name="Adwoa Overdue Customer",
            phone="0241234567",
            email="adwoa.overdue@example.com",
            outstanding_balance=Decimal("100.00"),
            total_purchases=Decimal("140.00"),
            created_by=self.owner,
        )
        self.sale = Sale.objects.create(
            business=self.business,
            customer=self.customer,
            sale_number="SAL-OVERDUE-0001",
            invoice_number="INV-OVERDUE-0001",
            payment_method=Sale.PaymentMethod.CREDIT,
            status=Sale.Status.PARTIALLY_PAID,
            subtotal=Decimal("140.00"),
            discount=Decimal("0.00"),
            total=Decimal("140.00"),
            amount_paid=Decimal("40.00"),
            outstanding_balance=Decimal("100.00"),
            debt_due_date=timezone.localdate() - timedelta(days=1),
            debt_principal_at_due=Decimal("100.00"),
            cashier=self.owner,
            cashier_name=self.owner.full_name,
        )

    def test_overdue_day_boundaries_map_to_capped_tiers(self):
        # Every threshold must match the approved 5%-to-30% schedule.
        expected = {
            0: 0,
            1: 5,
            30: 5,
            31: 10,
            60: 10,
            61: 15,
            90: 15,
            91: 20,
            120: 20,
            121: 25,
            150: 25,
            151: 30,
            999: 30,
        }

        for days_overdue, percentage in expected.items():
            with self.subTest(days_overdue=days_overdue):
                self.assertEqual(
                    overdue_tier_percentage_for_days(days_overdue),
                    percentage,
                )

    def test_due_date_itself_creates_no_charge(self):
        # A charge starts only after the original due date has passed.
        self.sale.debt_due_date = timezone.localdate()
        self.sale.save(update_fields=("debt_due_date", "updated_at"))

        created = ensure_current_overdue_charges(sale=self.sale)

        self.assertEqual(created, [])
        self.assertFalse(
            DebtOverdueCharge.objects.filter(sale=self.sale).exists()
        )

    def test_crossed_tiers_are_incremental_capped_and_idempotent(self):
        # Processing day 151 creates each crossed tier once without compounding.
        self.sale.debt_due_date = (
            timezone.localdate() - timedelta(days=151)
        )
        self.sale.save(update_fields=("debt_due_date", "updated_at"))

        created = ensure_current_overdue_charges(sale=self.sale)
        replay = ensure_current_overdue_charges(sale=self.sale)

        self.assertEqual(len(created), 6)
        self.assertEqual(replay, [])
        self.assertEqual(
            list(
                DebtOverdueCharge.objects.filter(
                    sale=self.sale,
                ).values_list(
                    "tier_percentage",
                    "total_charge_required",
                    "incremental_amount",
                )
            ),
            [
                (5, Decimal("5.00"), Decimal("5.00")),
                (10, Decimal("10.00"), Decimal("5.00")),
                (15, Decimal("15.00"), Decimal("5.00")),
                (20, Decimal("20.00"), Decimal("5.00")),
                (25, Decimal("25.00"), Decimal("5.00")),
                (30, Decimal("30.00"), Decimal("5.00")),
            ],
        )

    def test_cash_payment_settles_charge_before_principal_once(self):
        # A day-one payment pays the 5% charge before reducing principal.
        payment, replayed = record_customer_debt_payment(
            business=self.business,
            customer_id=self.customer.id,
            user=self.owner,
            data={
                "amount": Decimal("60.00"),
                "saleId": self.sale.id,
                "paymentMethod": Payment.Method.CASH,
                "reference": "OVERDUE-CASH-001",
                "note": "",
            },
            idempotency_key="overdue-cash-001",
        )

        self.assertFalse(replayed)
        allocation = DebtPaymentAllocation.objects.get(payment=payment)
        self.assertEqual(
            allocation.overdue_charge_paid,
            Decimal("5.00"),
        )
        self.assertEqual(allocation.principal_paid, Decimal("55.00"))

        self.sale.refresh_from_db()
        self.customer.refresh_from_db()
        self.assertEqual(self.sale.amount_paid, Decimal("95.00"))
        self.assertEqual(
            self.sale.outstanding_balance,
            Decimal("45.00"),
        )
        self.assertEqual(
            self.customer.outstanding_balance,
            Decimal("45.00"),
        )

        replay_payment, replayed = record_customer_debt_payment(
            business=self.business,
            customer_id=self.customer.id,
            user=self.owner,
            data={
                "amount": Decimal("60.00"),
                "saleId": self.sale.id,
                "paymentMethod": Payment.Method.CASH,
                "reference": "OVERDUE-CASH-001",
                "note": "",
            },
            idempotency_key="overdue-cash-001",
        )

        self.assertTrue(replayed)
        self.assertEqual(replay_payment.id, payment.id)
        self.assertEqual(
            DebtPaymentAllocation.objects.filter(
                payment=payment,
            ).count(),
            1,
        )

    def test_mobile_money_verification_uses_same_charge_first_split(self):
        # Pending prompts change no balances; verification shares the allocator.
        prompt_client = Mock()
        prompt_client.create_mobile_money_charge.return_value = {
            "reference": "provider-reference",
            "status": "pay_offline",
            "display_text": "Approve the payment on your phone.",
        }
        payment, replayed = initialize_mobile_money_debt_payment(
            business=self.business,
            customer_id=self.customer.id,
            user=self.owner,
            data={
                "amount": Decimal("60.00"),
                "saleId": self.sale.id,
                "paymentMethod": Payment.Method.MOBILE_MONEY,
                "reference": "OVERDUE-MOMO-001",
                "note": "",
                "mobileMoneyNetwork": "mtn",
                "mobileMoneyNumber": "0241234567",
            },
            idempotency_key="overdue-momo-001",
            client=prompt_client,
        )

        self.assertFalse(replayed)
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertFalse(
            DebtPaymentAllocation.objects.filter(
                payment=payment,
            ).exists()
        )
        self.sale.refresh_from_db()
        self.customer.refresh_from_db()
        self.assertEqual(
            self.sale.outstanding_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.customer.outstanding_balance,
            Decimal("100.00"),
        )

        verification_client = Mock()
        verification_client.verify_transaction.return_value = {
            "id": 800001,
            "status": "success",
            "reference": payment.gateway_reference,
            "amount": 6000,
            "currency": "GHS",
            "channel": "mobile_money",
        }
        verified, sale, customer, finalized = (
            verify_and_finalize_mobile_money_debt_payment(
                reference=payment.gateway_reference,
                client=verification_client,
            )
        )

        self.assertTrue(finalized)
        self.assertEqual(verified.status, Payment.Status.SUCCESSFUL)
        allocation = DebtPaymentAllocation.objects.get(payment=verified)
        self.assertEqual(
            allocation.overdue_charge_paid,
            Decimal("5.00"),
        )
        self.assertEqual(allocation.principal_paid, Decimal("55.00"))
        self.assertEqual(sale.amount_paid, Decimal("95.00"))
        self.assertEqual(
            sale.outstanding_balance,
            Decimal("45.00"),
        )
        self.assertEqual(
            customer.outstanding_balance,
            Decimal("45.00"),
        )
