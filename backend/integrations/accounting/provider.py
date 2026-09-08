class AccountingProviderError(Exception):
    pass


class BaseAccountingProvider:
    provider_name = ""
    display_name = ""
    live_connection_available = False

    def capabilities(self):
        return {
            "provider": self.provider_name,
            "displayName": self.display_name,
            "foundationReady": True,
            "liveConnectionAvailable": self.live_connection_available,
            "direction": "stockflow_to_accounting",
            "entities": [
                "customers", "suppliers", "products",
                "sales", "payments", "purchases",
            ],
        }

    def connect(self, *args, **kwargs):
        raise AccountingProviderError(
            f"{self.display_name} live connection is not configured yet."
        )

    def sync(self, *args, **kwargs):
        raise AccountingProviderError(
            f"{self.display_name} live sync is not configured yet."
        )
