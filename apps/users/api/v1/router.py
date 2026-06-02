from rest_framework.routers import DefaultRouter

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .viewsets import *

user_router = DefaultRouter()

# User actions
user_router.register(r"user", UserViewSet, "user")

# Group / Permission — gestão de perfis (Admin-only).
# Endpoints viram: /api/v1/user/groups/  e  /api/v1/user/permissions/
user_router.register(r"groups", GroupViewSet, "groups")
user_router.register(r"permissions", PermissionViewSet, "permissions")

auth_urls = [
    path("user/token/", EmailTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("user/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("user/logout/", LogoutView.as_view(), name="logout"),
    # Auto-cadastro removido — toda criação passa pelo admin via POST /users/.
    # Se um dia precisar reabrir: descomentar a linha abaixo (e revisar o
    # UserRegisterSerializer, que ainda tem campos legados de outro projeto).
    # path("user/register/", RegisterView.as_view(), name="register"),
    path("user/request-password-reset/", PasswordResetKeyWebToken.as_view(), name="request_password_reset"),
    path("user/password-reset/", PasswordResetWebToken.as_view(), name="password_reset"),
]
