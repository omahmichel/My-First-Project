from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from businesses.models import Business, BusinessMembership
from customers.models import Customer
from inventory.models import Product, StockMovement

from .models import Payment, Sale


class SalesRegressionTests(APITestCase):
    # Builds isolated business records for every sales API test.

    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner.tests@stockflow.local",
            password="StrongPass123!",
            full_name="Test Owner",
        )
        self.cashier = User.objects.create_user(
            email="cashier.tests@stockflow.local",
            password="StrongPass123!",
            full_name="Test Cashier",
        )
        self.outsider = User.objects.create_user(
            email="outsider.tests@stockflow.local",
            password="StrongPass123!",
            full_name="Outside User",
        )

        self.business = Business.objects.create(
            owner=self.owner,
            name="Phildial Test",
            slug="phildial-test",
            business_type="building_materials",
            invoice_prefix="INV",
            receipt_prefix="RCT",
        )
        self.other_business = Business.objects.create(
            owner=self.owner,
            name="Kendy Test",
            slug="kendy-test",
            business_type="boutique",
            invoice_prefix="INV",
            receipt_prefix="RCT",
        )

        BusinessMembership.objects.create(
            business=self.business,
            user=self.cashier,
            role="cashier",
            is_active=True,
        )

        self.product = Product.objects.create(
            business=self.business,
            name="Royal Ceramic Floor Tile",
            sku="TILE-6052",
            category="Tiles",
            unit="box",
            stock=10,
            reserved_stock=0,
            low_stock_level=2,
            cost_price=Decimal("120.00"),
            selling_price=Decimal("150.00"),
            design_code="6052",
        )
        self.customer = Customer.objects.create(
            business=self.business,
            name="Ama Serwaa",
            phone="0241234567",
            email="ama.tests@example.com",
            address="Adenta, Accra",
            created_by=self.owner,
        )

        self.sales_url = f"/api/businesses/{self.business.id}/sales/"
        self.customer_payment_url = (
            f"/api/businesses/{self.business.id}/customers/"
            f"{self.customer.id}/payments/"
        )
        self.other_business_customer_payment_url = (
            f"/api/businesses/{self.other_business.id}/customers/"
            f"{self.customer.id}/payments/"
        )

    def authenticate(self, user):
        # Authenticates directly without depending on the login endpoint.
        self.client.force_authenticate(user=user)

    def idempotency_headers(self, key):
        # Produces the DRF test-client form of Idempotency-Key.
        return {"HTTP_IDEMPOTENCY_KEY": key}

    def cash_sale_payload(self):
        # Returns one complete cash checkout request.
        return {
            "items": [
                {
                    "productId": str(self.product.id),
                    "quantity": 1,
                    "unitPrice": "150.00",
                }
            ],
            "customerId": None,
            "discount": "0.00",
            "amountPaid": "150.00",
            "paymentMethod": "cash",
        }

    def credit_sale_payload(self):
        # Returns one part-paid GHS 140 credit checkout request.
        return {
            "items": [
                {
                    "productId": str(self.product.id),
                    "quantity": 1,
                    "unitPrice": "150.00",
                }
            ],
            "customerId": str(self.customer.id),
            "discount": "10.00",
            "amountPaid": "40.00",
            "paymentMethod": "credit",
            "amountPaidMethod": "cash",
        }

    def create_credit_sale(self, key="credit-sale-test"):
        # Creates the shared credit-sale fixture through the API.
        self.authenticate(self.owner)
        response = self.client.post(
            self.sales_url,
            self.credit_sale_payload(),
            format="json",
            **self.idempotency_headers(key),
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.data,
        )
        return response

    def test_cash_sale_creates_documents_payment_and_stock_movement(self):
        # A successful cash sale must commit all related records together.
        self.authenticate(self.owner)
        response = self.client.post(
            self.sales_url,
            self.cash_sale_payload(),
            format="json",
            **self.idempotency_headers("cash-sale-001"),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.data,
        )
        self.assertEqual(response.data["status"], "completed")
        self.assertEqual(response.data["saleNumber"], "SAL-00001")
        self.assertEqual(response.data["invoiceNumber"], "INV-00001")
        self.assertEqual(response.data["receiptNumber"], "RCT-00001")

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 9)
        self.assertEqual(self.product.reserved_stock, 0)

        sale = Sale.objects.get(id=response.data["id"])
        self.assertEqual(sale.total, Decimal("150.00"))
        self.assertEqual(sale.amount_paid, Decimal("150.00"))
        self.assertEqual(sale.outstanding_balance, Decimal("0.00"))
        self.assertEqual(
            Payment.objects.filter(
                sale=sale,
                status=Payment.Status.SUCCESSFUL,
            ).count(),
            1,
        )

        movement = StockMovement.objects.get(
            business=self.business,
            reason="Sale SAL-00001",
        )
        self.assertEqual(movement.quantity, -1)
        self.assertEqual(movement.previous_stock, 10)
        self.assertEqual(movement.new_stock, 9)

    def test_sale_idempotency_replays_without_duplicate_changes(self):
        # Reusing a key must return the original sale without charging twice.
        self.authenticate(self.owner)
        headers = self.idempotency_headers("cash-sale-replay-001")
        payload = self.cash_sale_payload()

        first_response = self.client.post(
            self.sales_url,
            payload,
            format="json",
            **headers,
        )
        replay_response = self.client.post(
            self.sales_url,
            payload,
            format="json",
            **headers,
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(replay_response.status_code, status.HTTP_200_OK)
        self.assertEqual(replay_response["Idempotent-Replay"], "true")
        self.assertEqual(
            replay_response.data["id"],
            first_response.data["id"],
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 9)
        self.assertEqual(Sale.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(StockMovement.objects.count(), 1)

    def test_cashier_can_view_sale_without_cost_price(self):
        # Cashiers may view sales but must never receive the product cost.
        owner_response = self.create_credit_sale(
            key="cashier-privacy-sale-001"
        )
        sale_id = owner_response.data["id"]

        self.authenticate(self.cashier)
        response = self.client.get(f"{self.sales_url}{sale_id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("costPrice", response.data["items"][0])
        self.assertIn("unitPrice", response.data["items"][0])

    def test_debt_payments_reduce_balances_and_complete_invoice(self):
        # Later payments must settle the invoice and customer atomically.
        sale_response = self.create_credit_sale(
            key="debt-payment-sale-001"
        )
        sale_id = sale_response.data["id"]

        first_payment = self.client.post(
            self.customer_payment_url,
            {
                "amount": "60.00",
                "saleId": sale_id,
                "paymentMethod": "cash",
                "reference": "DEBT-CASH-001",
            },
            format="json",
            **self.idempotency_headers("debt-payment-001"),
        )
        self.assertEqual(
            first_payment.status_code,
            status.HTTP_201_CREATED,
            first_payment.data,
        )
        self.assertEqual(first_payment.data["receiptNumber"], "RCT-00002")

        sale = Sale.objects.get(pk=sale_id)
        self.customer.refresh_from_db()
        self.assertEqual(sale.amount_paid, Decimal("100.00"))
        self.assertEqual(sale.outstanding_balance, Decimal("40.00"))
        self.assertEqual(sale.status, Sale.Status.PARTIALLY_PAID)
        self.assertEqual(
            self.customer.outstanding_balance,
            Decimal("40.00"),
        )

        final_payment = self.client.post(
            self.customer_payment_url,
            {
                "amount": "40.00",
                "saleId": sale_id,
                "paymentMethod": "cash",
                "reference": "DEBT-CASH-002",
            },
            format="json",
            **self.idempotency_headers("debt-payment-002"),
        )
        self.assertEqual(
            final_payment.status_code,
            status.HTTP_201_CREATED,
            final_payment.data,
        )
        self.assertEqual(final_payment.data["receiptNumber"], "RCT-00003")

        sale.refresh_from_db()
        self.customer.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(sale.amount_paid, Decimal("140.00"))
        self.assertEqual(sale.outstanding_balance, Decimal("0.00"))
        self.assertEqual(sale.status, Sale.Status.COMPLETED)
        self.assertEqual(
            self.customer.outstanding_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.customer.total_purchases,
            Decimal("140.00"),
        )
        self.assertEqual(self.product.stock, 9)
        self.assertEqual(
            Payment.objects.filter(
                sale=sale,
                payment_type=Payment.PaymentType.DEBT_PAYMENT,
            ).count(),
            2,
        )

    def test_debt_payment_idempotency_prevents_second_balance_reduction(self):
        # Replaying one debt payment must not create another receipt.
        sale_response = self.create_credit_sale(
            key="debt-replay-sale-001"
        )
        sale_id = sale_response.data["id"]
        headers = self.idempotency_headers("debt-replay-payment-001")
        payload = {
            "amount": "60.00",
            "saleId": sale_id,
            "paymentMethod": "cash",
            "reference": "DEBT-REPLAY-001",
        }

        first_response = self.client.post(
            self.customer_payment_url,
            payload,
            format="json",
            **headers,
        )
        replay_response = self.client.post(
            self.customer_payment_url,
            payload,
            format="json",
            **headers,
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(replay_response.status_code, status.HTTP_200_OK)
        self.assertEqual(replay_response["Idempotent-Replay"], "true")
        self.assertEqual(
            replay_response.data["id"],
            first_response.data["id"],
        )

        sale = Sale.objects.get(pk=sale_id)
        self.customer.refresh_from_db()
        self.assertEqual(sale.amount_paid, Decimal("100.00"))
        self.assertEqual(sale.outstanding_balance, Decimal("40.00"))
        self.assertEqual(
            self.customer.outstanding_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            Payment.objects.filter(
                sale=sale,
                payment_type=Payment.PaymentType.DEBT_PAYMENT,
            ).count(),
            1,
        )

    def test_overpayment_is_rejected_without_database_changes(self):
        # A debt payment cannot exceed the selected outstanding balance.
        sale_response = self.create_credit_sale(
            key="overpayment-sale-001"
        )
        sale_id = sale_response.data["id"]

        response = self.client.post(
            self.customer_payment_url,
            {
                "amount": "101.00",
                "saleId": sale_id,
                "paymentMethod": "cash",
            },
            format="json",
            **self.idempotency_headers("overpayment-001"),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        sale = Sale.objects.get(pk=sale_id)
        self.customer.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(sale.amount_paid, Decimal("40.00"))
        self.assertEqual(sale.outstanding_balance, Decimal("100.00"))
        self.assertEqual(
            self.customer.outstanding_balance,
            Decimal("100.00"),
        )
        self.assertEqual(self.product.stock, 9)
        self.assertEqual(
            Payment.objects.filter(
                idempotency_key="overpayment-001",
            ).count(),
            0,
        )

    def test_mobile_money_checkout_is_blocked_without_gateway(self):
        # The API must not fake a Mobile Money prompt or successful sale.
        self.authenticate(self.owner)
        payload = self.cash_sale_payload()
        payload.update(
            {
                "paymentMethod": "mobile_money",
                "mobileMoneyNetwork": "mtn",
                "mobileMoneyNumber": "0241234567",
            }
        )

        response = self.client.post(
            self.sales_url,
            payload,
            format="json",
            **self.idempotency_headers("momo-checkout-001"),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("paymentMethod", response.data)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)
        self.assertEqual(self.product.reserved_stock, 0)
        self.assertEqual(Sale.objects.count(), 0)
        self.assertEqual(Payment.objects.count(), 0)
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_business_isolation_hides_customer_from_other_business(self):
        # Even one owner of two shops cannot mix their customer records.
        self.authenticate(self.owner)

        response = self.client.post(
            self.other_business_customer_payment_url,
            {
                "amount": "1.00",
                "paymentMethod": "cash",
            },
            format="json",
            **self.idempotency_headers("cross-business-payment-001"),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            Payment.objects.filter(
                idempotency_key="cross-business-payment-001",
            ).count(),
            0,
        )

    def test_outsider_cannot_access_business_sales(self):
        # Non-members receive a hidden-business response.
        self.authenticate(self.outsider)
        response = self.client.get(self.sales_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_idempotency_key_is_required_for_sales_and_debt_payments(self):
        # Financial write requests must always include a unique key.
        self.authenticate(self.owner)

        sale_response = self.client.post(
            self.sales_url,
            self.cash_sale_payload(),
            format="json",
        )
        payment_response = self.client.post(
            self.customer_payment_url,
            {
                "amount": "1.00",
                "paymentMethod": "cash",
            },
            format="json",
        )

        self.assertEqual(
            sale_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            payment_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            sale_response.data["detail"],
            "Idempotency-Key header is required.",
        )
        self.assertEqual(
            payment_response.data["detail"],
            "Idempotency-Key header is required.",
        )
        self.assertEqual(Sale.objects.count(), 0)
        self.assertEqual(Payment.objects.count(), 0)
