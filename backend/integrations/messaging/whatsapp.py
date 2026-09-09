from .provider import BaseMessageProvider, MessagingProviderError


class WhatsAppProvider(BaseMessageProvider):
    """Business-scoped WhatsApp Cloud API provider."""

    channel = "whatsapp"
    provider_name = "whatsapp_cloud_api"
    available = True

    def send(self, *, recipient, message, business=None):
        if business is None:
            raise MessagingProviderError(
                "A business is required for WhatsApp delivery."
            )
        from .whatsapp_live import send_whatsapp_text

        return send_whatsapp_text(
            business=business,
            recipient=recipient,
            message=message,
        )
