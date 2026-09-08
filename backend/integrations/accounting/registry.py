from .quickbooks import QuickBooksAccountingProvider
from .xero import XeroAccountingProvider


PROVIDERS = {
    "quickbooks": QuickBooksAccountingProvider,
    "xero": XeroAccountingProvider,
}


def get_accounting_provider(provider_name):
    provider_class = PROVIDERS.get(str(provider_name or "").lower())
    if not provider_class:
        raise ValueError("Unsupported accounting provider.")
    return provider_class()


def accounting_capabilities():
    return {
        "authoritativeSource": "stockflow",
        "direction": "stockflow_to_accounting",
        "providers": [provider().capabilities() for provider in PROVIDERS.values()],
        "safety": {
            "accountingPlatformMayOverwriteStockFlow": False,
            "financialWritesIntoStockFlow": False,
        },
    }
