from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .passkey_service import (
    begin_passkey_authentication,
    begin_passkey_registration,
    finish_passkey_authentication,
    finish_passkey_registration,
)


class _LoginOptionsSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.strip().lower()


class _CredentialSerializer(serializers.Serializer):
    challengeId = serializers.CharField(max_length=100)
    credential = serializers.JSONField()
    label = serializers.CharField(max_length=80, required=False, allow_blank=True)


class PasskeyRegistrationOptionsAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    throttle_scope = "auth_passkey_register"

    def post(self, request):
        challenge_id, options = begin_passkey_registration(request.user)
        return Response({"challengeId": challenge_id, "options": options})


class PasskeyRegistrationVerifyAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    throttle_scope = "auth_passkey_register"

    def post(self, request):
        serializer = _CredentialSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = finish_passkey_registration(
            user=request.user,
            challenge_token=serializer.validated_data["challengeId"],
            credential=serializer.validated_data["credential"],
            label=serializer.validated_data.get("label", ""),
        )
        return Response(
            {
                "message": "Biometric/passkey sign-in is now enabled on this authenticator.",
                "passkeyId": row.pk,
                "label": row.label,
            },
            status=status.HTTP_201_CREATED,
        )


class PasskeyLoginOptionsAPIView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    throttle_scope = "auth_passkey_login"

    def post(self, request):
        serializer = _LoginOptionsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        challenge_id, options = begin_passkey_authentication(
            serializer.validated_data["email"]
        )
        return Response({"challengeId": challenge_id, "options": options})


class PasskeyLoginVerifyAPIView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    throttle_scope = "auth_passkey_verify"

    def post(self, request):
        serializer = _CredentialSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            finish_passkey_authentication(
                challenge_token=serializer.validated_data["challengeId"],
                credential=serializer.validated_data["credential"],
            )
        )
