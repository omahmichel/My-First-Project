# StockFlow owner SMS alerts

Uses the existing server-side mNotify configuration. No API keys are added to the frontend.
All owner SMS preferences start disabled. Settings > SMS alerts lets the actual business
owner verify a Ghana phone number, choose event types, enable alerts, and review recent status.

## Behaviour

- Restocking: one SMS per product stock-in movement, including branch and staff.
- Adjustments: manual corrections, damage and returns, with previous/new stock and a shortened reason.
- Low stock: physical quantity crosses from above the branch threshold to at/below it. No repeats while it remains low. Recovers after restocking above the threshold. Existing low stock at activation is not replayed. Pending-payment reservations do not trigger physical low-stock alerts.
- Sales: one SMS when a sale is first confirmed, including credit/part-payment sales. Pending, cancelled and failed payments do not trigger it. Later debt repayments do not resend the sale SMS.
- Security: business-scoped HTTP 403 rejections, and five failed password sign-ins within 15 minutes for known owners/active members. Maximum one security SMS per business in a rolling hour. Unknown email addresses, global probes, expired-token 401 responses and unrelated tenants are not assigned to an owner. This is activity notification, not an intrusion-detection guarantee; a blocked request can also be a legitimate user's permission mistake.
- Messages are compact single-segment GSM-safe text (names/reasons may be shortened). Currency is GHS; event timestamps use UTC, also Ghana time.
- Failed stock/sale transactions roll back their queued messages. SMS network requests run only in the queue processor, never inside checkout or stock transactions.
- Only the actual owner can configure SMS or view its history. Phone verification: six digits, ten-minute validity, five attempts, one request per minute and three per hour per business.
- Changing owner/phone, disabling alerts or removing an event type cancels incompatible pending messages. An SMS already being submitted cannot be recalled.
- SENT means accepted by mNotify, not confirmed handset delivery. A timeout or interrupted submission is marked UNKNOWN and is not automatically resent because the provider may already have accepted it. Check mNotify for ambiguous outcomes. Pending messages older than 24 hours expire; verification codes expire after ten minutes. No bulk replay or manual resend of old alerts is included.
- The existing intelligence SMS and customer-debt reminders remain separate. If intelligence low-stock SMS is already enabled, disable that overlapping event in its preferences to avoid receiving both types.

## Apply and verify locally (Windows CMD, project root)

Run the supplied stockflow_owner_sms.py installer. It writes source and backups only.
It does not send SMS, migrate a database, access secrets, run Git, or deploy.

    backend\venv\Scripts\python.exe "%USERPROFILE%\Downloads\stockflow_owner_sms.py"
    backend\venv\Scripts\python.exe backend\manage.py check
    npm --prefix frontend run build
    git status --short

Tests supplied in owner_alerts use mocked SMS calls. The package was checked with Django
6.0.7 and DRF 3.17.1 using an isolated SQLite test database. Live PostgreSQL concurrency,
Render process supervision, real handset delivery and laptop/phone visual checks remain
deployment verification steps. The frontend build retains its existing large-chunk warning.
The uploaded project also has an unrelated accounts passkey index-name migration difference;
this patch does not generate or change that migration.

## Commit only these files after reviewing git diff

    git add backend/config/settings.py backend/config/urls.py backend/owner_alerts backend/run_with_owner_sms.py frontend/src/pages/settings/SettingsPage.jsx frontend/src/pages/settings/OwnerSmsPanel.jsx frontend/src/styles/owner-sms.css
    git commit -m "Add verified business-owner SMS alerts"
    git push origin development

Do not stage unrelated logs, secrets or untracked files with git add .

## Render activation (backend root directory is backend)

Deploy both backend and frontend from this commit. The new owner_alerts migration must be
applied to the production database before the feature or worker is used. On the paid backend,
add this to the existing Pre-Deploy Command without removing required existing commands:

    python manage.py migrate --noinput

If a migration pre-deploy command already exists, retain it. Otherwise the first deployment
can be followed immediately by the same command in Render Shell; SMS settings will remain
unavailable until the migration succeeds. These are additive tables, not changes to stock or
sales records. Use the existing backup policy before applying production migrations.

SMS requires a continuously running processor or an existing scheduler. Do not rely on an
open Render Shell for permanent processing.

Option A: run alongside the existing paid backend (included launcher):

1. Copy the current Render Start Command before changing it.
2. Prefix that exact executable command with: python run_with_owner_sms.py --
3. For example ONLY if the current command is gunicorn config.wsgi:application --bind 0.0.0.0:$PORT:

    python run_with_owner_sms.py -- gunicorn config.wsgi:application --bind 0.0.0.0:$PORT

Preserve all actual worker-class, bind, timeout and worker-count arguments. If the existing
start command contains shell operators or includes migrations, review it before adapting.
The launcher starts the web process and SMS processor and forwards shutdown to both. If either
exits unexpectedly it exits nonzero so the service can restart. The worker shares the paid
backend's memory/CPU; monitor capacity. No separate Render resource is created by this patch.

Option B: use an existing durable scheduler every minute:

    python manage.py process_owner_sms --limit 100

Or use a dedicated worker, if deliberately provisioned:

    python manage.py process_owner_sms --loop --interval 5

Choose one operating mode. Overlapping processors use conditional database claims to avoid
submitting the same queue item twice. Retain MNOTIFY_API_KEY, MNOTIFY_SENDER_ID and MNOTIFY_API_URL
in server environment variables. The existing provider timeout setting is reused.

## Hosted verification

1. Check migration and web/worker startup succeeded. The worker logs counts only, no phone numbers/codes.
2. Owner login > Settings > SMS alerts: request code, receive it, verify, select event types, enable and save.
3. Make an intentional small test restock and adjustment in a test business. Confirm staff/branch details.
4. Complete a test sale crossing the low-stock threshold. Confirm one sale SMS and one low-stock SMS.
5. Confirm the next sale while still low does not repeat low-stock SMS. Reopen/save records; no new sale SMS.
6. Check pending/cancelled payment flows do not generate completed-sale SMS.
7. Use a test staff account to attempt a restricted business action. Confirm the request is blocked and the owner receives at most one security SMS per hour.
8. Check Settings and SMS receipt on laptop and phone. SMS credits are consumed by verification and enabled events.

## Rollback

First restore the previous Render Start Command if the launcher was enabled. Revert the feature
commit and deploy the previous application. The new tables can be left in place; do not delete
stock/sales records or reverse unrelated migrations. Installer backups are stored in
.stockflow_backups/owner_sms_<timestamp> with original target files and a list of added files.
