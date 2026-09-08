from .provider import BaseMessageProvider, MessagingProviderError


class WhatsAppProvider(BaseMessageProvider):
    """Provider contract only. Live WhatsApp delivery is intentionally disabled."""

    channel = "whatsapp"
    provider_name = "unconfigured"
    available = False

    def send(self, *, recipient, message):
        raise MessagingProviderError(
            "WhatsApp delivery is not configured for this StockFlow deployment."
        )
