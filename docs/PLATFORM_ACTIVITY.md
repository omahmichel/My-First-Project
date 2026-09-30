# StockFlow platform activity

Available only to active Django staff + superuser accounts through the existing
platform administrator API. No public registration or new administrator grants.

## Installation
Stop Django, apply the guarded installer from the project root, run
`python backend/manage.py migrate`, run the platform_events and
accounts.test_platform_admin tests, build the frontend, and restart Django.
Run `python backend/manage.py record_system_check` to record a first system check.
Passwords, permissions, subscription state and payment state are not changed.
The migration creates an event table and imports existing platform status audit
entries, retaining the originals. Other historical actions cannot be reconstructed.

## Capture coverage
- API and Django admin request outcomes, authentication steps, validation failures,
  permission denials, server errors and throttling responses.
- Committed save/delete/relationship changes in accounts, businesses, customers,
  inventory, sales, storefront, integrations and intelligence. Transient OTP and
  credential-challenge records and selected noisy internal records are excluded.
- Existing payout, reservation cleanup, debt reminder, webhook, intelligence and
  multibranch management jobs: start, completion and uncaught failure.
- Django security logger and error-level domain application log messages.
- `manage.py check` completion/failure; `record_system_check` records issue IDs
  and severity without diagnostic messages. Checks must actually be run; no
  scheduler is installed and no production configuration is asserted as safe.
- Authenticated browser runtime-error reports, explicitly marked browser-report.
  Reports are untrusted diagnostic signals, not proof of a server error or attack.
- Failed requests to selected sensitive paths such as /.env and /.git/ are marked
  suspected probes. Ordinary 401/403/429 responses are warnings, not confirmed attacks.

Successful activity/notification reads do not log themselves. Repeated failed
requests and read events are grouped per minute. Each grouped row retains its
first request ID, first timestamp, latest timestamp and occurrence count.
Some operations produce a request event plus one or more record events; these
are different layers of evidence rather than separate business transactions.

The activity view refreshes every 30 seconds while visible. The notification
menu refreshes every 30 seconds while open and visible, and shows the latest five
warning/error/critical groups from the last 24 hours along with business alerts.
It is a status snapshot, not an unread inbox. Older events remain searchable.

## Data handling and boundaries
No passwords, tokens, OTPs, request/response bodies, query strings, raw URLs,
exception messages, stack traces or arbitrary model values are stored in events.
Safe identifiers, status enums, field names, check IDs and exception class names
are retained. Administrator-only output resolves current business and user names.
Peer IP is REMOTE_ADDR only: behind a proxy it may identify the proxy, not the
customer. Forwarded headers are deliberately not trusted by this feature.

Events depend on the application and database being available. A capture failure
emits a constant server warning and does not fail the business transaction.
This database log is not a tamper-proof external audit archive. A full compromise
or database outage may prevent capture. Bulk updates bypass Django model signals;
request/job outcomes still capture those operations, but not each affected row.
No browser clicks without API calls, operating-system events, reverse-proxy/WAF
blocks, or provider events that never reach StockFlow are collected. Hosting-level
security monitoring must be integrated separately after hosting is selected.
This feature records detected signals; it does not detect or block every attack.

Retention is manual. Preview old rows with
`python backend/manage.py prune_platform_events --days 90`.
Add `--apply` only when deletion is intended; the minimum is seven days.
No deletion schedule is installed. Before high-volume deployment, measure event
write load, choose retention, and connect an external durable monitoring service.

## Local verification
Open Activity log as platform admin. Run `record_system_check`, then verify a
system event appears. Make an ordinary allowed business edit and verify its
record/request entries. Try filters and the three-dot notification menu on desktop
and mobile. Avoid manufacturing payments or attack traffic for UI testing.

Packaged checks: 31 Django tests and Vite production build passed in an isolated
Django 5.2 / Python 3.12 environment. Run the supplied commands against your
installed Django version too. Existing large-bundle warnings remain.
