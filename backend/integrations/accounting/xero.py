from .provider import BaseAccountingProvider


class XeroAccountingProvider(BaseAccountingProvider):
    provider_name = "xero"
    display_name = "Xero"
