from django.conf import settings


def public_shop_path(shop):
    return '/shops/' + shop.business.slug


def public_shop_url(shop):
    base = str(
        getattr(settings, 'STOCKFLOW_PUBLIC_BASE_URL', '') or ''
    ).strip().rstrip('/')
    if not base:
        return ''
    return base + public_shop_path(shop)
