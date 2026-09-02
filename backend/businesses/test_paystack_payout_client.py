from unittest.mock import Mock

from django.test import SimpleTestCase, override_settings

from .paystack_client import PaystackClient


@override_settings(
    PAYMENT_GATEWAY="paystack",
    PAYMENT_GATEWAY_SECRET_KEY="sk_test_stockflow_payout",
)
class PaystackPayoutClientTests(SimpleTestCase):
    def setUp(self):
        self.session = Mock()
        self.response = Mock()
        self.response.status_code = 200
        self.session.request.return_value = self.response
        self.client = PaystackClient(session=self.session)

    def test_creates_ghana_mobile_money_transfer_recipient(self):
        self.response.json.return_value = {
            "status": True,
            "data": {
                "id": 123,
                "recipient_code": "RCP_stockflow",
                "type": "mobile_money",
                "currency": "GHS",
            },
        }

        result = self.client.create_transfer_recipient(
            name="Merchant Owner",
            account_number="0241234567",
            bank_code="MTN",
        )

        self.assertEqual(result["recipient_code"], "RCP_stockflow")
        request = self.session.request.call_args
        self.assertTrue(request.args[1].endswith("/transferrecipient"))
        self.assertEqual(request.kwargs["json"]["type"], "mobile_money")
        self.assertEqual(request.kwargs["json"]["currency"], "GHS")
        self.assertEqual(request.kwargs["json"]["bank_code"], "MTN")

    def test_initiates_balance_transfer_with_caller_reference(self):
        self.response.json.return_value = {
            "status": True,
            "data": {
                "reference": "stf_payout_1234567890abcdef",
                "status": "pending",
                "transfer_code": "TRF_stockflow",
            },
        }

        result = self.client.initiate_transfer(
            amount_subunit=18500,
            recipient_code="RCP_stockflow",
            reference="stf_payout_1234567890abcdef",
            reason="StockFlow merchant payout",
        )

        self.assertEqual(result["status"], "pending")
        payload = self.session.request.call_args.kwargs["json"]
        self.assertEqual(payload["source"], "balance")
        self.assertEqual(payload["amount"], 18500)
        self.assertEqual(payload["recipient"], "RCP_stockflow")
