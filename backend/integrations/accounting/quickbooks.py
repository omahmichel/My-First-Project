from .provider import BaseAccountingProvider


class QuickBooksAccountingProvider(BaseAccountingProvider):
    provider_name = "quickbooks"
    display_name = "QuickBooks Online"
