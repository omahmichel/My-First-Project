"""Registration OTP SMS; never logs the code or provider response."""
import requests
from sales.debt_reminder_service import send_mnotify_sms


def send_registration_sms(*, recipient, message):
    def post_otp(url, **kwargs):
        kwargs["json"]["sms_type"] = "otp"
        return requests.post(url, **kwargs)
    send_mnotify_sms(recipient=recipient, message=message, request_func=post_otp)
