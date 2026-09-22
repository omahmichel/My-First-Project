# TikTok and Snapchat account connections

This patch implements account authorization, verified account identity, encrypted credential storage, expiry/renewal, and local disconnect. It does not upload or publish any content. `deliveryAvailable` remains false. Facebook, Instagram and Shopify code is unchanged except the social channel summary and screen include the new connections.

## Configuration (StockFlow administrator only)

Both providers need app credentials and a registered HTTPS callback. Do not put secrets in React, source control, screenshots or chat. Existing Django dotenv loading can supply these environment variables without a settings.py edit:

- STOCKFLOW_TIKTOK_CLIENT_ID: TikTok client key
- STOCKFLOW_TIKTOK_CLIENT_SECRET
- STOCKFLOW_TIKTOK_REDIRECT_URI: https://YOUR-HOST/api/storefront/social/tiktok/callback/
- STOCKFLOW_SNAPCHAT_CLIENT_ID
- STOCKFLOW_SNAPCHAT_CLIENT_SECRET
- STOCKFLOW_SNAPCHAT_REDIRECT_URI: https://YOUR-HOST/api/storefront/social/snapchat/callback/
- STOCKFLOW_SOCIAL_RETURN_URL: the exact HTTPS StockFlow online-shop management page, without query or fragment
- STOCKFLOW_INTEGRATION_DATA_KEY: existing production encryption key; preserve this key across deployments

Use a stable HTTPS host reachable by the same browser that initiates authorization. The return page must be on the origin where the owner is signed in. Localhost HTTP is not a TikTok Web callback. No domain or provider account has been created by this patch.

TikTok: create a Web app in TikTok for Developers. Configure Login Kit and request user.info.basic and video.publish. Direct Post public visibility requires the applicable audit. A review interface with creator settings, editable post metadata, commercial disclosures and explicit consent remains to be implemented before publishing.

Snapchat: create the OAuth app through the Snap Business Dashboard, not the Snap Kit developer portal. Obtain Public Profile API allowlisting through Snap. Request snapchat-profile-api. This implementation connects the Public Profile belonging to the authorizing user using /v1/public_profiles/my_profile. Organization-wide selection is not implemented. Story/Spotlight upload and publication are not implemented by this patch.

Refresh is performed when the owner selects Verify connection and the access token is close to expiry. Disconnect removes local credentials and pending authorizations; it does not delete posts or revoke the app from the provider's own authorized-app settings.

## Verification

Run migrate, then:

    backend\venv\Scripts\python.exe backend\manage.py test storefront.test_short_video_connections --verbosity 2
    npm --prefix frontend run build

The automated provider responses are mocked; passing tests does not prove provider approval or live account connectivity. Check each live OAuth flow on phone and laptop after environment configuration. Verify denial/cancellation, reconnect, account identity, expired sessions and disconnect. Confirm no posts are created by connecting an account.

## Official sources reviewed 21 September 2026

- https://developers.tiktok.com/docs/en/login-kit-web
- https://developers.tiktok.com/docs/en/oauth-user-access-token-management
- https://developers.tiktok.com/docs/en/tiktok-api-v2-get-user-info
- https://developers.tiktok.com/docs/en/content-sharing-guidelines
- https://developers.snap.com/marketing-api/Public-Profile-API/GetStarted
- https://developers.snap.com/marketing-api/Public-Profile-API/Profiles
