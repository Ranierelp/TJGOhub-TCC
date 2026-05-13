from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from tools.utils import send_email
from rest_framework.throttling import AnonRateThrottle

from apps.commons.api.v1.permissions import MineOrReadOnly
from apps.commons.api.v1.viewsets import BaseModelApiViewSet
from apps.commons.models import Email
from apps.users.api.v1 import exceptions, serializers


class UserViewSet(BaseModelApiViewSet):
    model = apps.get_model("users", "User")

    def get_serializer_class(self):
        if self.request and self.request.method in ("PATCH", "PUT"):
            return serializers.UserUpdateSerializer
        return serializers.UserSerializer

    @action(
        methods=["get"],
        detail=False,
        url_path="me",
        permission_classes=[IsAuthenticated],
    )
    def get_me(self, request, *args, **kwargs):
        return Response(self.get_serializer(self.request.user, many=False).data, status=status.HTTP_200_OK)



class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = serializers.TokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)

            email = request.data.get("email")
            if not email:
                return Response({"error": _("O campo e-mail é obrigatório.")}, status=status.HTTP_400_BAD_REQUEST)

            User = apps.get_model("users", "User")
            try:
                user = User.objects.get(email=email)
                user.last_login = timezone.now()
                user.save()
            except User.DoesNotExist:
                return Response({"error": _("Usuário não encontrado.")}, status=status.HTTP_404_NOT_FOUND)

            # Monta a resposta com dados extras
            response_data = serializer.validated_data
            response_data["user"] = {
                "id": str(user.id),
                "email": user.email,
                "name": user.get_full_name(),
                "is_active": user.is_active
            }

        except TokenError as e:
            raise InvalidToken(e.args[0])

        return Response(response_data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response({"error": _("O refresh token é obrigatório.")}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            return Response({"error": _("Refresh token inválido.")}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"message": _("Logout realizado com sucesso.")}, status=status.HTTP_200_OK)


class RegisterView(APIView):
    http_method_names = ["post"]
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    def post(self, *args, **kwargs):
        serializer = serializers.UserRegisterSerializer(data=self.request.data)

        if serializer.is_valid(raise_exception=True):
            email_model, created = Email.objects.get_or_create()
            subject = email_model.user_welcome_subject
            template = email_model.user_welcome

            new_user = get_user_model().objects.create_user(**serializer.validated_data)

            data = {
                "email": serializer.validated_data["email"],
                "link": f"{settings.SITE_URL}/bem-vindo?token={RefreshToken.for_user(new_user).access_token}",
            }

            send_email(subject, settings.EMAIL_HOST_USER, serializer.validated_data["email"], data, template)
            return Response(status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetKeyWebToken(APIView):
    http_method_names = ["post"]
    permission_classes = [AllowAny, ]

    def post(self, *args, **kwargs):
        """
        API View that receives a POST with a user's email.
        Send email to user, to reset password.
        """
        if "email" not in self.request.data:
            return Response({"error": _("É necessário informar um e-mail válido.")}, status=status.HTTP_400_BAD_REQUEST)

        serializer = serializers.PasswordResetKeyWebTokenSerializer(data={"email": self.request.data["email"]})
        if serializer.is_valid(raise_exception=True):
            if serializer.validated_data["user"] is not None:
                email_model, created = Email.objects.get_or_create()
                subject = email_model.user_reset_password_subject
                template = email_model.user_reset_password

                data = {
                    "email": serializer.validated_data["email"],
                    "link": f"{settings.SITE_URL}/nova-senha?id={serializer.validated_data['user']}&key={serializer.validated_data['token']}",
                }

                send_email(subject, settings.EMAIL_HOST_USER, serializer.validated_data["email"], data, template)

            return Response({"success": "Se o email existir, um link de recuperação foi enviado."}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(auth=[])
class PasswordResetWebToken(APIView):
    authentication_classes = []
    permission_classes = [AllowAny, ]

    def post(self, request, *args, **kwargs):
        """
        API View that receives a POST with a id, key, confirm_password and new_password.
        Change paswsord and returns a JSON Web Token that can be used for authenticated requests.
        """
        serializer = serializers.PasswordResetWebTokenSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
