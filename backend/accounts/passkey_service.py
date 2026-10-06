import json
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import update_last_login
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from webauthn import (
    base64url_to_bytes,
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.exceptions import (
    InvalidAuthenticationResponse,
    InvalidRegistrationResponse,
)
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from .models import PasskeyChallenge, PasskeyCredential
from .serializers import UserSerializer

REGISTRATION = PasskeyChallenge.Purpose.REGISTRATION
AUTHENTICATION = PasskeyChallenge.Purpose.AUTHENTICATION


def _user_handle(user):
    digest = salted_hmac(
        "stockflow.accounts.passkey_user_handle",
        str(user.pk),
        secret=settings.SECRET_KEY,
        algorithm="sha256",
    ).hexdigest()
    return bytes.fromhex(digest)


def _enum_value(value):
    return getattr(value, "value", str(value))


def _create_challenge(*, user, purpose, challenge):
    now = timezone.now()
    PasskeyChallenge.objects.filter(expires_at__lte=now).delete()
    PasskeyChallenge.objects.filter(user=user, purpose=purpose).delete()
    return PasskeyChallenge.objects.create(
        user=user,
        purpose=purpose,
        challenge_token=secrets.token_urlsafe(32),
        challenge=challenge,
        expires_at=now + timedelta(seconds=settings.WEBAUTHN_CHALLENGE_TTL_SECONDS),
    )


def _consume_challenge(*, challenge_token, purpose, user=None):
    with transaction.atomic():
        challenge = (
            PasskeyChallenge.objects.select_for_update()
            .select_related("user")
            .filter(challenge_token=challenge_token, purpose=purpose)
            .first()
        )
        if not challenge or challenge.expires_at <= timezone.now():
            if challenge:
                challenge.delete()
            raise serializers.ValidationError(
                {"challengeId": "This biometric sign-in request has expired. Start again."}
            )
        if user is not None and challenge.user_id != user.id:
            challenge.delete()
            raise serializers.ValidationError(
                {"challengeId": "This biometric request does not belong to this account."}
            )
        challenge_bytes = bytes(challenge.challenge)
        challenge_user = challenge.user
        challenge.delete()
    return challenge_user, challenge_bytes


def begin_passkey_registration(user):
    challenge_bytes = secrets.token_bytes(32)
    options = generate_registration_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        rp_name=settings.WEBAUTHN_RP_NAME,
        user_id=_user_handle(user),
        user_name=user.email,
        user_display_name=user.full_name or user.email,
        challenge=challenge_bytes,
        timeout=60_000,
        attestation=AttestationConveyancePreference.NONE,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=bytes(row.credential_id))
            for row in user.passkey_credentials.all()
        ],
    )
    challenge = _create_challenge(
        user=user,
        purpose=REGISTRATION,
        challenge=challenge_bytes,
    )
    return challenge.challenge_token, json.loads(options_to_json(options))


def finish_passkey_registration(*, user, challenge_token, credential, label=""):
    _, challenge_bytes = _consume_challenge(
        challenge_token=challenge_token,
        purpose=REGISTRATION,
        user=user,
    )
    try:
        verification = verify_registration_response(
            credential=credential,
            expected_challenge=challenge_bytes,
            expected_rp_id=settings.WEBAUTHN_RP_ID,
            expected_origin=settings.WEBAUTHN_ORIGINS,
            require_user_verification=True,
        )
    except (InvalidRegistrationResponse, ValueError, TypeError) as exc:
        raise serializers.ValidationError(
            {"credential": "StockFlow could not verify this biometric/passkey registration."}
        ) from exc

    transports = credential.get("response", {}).get("transports", [])
    if not isinstance(transports, list):
        transports = []

    credential_id = bytes(verification.credential_id)
    if PasskeyCredential.objects.filter(credential_id=credential_id).exists():
        raise serializers.ValidationError(
            {"credential": "This passkey is already registered with StockFlow."}
        )

    return PasskeyCredential.objects.create(
        user=user,
        credential_id=credential_id,
        public_key=bytes(verification.credential_public_key),
        sign_count=verification.sign_count,
        transports=[str(value)[:30] for value in transports[:8]],
        device_type=_enum_value(verification.credential_device_type)[:30],
        backed_up=bool(verification.credential_backed_up),
        label=(label or "Biometric sign-in")[:80],
    )


def begin_passkey_authentication(email):
    normalized = (email or "").strip().lower()
    credential = (
        PasskeyCredential.objects.select_related("user")
        .filter(user__email=normalized, user__is_active=True)
        .first()
    )
    if not credential:
        raise serializers.ValidationError(
            {"email": "Biometric sign-in is not available for this account yet."}
        )
    user = credential.user
    challenge_bytes = secrets.token_bytes(32)
    options = generate_authentication_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        challenge=challenge_bytes,
        timeout=60_000,
        allow_credentials=[
            PublicKeyCredentialDescriptor(id=bytes(row.credential_id))
            for row in user.passkey_credentials.all()
        ],
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    challenge = _create_challenge(
        user=user,
        purpose=AUTHENTICATION,
        challenge=challenge_bytes,
    )
    return challenge.challenge_token, json.loads(options_to_json(options))


def finish_passkey_authentication(*, challenge_token, credential):
    user, challenge_bytes = _consume_challenge(
        challenge_token=challenge_token,
        purpose=AUTHENTICATION,
    )
    raw_id = credential.get("rawId") or credential.get("id")
    if not isinstance(raw_id, str):
        raise serializers.ValidationError(
            {"credential": "StockFlow received an invalid biometric credential."}
        )
    try:
        credential_id = base64url_to_bytes(raw_id)
    except Exception as exc:
        raise serializers.ValidationError(
            {"credential": "StockFlow received an invalid biometric credential."}
        ) from exc

    stored = PasskeyCredential.objects.filter(
        user=user,
        credential_id=credential_id,
    ).first()
    if not stored or not user.is_active:
        raise serializers.ValidationError(
            {"credential": "StockFlow could not verify this biometric sign-in."}
        )

    try:
        verification = verify_authentication_response(
            credential=credential,
            expected_challenge=challenge_bytes,
            expected_rp_id=settings.WEBAUTHN_RP_ID,
            expected_origin=settings.WEBAUTHN_ORIGINS,
            credential_public_key=bytes(stored.public_key),
            credential_current_sign_count=stored.sign_count,
            require_user_verification=True,
        )
    except (InvalidAuthenticationResponse, ValueError, TypeError) as exc:
        raise serializers.ValidationError(
            {"credential": "StockFlow could not verify this biometric sign-in."}
        ) from exc

    stored.sign_count = verification.new_sign_count
    stored.device_type = _enum_value(verification.credential_device_type)[:30]
    stored.backed_up = bool(verification.credential_backed_up)
    stored.last_used_at = timezone.now()
    stored.save(
        update_fields=("sign_count", "device_type", "backed_up", "last_used_at")
    )

    refresh = RefreshToken.for_user(user)
    update_last_login(None, user)
    return {
        "message": "Biometric sign-in verified successfully.",
        "user": UserSerializer(user).data,
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }
