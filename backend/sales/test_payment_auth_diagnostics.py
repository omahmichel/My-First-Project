from unittest.mock import Mock, patch
from django.test import SimpleTestCase
from .mobile_money_auth import _trace_request, _trace_status

class PaymentAuthDiagnosticTests(SimpleTestCase):
    def test_diagnostics_never_log_code_or_reference(self):
        @_trace_request
        def action(**kwargs): return Mock(status="pending_payment")
        with self.assertLogs("sales.mobile_money_auth", level="WARNING") as logs:
            action(otp="987654", reference="private-reference")
            _trace_status("after_otp", {"status":"pay_offline", "otp":"987654"})
        text=" ".join(logs.output)
        self.assertIn("otp_supplied=True",text)
        self.assertIn("provider_status=pay_offline",text)
        self.assertNotIn("987654",text)
        self.assertNotIn("private-reference",text)

    def test_exception_text_is_not_logged(self):
        @_trace_request
        def action(**kwargs): raise ValueError("sensitive-provider-value")
        with self.assertLogs("sales.mobile_money_auth",level="WARNING") as logs:
            with self.assertRaises(ValueError): action(otp="987654")
        self.assertIn("error_type=ValueError"," ".join(logs.output))
        self.assertNotIn("sensitive-provider-value"," ".join(logs.output))

    def test_unknown_provider_status_is_not_echoed(self):
        with self.assertLogs("sales.mobile_money_auth",level="WARNING") as logs:
            _trace_status("before_otp",{"status":"sensitive-provider-value"})
        self.assertIn("other_or_missing"," ".join(logs.output))
        self.assertNotIn("sensitive-provider-value"," ".join(logs.output))
