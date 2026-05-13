import collections

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework_simplejwt.serializers import PasswordField
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer as JwtTokenObtainPairSerializer,
)
from rest_framework_simplejwt.tokens import RefreshToken
from apps.users import models

"""
User serializers
"""


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ("id", "name",)


class UserSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        representation = super(UserSerializer, self).to_representation(instance)

        if instance.groups.all():
            representation["groups"] = GroupSerializer(instance.groups.all(), many=True).data

        return representation

    class Meta:
        model = models.User
        exclude = ("pkid",)
        extra_kwargs = {"password": {"write_only": True}, "groups": {"read_only": True}}
        read_only_fields = (
            "is_active",
            "is_staff",
            "is_superuser",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "date_joined",
            "last_login",
        )

    def save(self, **kwargs):
        instance = super().save(**kwargs)
        if self.validated_data.get("password"):
            instance.set_password(self.validated_data.get("password"))
        return instance


class UserUpdateSerializer(serializers.ModelSerializer):
    new_password = PasswordField(write_only=True, required=False)
    confirm_password = PasswordField(write_only=True, required=False)

    class Meta:
        model = models.User
        exclude = ("pkid",)
        extra_kwargs = {
            "password": {"required": False, "write_only": True},
            "email": {"required": False, "read_only": True},
            "groups": {"read_only": True}
        }

    def validate(self, attrs):
        new_password = attrs.get("new_password")
        confirm_password = attrs.get("confirm_password")

        if new_password or confirm_password:
            try:
                if new_password != confirm_password:
                    raise serializers.ValidationError(_(u"As duas senhas devem ser idênticas."))
                validate_password(new_password)
                attrs["password"] = make_password(new_password)
                attrs.pop("new_password", None)
                attrs.pop("confirm_password", None)
            except ValidationError as e:
                raise serializers.ValidationError(e.messages)

        return attrs



class UserRegisterSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(required=True, max_length=50)
    last_name = serializers.CharField(required=True, max_length=50)
    password1 = serializers.CharField(required=True, write_only=True)
    password2 = serializers.CharField(required=True, write_only=True)
    email = serializers.EmailField(required=True)


    def validate(self, attrs):
        items = list(attrs.items())

        if "terms" not in attrs:
            raise serializers.ValidationError(code=404, detail=_(u"Deve-se aceitar os termos e condições da plafatorma."))

        try:
            validate_email(attrs.get("email"))
        except ValidationError as e:
            raise serializers.ValidationError(code=404, detail=e.messages)

        try:
            models.User.objects.get(email=attrs.get("email"))
            raise serializers.ValidationError(code=404, detail=_(u"Já existe um usuário cadastrado com este e-mail."))
        except models.User.DoesNotExist:
            pass


        if attrs.get("password1") == attrs.get("password2"):
            items.append(("password", attrs.get("password1")))
            items.sort()
            attrs = collections.OrderedDict(items)
            del attrs["password1"]
            del attrs["password2"]
        else:
            raise serializers.ValidationError(code=404, detail=_(u"As senhas não são idênticas."))

        return attrs

    class Meta:
        model = models.User
        fields = (
            "first_name", "last_name", "email", "password1", "password2", "terms", "receive_emails"
        )



"""
JWT Serializers
"""


class TokenObtainPairSerializer(JwtTokenObtainPairSerializer):
    username_field = get_user_model().USERNAME_FIELD


class PasswordResetKeyWebTokenSerializer(serializers.Serializer):
    email = serializers.CharField(write_only=True)

    def validate(self, attrs):
        try:
            validate_email(attrs.get("email"))
        except ValidationError as e:
            raise serializers.ValidationError(e.messages)

        email = str(attrs.get("email"))
        token_generator = default_token_generator

        try:
            user = models.User.objects.get(email=email)
        except models.User.DoesNotExist:
            return {"user": None, "email": email, "token": None}

        user.code_date = timezone.now()
        user.save()

        context = {
            "user": user.id,
            "email": user.email,
            "token": token_generator.make_token(user),
        }

        return context


class PasswordResetWebTokenSerializer(serializers.Serializer):
    id = serializers.CharField(write_only=True)
    key = serializers.CharField(write_only=True)
    new_password = PasswordField(write_only=True)
    confirm_password = PasswordField(write_only=True)

    def __init__(self, *args, **kwargs):
        super(PasswordResetWebTokenSerializer, self).__init__(*args, **kwargs)

    def validate(self, attrs):
        token_generator = default_token_generator

        try:
            user = models.User.objects.get(id=attrs.get("id"))
        except models.User.DoesNotExist:
            raise serializers.ValidationError(_(u"No user found."))

        # Password Validation
        try:
            if "new_password" in attrs and "confirm_password" in attrs:
                if attrs.get("new_password") != attrs.get("confirm_password"):
                    raise serializers.ValidationError(_(u"As duas senhas devem ser idênticas."))

            validate_password(attrs.get("new_password"), user)
        except ValidationError as e:
            raise serializers.ValidationError(e.messages)

        # Token Validation
        if not token_generator.check_token(user, attrs.get("key")):
            raise serializers.ValidationError(_(u"Link expirado, por favor, tente novamente."))

        user.is_active = True
        user.set_password(attrs.get("new_password"))
        user.save()

        refresh = RefreshToken.for_user(user)

        payload = {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }

        context = {
            "token": payload,
            "user": UserSerializer(user).data
        }

        return context
