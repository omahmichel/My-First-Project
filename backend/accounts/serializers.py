from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    # Returns safe account details to the authenticated frontend.

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "full_name",
            "phone",
            "is_active",
            "date_joined",
        )
        read_only_fields = (
            "id",
            "email",
            "is_active",
            "date_joined",
        )


class RegisterSerializer(serializers.ModelSerializer):
    # Creates a new account using email and a confirmed password.

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

    class Meta:
        model = User
        fields = (
            "email",
            "full_name",
            "phone",
            "password",
            "password_confirm",
        )

    def validate_email(self, value):
        # Normalizes the submitted email before uniqueness checks.
        return value.strip().lower()

    def validate(self, attrs):
        # Requires both submitted passwords to match.
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "The passwords do not match."}
            )

        return attrs

    def create(self, validated_data):
        # Uses the custom manager so the password is hashed safely.
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")

        return User.objects.create_user(
            password=password,
            **validated_data,
        )


class RegistrationOTPVerifySerializer(serializers.Serializer):
    # Validates the submitted email and six-digit verification code.

    email = serializers.EmailField()
    otp = serializers.RegexField(
        regex=r"^\d{6}$",
        max_length=6,
        min_length=6,
    )

    def validate_email(self, value):
        return value.strip().lower()


class RegistrationOTPResendSerializer(serializers.Serializer):
    # Normalizes the email used to request a replacement code.

    email = serializers.EmailField()

    def validate_email(self, value):
        return value.strip().lower()


class LoginSerializer(TokenObtainPairSerializer):
    # Returns JWT tokens together with safe user details.

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data
