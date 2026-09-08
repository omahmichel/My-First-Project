from .shopify import ShopifyCommerceProvider
from .woocommerce import WooCommerceProvider


PROVIDERS = {
    "shopify": ShopifyCommerceProvider,
    "woocommerce": WooCommerceProvider,
}


def get_commerce_provider(provider_name):
    provider_class = PROVIDERS.get(str(provider_name or "").lower())
    if not provider_class:
        raise ValueError("Unsupported commerce provider.")
    return provider_class()


def commerce_capabilities():
    return {
        "authoritativeInventory": "stockflow",
        "catalogDirection": "stockflow_to_commerce",
        "inventoryDirection": "stockflow_to_commerce",
        "orderImportMode": "staged_review",
        "providers": [
            provider_class().capabilities()
            for provider_class in PROVIDERS.values()
        ],
        "safety": {
            "externalPlatformMayOverwriteStockFlowInventory": False,
            "stagedOrdersMutateStock": False,
            "stagedOrdersCreateSales": False,
        },
    }
