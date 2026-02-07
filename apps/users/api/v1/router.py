from rest_framework.routers import DefaultRouter

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .viewsets import *

user_router = DefaultRouter()

# User actions
user_router.register(r"user", UserViewSet, "user")
user_router.register(r"", UserOnboardingViewSet, "user-onboarding")

auth_urls = [
    path("user/token/", EmailTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("user/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("user/register/", RegisterView.as_view(), name="token_obtain_pair"),
    path("user/request-password-reset/", PasswordResetKeyWebToken.as_view(), name="request_password_reset"),
    path("user/password-reset/", PasswordResetWebToken.as_view(), name="password_reset"),
]
