import secrets
from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth.models import update_last_login
from django.contrib.auth.hashers import check_password
from django.utils.crypto import constant_time_compare, salted_hmac
from django.core.mail import send_mail
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


def _pending_otp_hash():
    # Marks a password-verified challenge whose email code is not issued yet.
    return f"{PENDING_OTP_PREFIX}{secrets.token_urlsafe(32)}"


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
        seconds=settings.LOGIN_OTP_RESEND_COOLDOWN_SECONDS,
    )


def _send_otp_email(*, user, otp):
    send_mail(
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
    )


def _restore_challenge(challenge, snapshot):
    # Restores the previous usable challenge if replacement delivery fails.
    if snapshot is None:
        challenge.delete()
        return

    for field_name, value in snapshot.items():
        setattr(challenge, field_name, value)

    challenge.save(
        update_fields=(
            "challenge_token",
            "otp_hash",
            "expires_at",
            "resend_available_at",
            "failed_attempts",
            "updated_at",
        )
    )


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
    challenge.resend_available_at = now
    challenge.failed_attempts = 0
    challenge.save()

    return challenge, True


def deliver_login_otp(challenge_token):
    # Keeps the database lock short; SMTP runs only after the transaction commits.
    now = timezone.now()

    with transaction.atomic():
        challenge = (
            PendingLoginChallenge.objects.select_for_update()
            .select_related("user")
            .filter(challenge_token=challenge_token)
            .first()
        )

        if not challenge or challenge.expires_at <= now:
            if challenge:
                challenge.delete()
            raise serializers.ValidationError(
                {"challengeId": "This sign-in request is no longer valid."}
            )

        if not challenge.user.is_active:
            challenge.delete()
            raise serializers.ValidationError(
                {"challengeId": "This sign-in request is no longer valid."}
            )

        if challenge.otp_hash.startswith(SENDING_OTP_PREFIX):
            raise serializers.ValidationError(
                {
                    "challengeId": (
                        "Security code delivery is already in progress."
                    )
                }
            )

        if not challenge.otp_hash.startswith(PENDING_OTP_PREFIX):
            return challenge, False

        snapshot = {
            "challenge_token": challenge.challenge_token,
            "otp_hash": challenge.otp_hash,
            "expires_at": challenge.expires_at,
            "resend_available_at": challenge.resend_available_at,
            "failed_attempts": challenge.failed_attempts,
        }

        otp = _generate_otp()
        final_otp_hash = _otp_hash(
            challenge_token=challenge.challenge_token,
            otp=otp,
        )
        sending_otp_hash = f"{SENDING_OTP_PREFIX}{final_otp_hash}"
        challenge.otp_hash = sending_otp_hash
        challenge.expires_at = _otp_expiry()
        challenge.resend_available_at = _resend_available_at()
        challenge.failed_attempts = 0
        challenge.save(
            update_fields=(
                "otp_hash",
                "expires_at",
                "resend_available_at",
                "failed_attempts",
                "updated_at",
            )
        )
        user = challenge.user

    try:
        _send_otp_email(user=user, otp=otp)
    except Exception as error:
        with transaction.atomic():
            current = (
                PendingLoginChallenge.objects.select_for_update()
                .filter(challenge_token=challenge_token)
                .first()
            )
            if current and current.otp_hash == sending_otp_hash:
                _restore_challenge(current, snapshot)
        raise LoginEmailDeliveryError from error

    with transaction.atomic():
        challenge = (
            PendingLoginChallenge.objects.select_for_update()
            .select_related("user")
            .filter(challenge_token=challenge_token)
            .first()
        )
        if not challenge:
            raise serializers.ValidationError(
                {"challengeId": "This sign-in request is no longer valid."}
            )
        if challenge.otp_hash == sending_otp_hash:
            challenge.otp_hash = final_otp_hash
            challenge.save(update_fields=("otp_hash", "updated_at"))

    return challenge, True


def resend_login_otp(challenge_token):
    # Replaces the active OTP while keeping SMTP outside the database lock.
    now = timezone.now()

    with transaction.atomic():
        challenge = (
            PendingLoginChallenge.objects.select_for_update()
            .select_related("user")
            .filter(challenge_token=challenge_token)
            .first()
        )

        if not challenge:
            raise serializers.ValidationError(
                {"challengeId": "This sign-in request is no longer valid."}
            )

        if not challenge.user.is_active:
            challenge.delete()
            raise serializers.ValidationError(
                {"challengeId": "This sign-in request is no longer valid."}
            )

        if challenge.otp_hash.startswith(SENDING_OTP_PREFIX):
            raise serializers.ValidationError(
                {
                    "challengeId": (
                        "Security code delivery is already in progress."
                    )
                }
            )

        if challenge.otp_hash.startswith(PENDING_OTP_PREFIX):
            raise serializers.ValidationError(
                {
                    "challengeId": (
                        "The first security code has not been delivered yet."
                    )
                }
            )

        if challenge.resend_available_at > now:
            wait_seconds = max(
                1,
                int((challenge.resend_available_at - now).total_seconds()),
            )
            raise serializers.ValidationError(
                {
                    "challengeId": (
                        "Please wait before requesting another security code. "
                        f"Try again in {wait_seconds} seconds."
                    )
                }
            )

        snapshot = {
            "challenge_token": challenge.challenge_token,
            "otp_hash": challenge.otp_hash,
            "expires_at": challenge.expires_at,
            "resend_available_at": challenge.resend_available_at,
            "failed_attempts": challenge.failed_attempts,
        }

        otp = _generate_otp()
        final_otp_hash = _otp_hash(
            challenge_token=challenge.challenge_token,
            otp=otp,
        )
        sending_otp_hash = f"{SENDING_OTP_PREFIX}{final_otp_hash}"
        challenge.otp_hash = sending_otp_hash
        challenge.expires_at = _otp_expiry()
        challenge.resend_available_at = _resend_available_at()
        challenge.failed_attempts = 0
        challenge.save(
            update_fields=(
                "otp_hash",
                "expires_at",
                "resend_available_at",
                "failed_attempts",
                "updated_at",
            )
        )
        user = challenge.user

    try:
        _send_otp_email(user=user, otp=otp)
    except Exception as error:
        with transaction.atomic():
            current = (
                PendingLoginChallenge.objects.select_for_update()
                .filter(challenge_token=challenge_token)
                .first()
            )
            if current and current.otp_hash == sending_otp_hash:
                _restore_challenge(current, snapshot)
        raise LoginEmailDeliveryError from error

    with transaction.atomic():
        challenge = (
            PendingLoginChallenge.objects.select_for_update()
            .select_related("user")
            .filter(challenge_token=challenge_token)
            .first()
        )
        if not challenge:
            raise serializers.ValidationError(
                {"challengeId": "This sign-in request is no longer valid."}
            )
        if challenge.otp_hash == sending_otp_hash:
            challenge.otp_hash = final_otp_hash
            challenge.save(update_fields=("otp_hash", "updated_at"))

    return challenge


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
