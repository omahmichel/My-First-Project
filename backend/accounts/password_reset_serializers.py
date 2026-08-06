from django.contrib.auth import get_user_model
from django.contrib.auth import password_validation
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

User = get_user_model()


class PasswordResetRequestSerializer(serializers.Serializer):
    # Normalizes the submitted address without revealing account existence.

    email = serializers.EmailField()

    def validate_email(self, value):
        return value.strip().lower()


class PasswordResetConfirmSerializer(serializers.Serializer):
    # Validates a signed one-time reset link and replacement password.

    uid = serializers.CharField(write_only=True)
    token = serializers.CharField(write_only=True)
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        trim_whitespace=False,
    )
    password_confirm = serializers.CharField(
        write_only=True,
        min_length=8,
        trim_whitespace=False,
    )

    default_error_messages = {
        "invalid_link": "This password reset link is invalid or has expired.",
        "password_mismatch": "The passwords do not match.",
    }

    def validate(self, attrs):
        # Requires matching passwords before checking the signed link.
        if attrs["password"] != attrs["password_confirm"]:
            self.fail("password_mismatch")

        try:
            user_id = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=user_id, is_active=True)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            self.fail("invalid_link")

        if not default_token_generator.check_token(user, attrs["token"]):
            self.fail("invalid_link")

        password_validation.validate_password(attrs["password"], user=user)
        attrs["user"] = user
        return attrs

    def save(self):
        # Changes the password and invalidates existing refresh sessions.
        user = self.validated_data["user"]
        user.set_password(self.validated_data["password"])
        user.save(update_fields=("password",))

        for outstanding_token in OutstandingToken.objects.filter(user=user):
            BlacklistedToken.objects.get_or_create(token=outstanding_token)

        return user
