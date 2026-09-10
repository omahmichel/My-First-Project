from django.test import TestCase, override_settings
from customers.models import Customer
from sales.models import Sale, Payment
from . import test_completion


@override_settings(ALLOWED_HOSTS=['testserver', 'localhost'])
class AutomaticOrderCustomerTests(TestCase):
    def setUp(self):
        test_completion.OrderCompletionTests.setUp(self)

    def submit(self):
        return self.client.post(self.complete, self.payload, format='json')

    def test_existing_customer_is_matched_without_client_customer_id(self):
        response = self.submit()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Sale.objects.get().customer_id, self.customer.id)
        self.assertEqual(Customer.objects.count(), 1)

    def test_ghana_phone_formats_match(self):
        self.customer.phone = '+233244000000'
        self.customer.save()
        response = self.submit()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(Sale.objects.get().customer_phone, self.order.customer_phone)

    def test_missing_customer_is_created_once_on_retry(self):
        self.customer.delete()
        self.assertEqual(self.submit().status_code, 200)
        self.assertEqual(self.submit().status_code, 200)
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(Customer.objects.get().name, self.order.customer_name)
        self.assertEqual(Payment.objects.count(), 1)

    def test_conflicting_or_duplicate_accounts_block_completion(self):
        self.customer.name = 'Different buyer'
        self.customer.save()
        self.assertEqual(self.submit().status_code, 400)
        self.customer.name = self.order.customer_name
        self.customer.save()
        Customer.objects.create(business=self.business, name=self.order.customer_name, phone=self.order.customer_phone)
        self.assertEqual(self.submit().status_code, 400)
        self.assertFalse(Sale.objects.exists())

    def test_invoice_keeps_order_snapshot_after_customer_changes(self):
        self.assertEqual(self.submit().status_code, 200)
        self.customer.name = 'Updated account name'
        self.customer.phone = '0200000000'
        self.customer.save()
        sale = Sale.objects.get()
        sale.save()
        sale.refresh_from_db()
        self.assertEqual(sale.customer_name, self.order.customer_name)
        self.assertEqual(sale.customer_phone, self.order.customer_phone)

    def test_client_cannot_choose_another_customer(self):
        response = self.client.post(self.complete, dict(self.payload, customerId=str(self.customer.id)), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Sale.objects.exists())
