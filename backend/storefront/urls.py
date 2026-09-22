from django.urls import path

from .views import PublicShopAPIView, PublicShopOrderAPIView

app_name = 'storefront'

from .activity import PublicActivityAPIView

from .management import ShopSettingsAPIView

from .listings import ShopListingsAPIView, ShopListingAPIView

from .orders import ShopOrdersAPIView, ShopOrderAPIView, ShopOrderCancelAPIView

from .completion import ShopOrderCompleteAPIView

from .social import SocialChannelsAPIView, SocialChannelAPIView, SocialJobsAPIView
from .facebook_social import (
    FacebookConnectAPIView,
    FacebookOAuthCallbackAPIView,
    FacebookPageSelectionAPIView,
    FacebookDisconnectAPIView,
)
from .facebook_delivery import FacebookPublishJobAPIView
from .instagram_delivery import InstagramMediaAPIView, InstagramPublishJobAPIView

urlpatterns = [
    path('businesses/<uuid:business_id>/storefront/social/facebook/connect/', FacebookConnectAPIView.as_view(), name='social-facebook-connect'),
    path('businesses/<uuid:business_id>/storefront/social/facebook/select-page/', FacebookPageSelectionAPIView.as_view(), name='social-facebook-select-page'),
    path('businesses/<uuid:business_id>/storefront/social/facebook/connection/', FacebookDisconnectAPIView.as_view(), name='social-facebook-disconnect'),
    path('storefront/social/facebook/callback/', FacebookOAuthCallbackAPIView.as_view(), name='social-facebook-callback'),
    path('businesses/<uuid:business_id>/storefront/social/channels/', SocialChannelsAPIView.as_view(), name='social-channels'),
    path('businesses/<uuid:business_id>/storefront/social/channels/<str:platform>/', SocialChannelAPIView.as_view(), name='social-channel'),
    path('businesses/<uuid:business_id>/storefront/social/jobs/', SocialJobsAPIView.as_view(), name='social-jobs'),
    path('businesses/<uuid:business_id>/storefront/social/jobs/<uuid:job_id>/publish-facebook/', FacebookPublishJobAPIView.as_view(), name='social-facebook-publish-job'),
    path('businesses/<uuid:business_id>/storefront/social/jobs/<uuid:job_id>/publish-instagram/', InstagramPublishJobAPIView.as_view(), name='social-instagram-publish-job'),
    path('storefront/social/instagram/media/', InstagramMediaAPIView.as_view(), name='social-instagram-media'),
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

from .short_video_connections import (
    ShortVideoConnectAPIView, ShortVideoCallbackAPIView,
    ShortVideoFinishAPIView, ShortVideoConnectionAPIView,
)
for provider in ('tiktok', 'snapchat'):
    urlpatterns += [
        path('businesses/<uuid:business_id>/storefront/social/' + provider + '/connect/', ShortVideoConnectAPIView.as_view(), {'provider': provider}, name='social-' + provider + '-connect'),
        path('storefront/social/' + provider + '/callback/', ShortVideoCallbackAPIView.as_view(), {'provider': provider}, name='social-' + provider + '-callback'),
        path('businesses/<uuid:business_id>/storefront/social/' + provider + '/finish/', ShortVideoFinishAPIView.as_view(), {'provider': provider}, name='social-' + provider + '-finish'),
        path('businesses/<uuid:business_id>/storefront/social/' + provider + '/connection/', ShortVideoConnectionAPIView.as_view(), {'provider': provider}, name='social-' + provider + '-connection'),
    ]
