from django.urls import path
from . import platform_admin as views
from .platform_management import Administrators, Bugs, BugStatus, RegisterAdministrator
urlpatterns = [
    path("administrators/register/", RegisterAdministrator.as_view()),
    path("administrators/", Administrators.as_view()),
    path("bugs/", Bugs.as_view()),
    path("bugs/<int:pk>/status/", BugStatus.as_view()),
    path('notifications/', views.Notifications.as_view()),
    path('overview/', views.Overview.as_view()),
    path('users/', views.Users.as_view()),
    path('users/<int:pk>/', views.UserDetail.as_view()),
    path('users/<int:pk>/status/', views.ChangeStatus.as_view(), {'kind': 'users'}),
    path('businesses/', views.Businesses.as_view()),
    path('businesses/<uuid:pk>/', views.BusinessDetail.as_view()),
    path('businesses/<uuid:pk>/status/', views.ChangeStatus.as_view(), {'kind': 'businesses'}),
    path('subscriptions/', views.Subscriptions.as_view()),
    path('activity/', views.Activity.as_view()),
]
