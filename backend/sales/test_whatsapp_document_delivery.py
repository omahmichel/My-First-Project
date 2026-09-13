from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from businesses.models import Branch, Business
from customers.models import Customer
from integrations.messaging.whatsapp_live import save_whatsapp_credentials
from sales.models import Payment, Sale


@override_settings(DEBUG=True)
class WhatsAppDocumentDeliveryTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            email="document-share-owner@example.com",
            password="StrongPass123!",
        )
        self.business = Business.objects.create(
            owner=self.owner,
            name="Document Share Business",
            slug="document-share-business",
            business_type=Business.BusinessType.BUILDING_MATERIALS,
        )
        self.branch = Branch.objects.create(
            business=self.business,
            name="Main Branch",
            code="MAIN",
            is_main=True,
            is_active=True,
            created_by=self.owner,
        )
        self.customer = Customer.objects.create(
            business=self.business,
            name="Ama Customer",
            phone="0244000011",
            created_by=self.owner,
        )
        self.sale = Sale.objects.create(
            business=self.business,
            branch=self.branch,
            customer=self.customer,
            customer_name=self.customer.name,
            customer_phone=self.customer.phone,
            sale_number="SAL-00001",
            invoice_number="INV-00001",
            payment_method=Sale.PaymentMethod.CASH,
            status=Sale.Status.COMPLETED,
            subtotal=Decimal("120.00"),
            discount=Decimal("0.00"),
            total=Decimal("120.00"),
            amount_paid=Decimal("120.00"),
            outstanding_balance=Decimal("0.00"),
            cashier=self.owner,
        )
        self.payment = Payment.objects.create(
            business=self.business,
            sale=self.sale,
            customer=self.customer,
            payment_type=Payment.PaymentType.SALE_PAYMENT,
            method=Payment.Method.CASH,
            status=Payment.Status.SUCCESSFUL,
            amount=Decimal("120.00"),
            receipt_number="RCT-00001",
            initiated_by=self.owner,
        )
        save_whatsapp_credentials(
            business=self.business,
            access_token="test-access-token",
            phone_number_id="1234567890",
            api_version="v23.0",
            created_by=self.owner,
        )
        self.client.force_authenticate(self.owner)
        self.url = (
            f"/api/businesses/{self.business.id}/sales/"
            f"{self.sale.id}/whatsapp-document/"
        )

    def pdf(self, name="browser-generated.pdf"):
        return SimpleUploadedFile(
            name,
            b"%PDF-1.4\nStockFlow test PDF\n%%EOF",
            content_type="application/pdf",
        )

    @staticmethod
    def provider_responses():
        upload = Mock()
        upload.status_code = 200
        upload.json.return_value = {"id": "media-123"}

        sent = Mock()
        sent.status_code = 200
        sent.json.return_value = {
            "messages": [{"id": "wamid.document-123"}]
        }
        return upload, sent

    @patch("integrations.messaging.whatsapp_live.requests.post")
    def test_invoice_pdf_is_uploaded_then_sent_as_document(self, post):
        post.side_effect = self.provider_responses()

        response = self.client.post(
            self.url,
            {
                "documentType": "invoice",
                "document": self.pdf("untrusted-client-name.pdf"),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["filename"], "INV-00001.pdf")
        self.assertEqual(response.data["documentType"], "invoice")
        self.assertEqual(
            response.data["providerReference"],
            "wamid.document-123",
        )
        self.assertEqual(post.call_count, 2)

        upload_call = post.call_args_list[0]
        self.assertTrue(
            upload_call.args[0].endswith("/1234567890/media")
        )
        self.assertEqual(
            upload_call.kwargs["files"]["file"][0],
            "INV-00001.pdf",
        )

        send_call = post.call_args_list[1]
        payload = send_call.kwargs["json"]
        self.assertEqual(payload["to"], "233244000011")
        self.assertEqual(payload["type"], "document")
        self.assertEqual(payload["document"]["id"], "media-123")
        self.assertEqual(
            payload["document"]["filename"],
            "INV-00001.pdf",
        )

    @patch("integrations.messaging.whatsapp_live.requests.post")
    def test_receipt_uses_server_verified_payment_number(self, post):
        post.side_effect = self.provider_responses()

        response = self.client.post(
            self.url,
            {
                "documentType": "receipt",
                "paymentId": str(self.payment.id),
                "document": self.pdf(),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["filename"], "RCT-00001.pdf")

    def test_rejects_non_pdf_content(self):
        fake = SimpleUploadedFile(
            "fake.pdf",
            b"this is not a pdf",
            content_type="application/pdf",
        )

        response = self.client.post(
            self.url,
            {
                "documentType": "invoice",
                "document": fake,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("document", response.data)

    def test_missing_customer_phone_is_rejected(self):
        # Sale.save() refreshes the historical customer-phone snapshot from
        # the linked customer. Use queryset.update() here to simulate a
        # genuinely missing stored snapshot without invoking model save().
        Sale.objects.filter(pk=self.sale.pk).update(customer_phone="")

        response = self.client.post(
            self.url,
            {
                "documentType": "invoice",
                "document": self.pdf(),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("phone", response.data["detail"].lower())

    def test_receipt_requires_payment_id(self):
        response = self.client.post(
            self.url,
            {
                "documentType": "receipt",
                "document": self.pdf(),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("paymentId", response.data)

    @patch("integrations.messaging.whatsapp_live.requests.post")
    def test_provider_failure_returns_safe_gateway_error(self, post):
        failed = Mock()
        failed.status_code = 400
        failed.json.return_value = {
            "error": {
                "message": "provider rejected upload",
                "code": 100,
            }
        }
        post.return_value = failed

        response = self.client.post(
            self.url,
            {
                "documentType": "invoice",
                "document": self.pdf(),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.data["code"],
            "whatsapp_document_send_failed",
        )
        self.assertNotIn("test-access-token", str(response.data))
