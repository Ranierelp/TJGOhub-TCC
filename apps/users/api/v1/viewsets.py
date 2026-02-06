from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from tools.utils import send_email

from apps.commons.api.v1.permissions import MineOrReadOnly
from apps.commons.api.v1.viewsets import BaseModelApiViewSet
from apps.commons.models import Email
from apps.users.api.v1 import exceptions, serializers
from apps.users.constants import UserConstants


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


class UserOnboardingViewSet(viewsets.ViewSet, generics.GenericAPIView):
    serializer_class = serializers.UserOnboardingSerializer

    @action(
        methods=["post"],
        detail=False,
        permission_classes=[IsAuthenticated],
    )
    def onboarding(self, request, *args, **kwargs):
        if not self.request.user.first_login_accomplished:
            """
            Add all necessary data into both dict and serializer.
            """

            data = {
                "name": request.data["name"],
                "first_login_accomplished": True,
                "status": UserConstants.USER_STATUS_ACTIVE,
                "is_active": True,
                "groups": [group.pk for group in self.request.user.groups.all()],
                "cellphone": request.data["cellphone"],
                "cep": request.data["cep"],
                "state": request.data["state"],
                "city": request.data["city"],
                "district": request.data["district"],
                "street": request.data["street"],
                "number": request.data["number"],
                "complement": request.data["complement"],
            }

            serializer = self.get_serializer(self.request.user, data=data)
            serializer.is_valid(raise_exception=True)
            serializer.save()

            profile, created = apps.get_model("users", "Profile").objects.get_or_create(user=self.request.user,
                                                                                        defaults={
                                                                                            "name": self.request.data[
                                                                                                "name"],
                                                                                            "cellphone":
                                                                                                self.request.data[
                                                                                                    "cellphone"]
                                                                                        })

            if not profile.address:
                address = apps.get_model("commons", "Address").objects.create(
                    cep=request.data["cep"],
                    state=request.data["state"],
                    city=request.data["city"],
                    district=request.data["district"],
                    street=request.data["street"],
                    number=request.data["number"],
                    complement=request.data["complement"]
                )

                profile.address = address
                profile.save()

            return Response(serializers.UserSerializer(self.request.user).data, status=status.HTTP_200_OK)
        else:
            raise exceptions.AlreadyDidFirstLogin


class ProfileViewSet(BaseModelApiViewSet):
    model = apps.get_model("users", "Profile")
    permission_classes = [MineOrReadOnly]

    @action(
        methods=["get"],
        detail=False,
        url_path="mine",
        permission_classes=[IsAuthenticated],
    )
    def get_mine(self, request, *args, **kwargs):
        instance = self.model.objects.filter(user=self.request.user).first()
        return Response(self.get_serializer(instance, many=False).data, status=status.HTTP_200_OK)

    @action(
        methods=["patch"],
        detail=False,
        url_path="update-mine",
        permission_classes=[IsAuthenticated],
    )
    def update_mine(self, request, *args, **kwargs):
        instance = self.model.objects.filter(user=self.request.user).first()

        data = {
            "is_active": True,
            "groups": [group.pk for group in self.request.user.groups.all()],
        }

        optional_fields = ["name", "cellphone", "cep", "state", "city", "district", "street", "number", "complement",
                           "avatar"]

        for field in optional_fields:
            if field in request.data:
                data[field] = request.data[field]

        if "name" in data and not data["name"]:
            return Response(data={"error": _(u"É necessário um nome")}, status=status.HTTP_400_BAD_REQUEST)

        serializer = serializers.ProfileUpdateSerializer(data=data)
        serializer.is_valid(raise_exception=True)

        profile_data = {
            "name": self.request.data.get("name", instance.name),
            "avatar": self.request.data.get("avatar", instance.avatar),
            "cellphone": self.request.data.get("cellphone", instance.cellphone),
        }

        profile, created = apps.get_model("users", "Profile").objects.update_or_create(
            user=self.request.user,
            defaults=profile_data
        )

        if instance.address:
            address_data = {
                "cep": request.data.get("cep", instance.address.cep),
                "state": request.data.get("state", instance.address.state),
                "city": request.data.get("city", instance.address.city),
                "district": request.data.get("district", instance.address.district),
                "street": request.data.get("street", instance.address.street),
                "number": request.data.get("number", instance.address.number),
                "complement": request.data.get("complement", instance.address.complement),
            }

            # Atualiza os campos do endereço
            for key, value in address_data.items():
                setattr(profile.address, key, value)

            profile.address.save()

        return Response(status=status.HTTP_200_OK)


class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = serializers.TokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)

            email = request.data.get("email")
            if not email:
                return Response({"error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

            User = apps.get_model("users", "User")
            try:
                user = User.objects.get(email=email)
                user.last_login = timezone.now()
                user.save()
            except User.DoesNotExist:
                return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

            # Monta a resposta com dados extras
            response_data = serializer.validated_data
            response_data["user"] = {
                "id": user.pkid,
                "email": user.email,
                "name": user.get_profile().name if user.get_profile() else "",
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
            return Response({"error": "Refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            return Response({"error": "Invalid refresh token."}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"message": "Logout successful."}, status=status.HTTP_200_OK)


class RegisterView(APIView):
    http_method_names = ["post"]
    permission_classes = [AllowAny, ]

    def post(self, *args, **kwargs):
        serializer = serializers.UserRegisterSerializer(data=self.request.data)

        if serializer.is_valid(raise_exception=True):
            email_model, created = Email.objects.get_or_create()
            subject = email_model.user_welcome_subject
            template = email_model.user_welcome

            new_user = get_user_model().objects.create_user(**serializer.validated_data)
            group = Group.objects.filter(name="corretor")
            if group.exists():
                group = group.first()
                group.user_set.add(new_user)

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
            return Response({"error": "Is necessary a valid email."}, status=status.HTTP_200_OK)

        serializer = serializers.PasswordResetKeyWebTokenSerializer(data={"email": self.request.data["email"]})
        if serializer.is_valid(raise_exception=True):
            email_model, created = Email.objects.get_or_create()
            subject = email_model.user_reset_password_subject
            template = email_model.user_reset_password

            data = {
                "email": self.request.data["email"],
                "link": f"{settings.SITE_URL}/nova-senha?id={serializer.validated_data['user']}&key={serializer.validated_data['token']}",
            }

            send_email(subject, settings.EMAIL_HOST_USER, serializer.validated_data["email"], data, template)
            return Response({"success": data["link"]}, status=status.HTTP_200_OK)

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
