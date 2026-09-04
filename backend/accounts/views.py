from django.conf import settings

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .login_otp_service import (
    LoginEmailDeliveryError,
    deliver_login_otp,
    issue_login_otp,
    login_token_response,
    resend_login_otp,
    verify_login_otp,
)
from .registration_otp_service import (
    RegistrationEmailDeliveryError,
    issue_registration_otp,
    registration_token_response,
    resend_registration_otp,
    verify_registration_otp,
)
from .serializers import (
    LoginOTPResendSerializer,
    LoginOTPVerifySerializer,
    LoginSerializer,
    RegisterSerializer,
    RegistrationOTPResendSerializer,
    RegistrationOTPVerifySerializer,
    UserSerializer,
)


class RegisterAPIView(APIView):
    # Validates registration details and sends an email verification code.

    permission_classes = (AllowAny,)
    throttle_scope = "auth_register"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            issue_registration_otp(serializer.validated_data)
        except RegistrationEmailDeliveryError:
            return Response(
                {
                    "detail": (
                        "StockFlow could not send the verification code. "
                        "Please try again."
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "message": (
                    "A six-digit verification code was sent to your email."
                ),
                "email": serializer.validated_data["email"],
            },
            status=status.HTTP_202_ACCEPTED,
        )


class RegistrationOTPVerifyAPIView(APIView):
    # Creates the real account after a correct, unexpired OTP is submitted.

    permission_classes = (AllowAny,)
    throttle_scope = "auth_register_verify"

    def post(self, request):
        serializer = RegistrationOTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tokens = verify_registration_otp(
            email=serializer.validated_data["email"],
            otp=serializer.validated_data["otp"],
        )

        return Response(
            registration_token_response(tokens),
            status=status.HTTP_201_CREATED,
        )


class RegistrationOTPResendAPIView(APIView):
    # Sends a replacement code after the configured cooldown.

    permission_classes = (AllowAny,)
    throttle_scope = "auth_register_resend"

    def post(self, request):
        serializer = RegistrationOTPResendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            resend_registration_otp(
                serializer.validated_data["email"],
            )
        except RegistrationEmailDeliveryError:
            return Response(
                {
                    "detail": (
                        "StockFlow could not send the verification code. "
                        "Please try again."
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {"message": "A new verification code was sent."},
            status=status.HTTP_200_OK,
        )


class LoginAPIView(APIView):
    # Validates email/password and creates a 2FA challenge without SMTP latency.

    permission_classes = (AllowAny,)
    throttle_scope = "auth_login"

    def post(self, request):
        serializer = LoginSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        challenge, email_delivery_required = issue_login_otp(
            serializer.validated_data["user"],
        )

        return Response(
            {
                "message": (
                    "Password accepted. Preparing your sign-in security code."
                    if email_delivery_required
                    else "Use the security code already sent to your email."
                ),
                "challengeId": challenge.challenge_token,
                "email": challenge.user.email,
                "expiresIn": settings.LOGIN_OTP_EXPIRY_SECONDS,
                "resendCooldown": (
                    0
                    if email_delivery_required
                    else settings.LOGIN_OTP_RESEND_COOLDOWN_SECONDS
                ),
                "emailDeliveryRequired": email_delivery_required,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class LoginOTPDeliverAPIView(APIView):
    # Delivers the first OTP after the login request has already completed.

    permission_classes = (AllowAny,)
    throttle_scope = "auth_login_deliver"

    def post(self, request):
        serializer = LoginOTPResendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            challenge, email_sent = deliver_login_otp(
                serializer.validated_data["challengeId"],
            )
        except LoginEmailDeliveryError:
            return Response(
                {
                    "detail": (
                        "StockFlow could not send the sign-in security code. "
                        "Please try again."
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "message": (
                    "A six-digit security code was sent to your email."
                    if email_sent
                    else "Use the security code already sent to your email."
                ),
                "challengeId": challenge.challenge_token,
                "email": challenge.user.email,
                "expiresIn": settings.LOGIN_OTP_EXPIRY_SECONDS,
                "resendCooldown": settings.LOGIN_OTP_RESEND_COOLDOWN_SECONDS,
                "emailDeliveryRequired": False,
            },
            status=status.HTTP_200_OK,
        )


class LoginOTPVerifyAPIView(APIView):
    # Completes login and issues JWT credentials only after OTP verification.

    permission_classes = (AllowAny,)
    throttle_scope = "auth_login_verify"

    def post(self, request):
        serializer = LoginOTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tokens = verify_login_otp(
            challenge_token=serializer.validated_data["challengeId"],
            otp=serializer.validated_data["otp"],
        )
        return Response(
            login_token_response(tokens),
            status=status.HTTP_200_OK,
        )


class LoginOTPResendAPIView(APIView):
    # Reissues the login security code after the configured cooldown.

    permission_classes = (AllowAny,)
    throttle_scope = "auth_login_resend"

    def post(self, request):
        serializer = LoginOTPResendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            challenge = resend_login_otp(
                serializer.validated_data["challengeId"],
            )
        except LoginEmailDeliveryError:
            return Response(
                {
                    "detail": (
                        "StockFlow could not send the sign-in security code. "
                        "Please try again."
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "message": "A new security code was sent to your email.",
                "challengeId": challenge.challenge_token,
                "email": challenge.user.email,
                "expiresIn": settings.LOGIN_OTP_EXPIRY_SECONDS,
                "resendCooldown": settings.LOGIN_OTP_RESEND_COOLDOWN_SECONDS,
            },
            status=status.HTTP_200_OK,
        )


class RefreshAPIView(TokenRefreshView):
    # Rotates refresh tokens while limiting automated refresh abuse.

    permission_classes = (AllowAny,)
    throttle_scope = "auth_refresh"


class CurrentUserAPIView(APIView):
    # Returns the currently authenticated account.

    permission_classes = (IsAuthenticated,)

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class LogoutAPIView(APIView):
    # Blacklists the submitted refresh token during logout.

    permission_classes = (IsAuthenticated,)
    throttle_scope = "auth_logout"

    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response(
                {"refresh": "A refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            RefreshToken(refresh_token).blacklist()
        except Exception:
            return Response(
                {"refresh": "The refresh token is invalid or expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"message": "Logged out successfully."},
            status=status.HTTP_200_OK,
        )
