from django.urls import path
from .password_reset_views import (
    PasswordResetConfirmAPIView,
    PasswordResetRequestAPIView,
)
from .views import (
    CurrentUserAPIView,
    LoginAPIView,
    LogoutAPIView,
    RegisterAPIView,
    RefreshAPIView,
)

app_name = "accounts"

urlpatterns = [
    path("register/", RegisterAPIView.as_view(), name="register"),
    path("login/", LoginAPIView.as_view(), name="login"),
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
