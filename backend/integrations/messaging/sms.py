from sales.debt_reminder_service import (
    DebtReminderProviderError,
    send_mnotify_sms,
)

from .provider import BaseMessageProvider, MessagingProviderError


class MNotifySmsProvider(BaseMessageProvider):
    channel = "sms"
    provider_name = "mnotify"
    available = True

    def send(self, *, recipient, message):
        try:
            return send_mnotify_sms(
                recipient=recipient,
                message=message,
            )
        except DebtReminderProviderError as exc:
            raise MessagingProviderError(
                str(exc),
                response_summary=getattr(exc, "response_summary", ""),
            ) from exc
