import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .password_reset_serializers import (
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
)

User = get_user_model()
logger = logging.getLogger(__name__)

PASSWORD_RESET_RESPONSE = (
    "If an active account uses that email address, "
    "a password reset link has been sent."
)


class PasswordResetRequestAPIView(APIView):
    # Sends a neutral response so unknown emails cannot be discovered.

    permission_classes = (AllowAny,)
    throttle_scope = "auth_password_reset_request"

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = User.objects.filter(
            email__iexact=serializer.validated_data["email"],
            is_active=True,
        ).first()

        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_url = (
                f"{settings.FRONTEND_BASE_URL}/reset-password"
                f"?uid={uid}&token={token}"
            )

            try:
                send_mail(
                    subject="Reset your StockFlow password",
                    message=(
                        f"Hello {user.full_name or 'StockFlow user'},\n\n"
                        "We received a request to reset your StockFlow "
                        "password.\n\n"
                        f"Open this secure link:\n{reset_url}\n\n"
                        "This link expires in one hour and can be used only "
                        "until the password is changed.\n\n"
                        "If you did not request this reset, ignore this email."
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=(user.email,),
                    fail_silently=False,
                )
            except Exception:
                logger.exception(
                    "Password reset email delivery failed for user_id=%s.",
                    user.pk,
                )

        return Response(
            {"message": PASSWORD_RESET_RESPONSE},
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmAPIView(APIView):
    # Replaces the password only when the signed reset link is valid.

    permission_classes = (AllowAny,)
    throttle_scope = "auth_password_reset_confirm"

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "message": (
                    "Password reset successfully. "
                    "You can now log in with the new password."
                )
            },
            status=status.HTTP_200_OK,
        )
