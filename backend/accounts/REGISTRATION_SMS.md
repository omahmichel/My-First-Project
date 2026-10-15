# Registration verification: email and SMS

This update adds Email/SMS selection on registration and channel switching on the code screen. SMS uses the configured mNotify key, sender ID and URL, with the OTP message type. Keep the provider account funded. Supported SMS numbers use Ghana's 0xxxxxxxxx or +233xxxxxxxxx formats.

Existing registration details are retained when switching channels. A replacement code invalidates the previous code. The resend cooldown and attempt limits still apply. A failed replacement restores the previous code and channel. A session challenge is required for SMS verification; only the phone supplied at registration can receive the code. No account or login tokens are issued until a correct code is entered.

The selected contact is recorded separately. SMS signup does not verify email. Email password recovery is withheld for SMS-only verified accounts until a successful email-code login verifies that address. Existing accounts retain their previous recovery behavior. Login remains email-based in this registration-only update; customers should still restore access to their email for future sign-in/recovery. SMS recovery and SMS sign-in are not included.

Per-recipient SMS attempts are additionally capped at five per hour in Django's configured cache. For multiple processes/instances, use a shared cache so that budget is shared; endpoint throttles and the database resend cooldown also remain active.

## Apply and validate locally (Windows CMD, project root)

Run the downloaded stockflow_registration_sms.py installer using the project Python. It checks source hashes before any write and backs up edited files. It does not change secrets, send SMS, run migrations, commit, push or deploy.

    backend\venv\Scripts\python.exe backend\manage.py check
    backend\venv\Scripts\python.exe backend\manage.py test accounts.test_registration_channels accounts.test_registration_otp accounts.test_password_reset accounts.test_login_otp
    npm --prefix frontend run build
    git status --short

If the installer stops because source or migrations changed, do not bypass it; supply the current files for a compatible update.

## Deploy

Commit only the changed registration/auth files and the new migration/test/guide. Push development, then deploy the backend with `python manage.py migrate --noinput` before its web server starts. The current Render start command already runs migrations; confirm the new accounts migration is applied. Deploy the frontend too.

The accounts migration also reconciles an existing auto-generated passkey index name with the current model definition. No existing user is marked email-verified by the migration.

## Verify on laptop and phone

Use a fresh test email and a phone you control. Request SMS, receive the actual handset message, enter the code, and confirm onboarding opens. Repeat email registration. On the email-code screen, wait for the cooldown, switch to SMS, and confirm the old email code fails while the new SMS code works. No password or code is persisted in browser registration state.

Check missing credit/network failure produces a clear error without creating an account. Test sign-in separately: it still sends email codes. Automated tests mock email/SMS delivery; they do not prove production handset delivery.
