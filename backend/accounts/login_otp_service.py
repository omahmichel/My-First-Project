import secrets
import logging
import math
from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth.models import update_last_login
from django.contrib.auth.hashers import check_password
from django.utils.crypto import constant_time_compare, salted_hmac
from django.core.mail import send_mail, get_connection
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import PendingLoginChallenge
from .serializers import UserSerializer


@dataclass
class LoginTokens:
    # Carries the verified account and JWT credentials after the second factor.

    user: object
    access: str
    refresh: str


class LoginEmailDeliveryError(Exception):
    # Signals that a login security code could not be delivered.

    pass


def _generate_otp():
    # Creates a cryptographically secure six-digit login code.
    return f"{secrets.randbelow(1_000_000):06d}"


OTP_HASH_PREFIX = "hmac-sha256$"
PENDING_OTP_PREFIX = "pending$"
SENDING_OTP_PREFIX = "sending$"


def _otp_hash(*, challenge_token, otp):
    # Uses a keyed HMAC so six-digit OTPs cannot be brute-forced from the DB alone.
    digest = salted_hmac(
        "stockflow.accounts.login_otp",
        f"{challenge_token}:{otp}",
        secret=settings.SECRET_KEY,
        algorithm="sha256",
    ).hexdigest()
    return f"{OTP_HASH_PREFIX}{digest}"


def _pending_otp_hash(*, retry=False):
    # Marks a password-verified challenge whose email code is not issued yet.
    return f"{PENDING_OTP_PREFIX}{'retry$' if retry else ''}{secrets.token_urlsafe(32)}"


def _otp_matches(*, challenge_token, otp, stored_hash):
    # Pending/in-flight delivery states can never satisfy the second factor.
    if stored_hash.startswith(
        (PENDING_OTP_PREFIX, SENDING_OTP_PREFIX)
    ):
        return False

    # Keeps short-lived pre-upgrade PBKDF2 challenges valid during deployment.
    if not stored_hash.startswith(OTP_HASH_PREFIX):
        return check_password(otp, stored_hash)

    expected_hash = _otp_hash(
        challenge_token=challenge_token,
        otp=otp,
    )
    return constant_time_compare(stored_hash, expected_hash)


def _challenge_token():
    # Creates an opaque browser-safe identifier that cannot authenticate alone.
    return secrets.token_urlsafe(32)


def _otp_expiry():
    return timezone.now() + timezone.timedelta(
        seconds=settings.LOGIN_OTP_EXPIRY_SECONDS,
    )


def _resend_available_at():
    return timezone.now() + timezone.timedelta(
        seconds=max(60, settings.LOGIN_OTP_RESEND_COOLDOWN_SECONDS),
    )


def _send_otp_email(*, user, otp):
    sent = send_mail(
        subject="Your StockFlow sign-in security code",
        message=(
            f"Hello {user.full_name or 'StockFlow user'},\n\n"
            "Use this six-digit security code to finish signing in to "
            "StockFlow:\n\n"
            f"{otp}\n\n"
            "The code expires in 10 minutes and can be used only for this "
            "sign-in. Do not share it with anyone.\n\n"
            "If you did not try to sign in, ignore this email and consider "
            "changing your password."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=(user.email,),
        fail_silently=False,
        connection=get_connection(timeout=min(getattr(settings, "EMAIL_TIMEOUT", 10) or 10, 20)),
    )

    if sent != 1:
        raise LoginEmailDeliveryError("Mail backend did not accept the message.")


@transaction.atomic
def issue_login_otp(user):
    # Creates/reuses the 2FA challenge without waiting for SMTP delivery.
    now = timezone.now()
    challenge = (
        PendingLoginChallenge.objects.select_for_update()
        .filter(user=user)
        .first()
    )

    if challenge and challenge.expires_at > now:
        delivery_required = challenge.otp_hash.startswith(
            PENDING_OTP_PREFIX,
        )
        return challenge, delivery_required

    if challenge is None:
        challenge = PendingLoginChallenge(user=user)

    challenge.challenge_token = _challenge_token()
    challenge.otp_hash = _pending_otp_hash()
    challenge.expires_at = _otp_expiry()
    challenge.resend_available_at = _resend_available_at()
    challenge.failed_attempts = 0
    challenge.save()

    return challenge, True


def challenge_timing(challenge):
    now = timezone.now()
    return {
        "expiresIn": max(0, math.ceil((challenge.expires_at - now).total_seconds())),
        "resendCooldown": max(0, math.ceil((challenge.resend_available_at - now).total_seconds())),
    }


def deliver_login_otp(challenge_token):
    return _deliver_code(challenge_token, replacement=False)


def resend_login_otp(challenge_token):
    challenge, _ = _deliver_code(challenge_token, replacement=True)
    return challenge


def _deliver_code(challenge_token, *, replacement):
    # SMTP must never hold a database transaction open. The sending hash is
    # a generation guard: a late delivery cannot overwrite a newer resend.
    now = timezone.now()
    with transaction.atomic():
        challenge = (PendingLoginChallenge.objects.select_for_update()
                     .select_related("user").filter(challenge_token=challenge_token).first())
        if not challenge or challenge.expires_at <= now or not challenge.user.is_active:
            raise serializers.ValidationError({"challengeId": "This sign-in request has expired. Please sign in again."})
        pending = challenge.otp_hash.startswith(PENDING_OTP_PREFIX)
        sending = challenge.otp_hash.startswith(SENDING_OTP_PREFIX)
        if not replacement and not pending and not sending:
            return challenge, False
        initial_delivery = not replacement and pending and not challenge.otp_hash.startswith("pending$retry$")
        if not initial_delivery and challenge.resend_available_at > now:
            seconds = challenge_timing(challenge)["resendCooldown"]
            raise serializers.ValidationError({"challengeId": f"Please wait {seconds} seconds before requesting another code."})
        old_hash = challenge.otp_hash.removeprefix(SENDING_OTP_PREFIX)
        otp = _generate_otp()
        while _otp_matches(challenge_token=challenge_token, otp=otp, stored_hash=old_hash):
            otp = _generate_otp()
        final_hash = _otp_hash(challenge_token=challenge_token, otp=otp)
        sending_hash = f"{SENDING_OTP_PREFIX}{final_hash}"
        challenge.otp_hash = sending_hash
        challenge.expires_at = _otp_expiry()
        challenge.resend_available_at = _resend_available_at()
        challenge.failed_attempts = 0
        challenge.save(update_fields=("otp_hash", "expires_at", "resend_available_at", "failed_attempts", "updated_at"))
        user = challenge.user
    try:
        _send_otp_email(user=user, otp=otp)
    except Exception as error:
        # Invalidate the failed generation, preserving its resend cooldown.
        PendingLoginChallenge.objects.filter(challenge_token=challenge_token, otp_hash=sending_hash).update(otp_hash=_pending_otp_hash(retry=True))
        logging.getLogger(__name__).warning("Login email delivery failed (%s).", type(error).__name__)
        raise LoginEmailDeliveryError from error
    updated = PendingLoginChallenge.objects.filter(challenge_token=challenge_token, otp_hash=sending_hash).update(otp_hash=final_hash)
    if not updated:
        raise serializers.ValidationError({"challengeId": "A newer code was requested. Use the most recently requested code."})
    challenge.otp_hash = final_hash
    return challenge, True


def verify_login_otp(*, challenge_token, otp):
    # Commits OTP attempt/expiry state before returning validation errors.
    invalid_message = "The security code is invalid or has expired."
    validation_error = None
    tokens = None

    with transaction.atomic():
        challenge = (
            PendingLoginChallenge.objects.select_for_update()
            .select_related("user")
            .filter(challenge_token=challenge_token)
            .first()
        )

        if not challenge:
            validation_error = {"otp": invalid_message}
        elif challenge.expires_at <= timezone.now():
            challenge.delete()
            validation_error = {"otp": invalid_message}
        elif not challenge.user.is_active:
            challenge.delete()
            validation_error = {"otp": invalid_message}
        elif challenge.otp_hash.startswith(
            (PENDING_OTP_PREFIX, SENDING_OTP_PREFIX)
        ):
            validation_error = {
                "otp": "The security code has not been delivered yet."
            }
        elif challenge.failed_attempts >= settings.LOGIN_OTP_MAX_ATTEMPTS:
            validation_error = {
                "otp": (
                    "Too many incorrect attempts. "
                    "Request a new security code."
                )
            }
        elif not _otp_matches(
            challenge_token=challenge.challenge_token,
            otp=otp,
            stored_hash=challenge.otp_hash,
        ):
            challenge.failed_attempts += 1
            challenge.save(update_fields=("failed_attempts", "updated_at"))

            attempts_left = max(
                0,
                settings.LOGIN_OTP_MAX_ATTEMPTS - challenge.failed_attempts,
            )

            if attempts_left == 0:
                validation_error = {
                    "otp": (
                        "Too many incorrect attempts. "
                        "Request a new security code."
                    )
                }
            else:
                validation_error = {
                    "otp": (
                        "The security code is incorrect. "
                        f"{attempts_left} attempt(s) remaining."
                    )
                }
        else:
            user = challenge.user
            challenge.delete()

            refresh = RefreshToken.for_user(user)
            update_last_login(None, user)

            tokens = LoginTokens(
                user=user,
                access=str(refresh.access_token),
                refresh=str(refresh),
            )

    if validation_error is not None:
        raise serializers.ValidationError(validation_error)

    return tokens


def login_token_response(tokens):
    # Returns the same authenticated user shape used throughout StockFlow.
    return {
        "message": "Sign-in verified successfully.",
        "user": UserSerializer(tokens.user).data,
        "access": tokens.access,
        "refresh": tokens.refresh,
    }
