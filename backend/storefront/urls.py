from django.urls import path

from .views import PublicShopAPIView, PublicShopOrderAPIView

app_name = 'storefront'

from .activity import PublicActivityAPIView

from .management import ShopSettingsAPIView

from .listings import ShopListingsAPIView, ShopListingAPIView

from .orders import ShopOrdersAPIView, ShopOrderAPIView, ShopOrderCancelAPIView

from .completion import ShopOrderCompleteAPIView

from .social import SocialChannelsAPIView, SocialChannelAPIView, SocialJobsAPIView

urlpatterns = [
    path('businesses/<uuid:business_id>/storefront/social/channels/', SocialChannelsAPIView.as_view(), name='social-channels'),
    path('businesses/<uuid:business_id>/storefront/social/channels/<str:platform>/', SocialChannelAPIView.as_view(), name='social-channel'),
    path('businesses/<uuid:business_id>/storefront/social/jobs/', SocialJobsAPIView.as_view(), name='social-jobs'),
    path('businesses/<uuid:business_id>/storefront/orders/<uuid:order_id>/complete/', ShopOrderCompleteAPIView.as_view(), name='shop-order-complete'),
    path('businesses/<uuid:business_id>/storefront/orders/', ShopOrdersAPIView.as_view(), name='shop-orders'),
    path('businesses/<uuid:business_id>/storefront/orders/<uuid:order_id>/', ShopOrderAPIView.as_view(), name='shop-order'),
    path('businesses/<uuid:business_id>/storefront/orders/<uuid:order_id>/cancel/', ShopOrderCancelAPIView.as_view(), name='shop-order-cancel'),
    path('businesses/<uuid:business_id>/storefront/listings/', ShopListingsAPIView.as_view(), name='shop-listings'),
    path('businesses/<uuid:business_id>/storefront/listings/<uuid:product_id>/', ShopListingAPIView.as_view(), name='shop-listing'),
    path('businesses/<uuid:business_id>/storefront/settings/', ShopSettingsAPIView.as_view(), name='shop-settings'),
    path('shops/<slug:shop_slug>/activity/', PublicActivityAPIView.as_view(), name='public-activity'),
    path('shops/<slug:shop_slug>/', PublicShopAPIView.as_view(), name='public-shop'),
    path('shops/<slug:shop_slug>/orders/', PublicShopOrderAPIView.as_view(), name='public-order-create'),
]
