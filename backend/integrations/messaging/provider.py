class MessagingProviderError(Exception):
    def __init__(self, message, *, response_summary=""):
        super().__init__(message)
        self.response_summary = str(response_summary or "")[:1000]


class BaseMessageProvider:
    channel = ""
    provider_name = ""
    available = False

    def send(self, *, recipient, message):
        raise NotImplementedError
