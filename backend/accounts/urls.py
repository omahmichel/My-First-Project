from django.urls import path
from .password_reset_views import (
    PasswordResetConfirmAPIView,
    PasswordResetRequestAPIView,
)
from .views import (
    CurrentUserAPIView,
    LoginAPIView,
    LoginOTPDeliverAPIView,
    LoginOTPResendAPIView,
    LoginOTPVerifyAPIView,
    LogoutAPIView,
    RegisterAPIView,
    RegistrationOTPResendAPIView,
    RegistrationOTPVerifyAPIView,
    RefreshAPIView,
)

app_name = "accounts"

urlpatterns = [
    path("register/", RegisterAPIView.as_view(), name="register"),
    path(
        "register/verify/",
        RegistrationOTPVerifyAPIView.as_view(),
        name="register-verify",
    ),
    path(
        "register/resend/",
        RegistrationOTPResendAPIView.as_view(),
        name="register-resend",
    ),
    path("login/", LoginAPIView.as_view(), name="login"),
    path(
        "login/deliver/",
        LoginOTPDeliverAPIView.as_view(),
        name="login-deliver",
    ),
    path(
        "login/verify/",
        LoginOTPVerifyAPIView.as_view(),
        name="login-verify",
    ),
    path(
        "login/resend/",
        LoginOTPResendAPIView.as_view(),
        name="login-resend",
    ),
    path("refresh/", RefreshAPIView.as_view(), name="refresh"),
    path("me/", CurrentUserAPIView.as_view(), name="current-user"),
    path("logout/", LogoutAPIView.as_view(), name="logout"),
    path(
        "password-reset/request/",
        PasswordResetRequestAPIView.as_view(),
        name="password-reset-request",
    ),
    path(
        "password-reset/confirm/",
        PasswordResetConfirmAPIView.as_view(),
        name="password-reset-confirm",
    ),
]
