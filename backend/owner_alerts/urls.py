from django.urls import path
from .views import OwnerSmsSettings, OwnerSmsRequestCode, OwnerSmsVerifyCode
urlpatterns = [
    path('businesses/<uuid:business_id>/owner-sms/', OwnerSmsSettings.as_view()),
    path('businesses/<uuid:business_id>/owner-sms/request-code/', OwnerSmsRequestCode.as_view()),
    path('businesses/<uuid:business_id>/owner-sms/verify-code/', OwnerSmsVerifyCode.as_view()),
]
