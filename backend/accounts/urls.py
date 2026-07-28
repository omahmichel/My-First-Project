from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    CurrentUserAPIView,
    LoginAPIView,
    LogoutAPIView,
    RegisterAPIView,
)

app_name = "accounts"

urlpatterns = [
    path("register/", RegisterAPIView.as_view(), name="register"),
    path("login/", LoginAPIView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="refresh"),
    path("me/", CurrentUserAPIView.as_view(), name="current-user"),
    path("logout/", LogoutAPIView.as_view(), name="logout"),
]
