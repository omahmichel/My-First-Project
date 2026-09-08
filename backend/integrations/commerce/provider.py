class CommerceProviderError(Exception):
    pass


class BaseCommerceProvider:
    provider_name = ""
    display_name = ""
    live_connection_available = False

    def capabilities(self):
        return {
            "provider": self.provider_name,
            "displayName": self.display_name,
            "foundationReady": True,
            "liveConnectionAvailable": self.live_connection_available,
            "authoritativeInventory": "stockflow",
            "catalogDirection": "stockflow_to_commerce",
            "inventoryDirection": "stockflow_to_commerce",
            "orderImportMode": "staged_review",
            "directExternalStockMutation": False,
        }

    def connect(self, *args, **kwargs):
        raise CommerceProviderError(
            f"{self.display_name} live connection is not configured yet."
        )

    def push_product(self, *args, **kwargs):
        raise CommerceProviderError(
            f"{self.display_name} product sync is not configured yet."
        )

    def push_inventory(self, *args, **kwargs):
        raise CommerceProviderError(
            f"{self.display_name} inventory sync is not configured yet."
        )

    def fetch_orders(self, *args, **kwargs):
        raise CommerceProviderError(
            f"{self.display_name} order import is not configured yet."
        )
