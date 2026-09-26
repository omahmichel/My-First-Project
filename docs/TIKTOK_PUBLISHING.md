# Manual TikTok product-video publishing

Select an existing product video in Online Shop > Social publishing > TikTok > Prepare a TikTok video.
Only a business owner can list private video previews, prepare, publish, or check publication history.
No automatic TikTok dispatch has been enabled. Facebook, Instagram and Snapchat flows are unchanged.
This flow is shared across business types. It does not require automatic-publishing preferences.

## Setup

1. Apply migration storefront.0008_tiktokpublication.
2. Install FFmpeg including ffprobe on the backend machine. Verify with `ffprobe -version`.
   If it is not on PATH, configure STOCKFLOW_FFPROBE_PATH with the absolute executable path through
   `backend\venv\Scripts\python.exe backend\tools\secure_env.py set STOCKFLOW_FFPROBE_PATH`.
3. Set STOCKFLOW_TIKTOK_MEDIA_BASE_URL to a public HTTPS origin, without a path or trailing slash,
   using the existing secure_env.py set command. This is deliberately separate from OAuth redirects.
   The origin must route /api/storefront/social/tiktok/media/ to Django and be verified in the
   SAME TikTok application's URL properties. The latest temporary tunnel was flagged by Chrome;
   investigate that warning before using it for live media delivery. Local UI testing can continue.
4. Restart Django after environment changes.
5. Connect and verify the desired TikTok account with video.publish permission.
6. Use a private test account for unaudited Direct Post, with Only me selected explicitly.
   A public account cannot receive unaudited Direct Post submissions. Public API posts require TikTok audit.
   A registered public profile and a developer app are separate things.

## Behaviour

The latest creator settings are fetched when preparing AND before submitting. Caption, privacy,
interaction permissions, commercial disclosures, AI disclosure and affirmative consent are sent
only after the owner presses Post to TikTok. Privacy has no default; interactions start disabled.
Server-side ffprobe inspects a bounded local copy of the stored video, checks duration and dimensions,
and applies the creator's duration limit. No user-provided external media URL is fetched.

Stored product videos use PULL_FROM_URL. A signed URL grants one-hour read access to the exact
consented publication/video version. Expired signatures, unsubmitted drafts and replaced videos
are rejected. Keep the public origin and servers available until TikTok finishes processing.
Video removal/replacement while processing can cause publication failure.

Each draft is claimed atomically once. Repeated submissions of that ID return its saved state.
Repeated previews reuse a recent draft. Pending or unknown attempts block another preview of the
same video version/account. Network ambiguity is recorded as unknown and is never auto-retried.
Check TikTok and seek support to reconcile unknown outcomes; do not blindly resubmit.
The most recent 20 submitted attempts appear in history. Processing status is polled every 15 seconds
while the panel is open; manual status checks also work after reloading. Initialization alone is
not reported as published. PUBLISH_COMPLETE is required.

Access tokens remain server-side. If access expires, use Verify connection to refresh it.
Consent drafts expire after ten minutes. Changing a connected account invalidates its old drafts.
Audit rows retain caption, selected metadata, account ID, tracking ID and outcome; no tokens are stored there.

## Validation

Run from project root:

    backend\venv\Scripts\python.exe backend\manage.py migrate
    backend\venv\Scripts\python.exe backend\manage.py test storefront.test_tiktok_publishing storefront.test_short_video_connections
    npm --prefix frontend run build

19 tests cover owner boundaries, missing consent, audience restrictions, interactions,
commercial disclosure, caption length, changed video/account, duration, duplicate attempts,
unknown outcomes, signed media access, expired previews, status confirmation and existing OAuth.
Tests mock TikTok. They do not establish live provider acceptance or audit approval.
Check the UI on laptop and phone before committing. Do not commit secrets or local environment files.

References:
https://developers.tiktok.com/docs/en/content-sharing-guidelines
https://developers.tiktok.com/docs/en/content-posting-api-reference-direct-post
https://developers.tiktok.com/docs/en/content-posting-api-reference-get-video-status
https://developers.tiktok.com/docs/en/content-posting-api-media-transfer-guide
