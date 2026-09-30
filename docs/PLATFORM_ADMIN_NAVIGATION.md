# Integrated platform administration

Administration uses StockFlow's existing Sidebar and AppLayout. Platform routes
have their own administrator guard and bypass business subscription/onboarding
requirements. Business operations retain their existing access checks. The shared
sidebar includes Administration only for platform administrators. Existing business
links are available when an authorised business is selected. No second sidebar.

Routes: /platform-admin/overview, users, businesses, subscriptions,
administrators (Add Admin), bugs, activity and notifications.
The old /platform-admin address redirects to overview.

Add Admin opens with a new-administrator registration form: full name, email, optional phone, new password, password confirmation and the authorising administrator password. New accounts have full staff + superuser access, no business is created, and normal login verification remains in place. Passwords use Django validation and hashing. Case-insensitive duplicate emails are rejected. Creating an account requires a durable audit write in the same transaction.

The existing-account section also searches active accounts. Select an account, review its email
and ID, enter your own administrator password and confirm the grant. The server
requires an active staff + superuser, checks the current password, enforces a grant
rate limit and writes an audit entry in the same transaction as the permission
change. No password is stored in activity events. It grants full staff and
superuser privileges, including Django administration; it is not a limited role.
No account is promoted by the installer. New people can be registered directly using the form; no business is required. The recipient
should sign out and sign in again after a successful grant.

Bugs includes system error/critical events and newly delivered support reports.
The migration imports existing captured system errors. Prior support emails are
not imported. Existing support mail delivery is preserved: a report is added to
Bugs after successful mail delivery. Email failures retain the existing error
response and can generate an application-error event. Raw automatic exception
messages and request contents remain excluded. Support descriptions are explicit
user-submitted text, visible only to platform administrators, rendered as text.

Statuses are Open, Investigating and Resolved. Updates use expected-state checks
to avoid overwriting another administrator's change. Changes are audited. Grouped
activity repeats share a bug; new event rows can create separate bugs. Security
warnings remain in Activity/Notifications, not every warning is a software bug.
No bug or administrator deletion/revocation UI is included in this update.

Installation: stop Django, apply installer from project root, migrate, run tests,
build frontend and restart Django. Installer checks current file hashes and backs
up changes. It does not change database records or run Git commands. Migrations
create BugReport and import existing error rows without deleting original events.

Validation: 45 backend tests passed under isolated Django 5.2 / Python 3.12; run
again with the project's installed Django version. Vite production build passed.
DOM interaction checks with mocked APIs covered the shared sidebar, every section,
no-business administrator, confirmation controls, notification-to-activity links
and ordinary-user rejection. Actual desktop/mobile appearance remains to be
verified on the user's laptop and phone.
