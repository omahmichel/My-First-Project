from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from .registration_otp_service import (
    RegistrationEmailDeliveryError,
    issue_registration_otp,
    registration_token_response,
    resend_registration_otp,
    verify_registration_otp,
)
from .serializers import (
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


class LoginAPIView(TokenObtainPairView):
    # Authenticates an email-based user and returns JWT tokens.

    permission_classes = (AllowAny,)
    serializer_class = LoginSerializer
    throttle_scope = "auth_login"


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
