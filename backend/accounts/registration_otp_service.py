import secrets
import uuid
from django.core.cache import cache
from django.utils.crypto import salted_hmac
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import (
    check_password,
    make_password,
)
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import PendingRegistration
from .serializers import UserSerializer

User = get_user_model()


@dataclass
class RegistrationTokens:
    # Carries the newly verified account and its JWT credentials.

    user: object
    access: str
    refresh: str


class RegistrationEmailDeliveryError(Exception):
    # Signals that the pending registration could not receive its OTP.

    pass


def _generate_otp(previous_hash=None):
    # Creates a secure code that differs from the active code when replacing it.
    for _ in range(20):
        otp = f"{secrets.randbelow(1_000_000):06d}"

        if not previous_hash or not check_password(otp, previous_hash):
            return otp

    raise RuntimeError("Could not generate a replacement verification code.")


def _otp_expiry():
    # Calculates the configured OTP expiry timestamp.
    return timezone.now() + timedelta(
        seconds=settings.REGISTRATION_OTP_EXPIRY_SECONDS,
    )


def _resend_available_at():
    # Calculates when another OTP may be requested.
    return timezone.now() + timedelta(
        seconds=settings.REGISTRATION_OTP_RESEND_COOLDOWN_SECONDS,
    )


def _send_otp_email(*, email, full_name, otp):
    # Sends the verification code through StockFlow's configured mail backend.
    send_mail(
        subject="Verify your StockFlow email address",
        message=(
            f"Hello {full_name or 'StockFlow user'},\n\n"
            "Use this six-digit code to verify your email address:\n\n"
            f"{otp}\n\n"
            "The code expires in 10 minutes. Do not share it with anyone.\n\n"
            "If you did not start this registration, ignore this email."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=(email,),
        fail_silently=False,
    )


def _send_registration_code(*, pending, otp):
    if pending.delivery_channel == "email":
        return _send_otp_email(email=pending.email, full_name=pending.full_name, otp=otp)
    from sales.debt_reminder_service import normalize_ghana_phone
    from .registration_sms import send_registration_sms
    try:
        phone = normalize_ghana_phone(pending.phone)
    except ValueError:
        raise serializers.ValidationError({"phone": "Add a valid Ghana phone number to your registration before choosing SMS."})
    # Per-recipient budget supplements the endpoint/IP limits and resend cooldown.
    key = "registration-sms:" + salted_hmac("registration-sms", phone).hexdigest()
    if cache.add(key, 1, 3600):
        count = 1
    else:
        count = cache.incr(key)
    if count > 5:
        raise serializers.ValidationError({"detail": "SMS request limit reached. Please use email or try again later."})
    send_registration_sms(recipient=phone, message=(
        f"Your StockFlow registration code is {otp}. "
        f"Expires in {settings.REGISTRATION_OTP_EXPIRY_SECONDS // 60} minutes. Do not share this code."
    ))


def _check_challenge(pending, challenge_id, channel=None):
    # Legacy email-only clients remain compatible; SMS always requires the session token.
    if challenge_id is not None and str(challenge_id) != str(pending.challenge_token):
        raise serializers.ValidationError({"detail": "This registration session changed. Please register again."})
    if (pending.delivery_channel == "sms" or channel == "sms") and not challenge_id:
        raise serializers.ValidationError({"detail": "Please restart registration to use SMS verification."})


def registration_delivery_response(pending):
    return {"email": pending.email, "channel": pending.delivery_channel,
            "challengeId": str(pending.challenge_token),
            "destination": ("••••" + pending.phone[-4:] if pending.delivery_channel == "sms" else pending.email),
            "resendAvailableAt": pending.resend_available_at.isoformat(),
            "message": "Verification code sent by " + ("SMS." if pending.delivery_channel == "sms" else "email.")}


def _restore_pending_registration(pending, snapshot):
    # Restores the previous valid code when replacement delivery fails.
    if snapshot is None:
        pending.delete()
        return

    for field_name, value in snapshot.items():
        setattr(pending, field_name, value)

    pending.save(
        update_fields=(
            "delivery_channel",
            "challenge_token",
            "full_name",
            "phone",
            "password_hash",
            "otp_hash",
            "expires_at",
            "resend_available_at",
            "failed_attempts",
            "updated_at",
        )
    )


@transaction.atomic
def issue_registration_otp(validated_data):
    # Creates or replaces one pending registration after cooldown validation.
    email = validated_data["email"]
    now = timezone.now()

    pending = (
        PendingRegistration.objects.select_for_update()
        .filter(email=email)
        .first()
    )

    if pending and pending.resend_available_at > now:
        wait_seconds = max(
            1,
            int((pending.resend_available_at - now).total_seconds()),
        )
        raise serializers.ValidationError(
            {
                "email": (
                    "A verification code was already sent. "
                    f"Try again in {wait_seconds} seconds."
                )
            }
        )

    snapshot = None

    if pending:
        snapshot = {
            "delivery_channel": pending.delivery_channel,
            "challenge_token": pending.challenge_token,
            "full_name": pending.full_name,
            "phone": pending.phone,
            "password_hash": pending.password_hash,
            "otp_hash": pending.otp_hash,
            "expires_at": pending.expires_at,
            "resend_available_at": pending.resend_available_at,
            "failed_attempts": pending.failed_attempts,
        }
    else:
        pending = PendingRegistration(email=email)

    otp = _generate_otp(
        snapshot["otp_hash"] if snapshot else None,
    )
    pending.delivery_channel = validated_data.get("channel", "email")
    pending.challenge_token = uuid.uuid4()
    pending.full_name = validated_data["full_name"]
    pending.phone = validated_data.get("phone", "")
    pending.password_hash = make_password(validated_data["password"])
    pending.otp_hash = make_password(otp)
    pending.expires_at = _otp_expiry()
    pending.resend_available_at = _resend_available_at()
    pending.failed_attempts = 0
    pending.save()

    try:
        _send_registration_code(pending=pending, otp=otp)
    except serializers.ValidationError:
        raise
    except Exception as error:
        _restore_pending_registration(pending, snapshot)
        raise RegistrationEmailDeliveryError from error

    return pending


@transaction.atomic
def resend_registration_otp(email, *, channel=None, challenge_id=None):
    # Replaces the current OTP without changing the submitted account details.
    now = timezone.now()
    pending = (
        PendingRegistration.objects.select_for_update()
        .filter(email=email)
        .first()
    )

    if not pending:
        raise serializers.ValidationError(
            {
                "email": (
                    "No pending registration was found. "
                    "Start the registration again."
                )
            }
        )

    _check_challenge(pending, challenge_id, channel)

    if User.objects.filter(email__iexact=email).exists():
        pending.delete()
        raise serializers.ValidationError(
            {"email": "An account with this email already exists."}
        )

    if pending.resend_available_at > now:
        wait_seconds = max(
            1,
            int((pending.resend_available_at - now).total_seconds()),
        )
        raise serializers.ValidationError(
            {
                "email": (
                    "Please wait before requesting another code. "
                    f"Try again in {wait_seconds} seconds."
                )
            }
        )

    snapshot = {
        "delivery_channel": pending.delivery_channel,
        "challenge_token": pending.challenge_token,
        "full_name": pending.full_name,
        "phone": pending.phone,
        "password_hash": pending.password_hash,
        "otp_hash": pending.otp_hash,
        "expires_at": pending.expires_at,
        "resend_available_at": pending.resend_available_at,
        "failed_attempts": pending.failed_attempts,
    }

    if channel is not None:
        pending.delivery_channel = channel
    otp = _generate_otp(pending.otp_hash)
    pending.otp_hash = make_password(otp)
    pending.expires_at = _otp_expiry()
    pending.resend_available_at = _resend_available_at()
    pending.failed_attempts = 0
    pending.save(
        update_fields=(
            "otp_hash",
            "delivery_channel",
            "expires_at",
            "resend_available_at",
            "failed_attempts",
            "updated_at",
        )
    )

    try:
        _send_registration_code(pending=pending, otp=otp)
    except serializers.ValidationError:
        raise
    except Exception as error:
        _restore_pending_registration(pending, snapshot)
        raise RegistrationEmailDeliveryError from error

    return pending


def verify_registration_otp(*, email, otp, challenge_id=None):
    # Commits security counters and expiry cleanup before returning errors.
    validation_error = None
    tokens = None
    invalid_message = (
        "The verification code is invalid or has expired."
    )

    with transaction.atomic():
        pending = (
            PendingRegistration.objects.select_for_update()
            .filter(email=email)
            .first()
        )

        if pending:
            _check_challenge(pending, challenge_id)

        if not pending:
            validation_error = {"otp": invalid_message}

        elif pending.expires_at <= timezone.now():
            pending.delete()
            validation_error = {"otp": invalid_message}

        elif (
            pending.failed_attempts
            >= settings.REGISTRATION_OTP_MAX_ATTEMPTS
        ):
            validation_error = {
                "otp": (
                    "Too many incorrect attempts. "
                    "Request a new verification code."
                )
            }

        elif not check_password(otp, pending.otp_hash):
            pending.failed_attempts += 1
            pending.save(
                update_fields=("failed_attempts", "updated_at")
            )

            attempts_left = max(
                0,
                settings.REGISTRATION_OTP_MAX_ATTEMPTS
                - pending.failed_attempts,
            )

            if attempts_left == 0:
                validation_error = {
                    "otp": (
                        "Too many incorrect attempts. "
                        "Request a new verification code."
                    )
                }
            else:
                validation_error = {
                    "otp": (
                        "The verification code is incorrect. "
                        f"{attempts_left} attempt(s) remaining."
                    )
                }

        elif User.objects.filter(email__iexact=email).exists():
            pending.delete()
            validation_error = {
                "email": "An account with this email already exists."
            }

        else:
            # Reuses the pending password hash without storing plaintext.
            user = User(
                email=pending.email,
                full_name=pending.full_name,
                phone=pending.phone,
                is_active=True,
                email_verified_at=(timezone.now() if pending.delivery_channel == "email" else None),
                registration_verified_channel=pending.delivery_channel,
                registration_verified_contact=(pending.phone if pending.delivery_channel == "sms" else pending.email),
            )
            user.password = pending.password_hash
            user.save()
            pending.delete()

            refresh = RefreshToken.for_user(user)
            tokens = RegistrationTokens(
                user=user,
                access=str(refresh.access_token),
                refresh=str(refresh),
            )

    if validation_error:
        raise serializers.ValidationError(validation_error)

    return tokens


def registration_token_response(tokens):
    # Produces the same safe account shape used by the existing frontend.
    return {
        "message": "Contact verified and account created successfully.",
        "user": UserSerializer(tokens.user).data,
        "access": tokens.access,
        "refresh": tokens.refresh,
    }
