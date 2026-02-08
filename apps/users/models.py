from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.commons.models import BaseModel


class UserManager(BaseUserManager):
    """
    Custom user model manager where email is the unique identifiers
    for authentication instead of usernames.
    """

    use_in_migrations = True

    def email_validator(self, email):
        """
        Validate the user email
        :param email:
        """
        try:
            validate_email(email)
        except ValidationError:
            raise ValueError(_("You must provide a valid email address."))

    def create_user(self, email, password, **extra_fields):
        """
        Create and save a User with the given email and password.
        :rtype: object
        """
        if not email:
            raise ValueError(_("The Email must be set"))
        else:
            email = self.normalize_email(email)
            self.email_validator(email)

        user = self.model(email=email, **extra_fields)
        user.is_active = True
        user.set_password(password)
        user.save()

        return user

    def create_superuser(self, email, password, **extra_fields):
        """
        Create and save a SuperUser with the given email and password.
        :rtype: object
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))

        user = self.create_user(email, password, **extra_fields)

        return user


class User(AbstractBaseUser, BaseModel, PermissionsMixin):
    class Meta:
        verbose_name = _("Usuário")
        verbose_name_plural = _("Usuários")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email"]),
        ]

    # Credentials
    email = models.EmailField(_("Email"), max_length=255, unique=True)
    first_name = models.CharField(_("Nome"), max_length=30, null=True, blank=True, help_text=_("Nome do usuário"))
    last_name = models.CharField(_("Sobrenome"), max_length=150, null=True, blank=True, help_text=_("Sobrenome do usuário"))

    # Access informations and dates
    is_staff = models.BooleanField(_("Colaborador"), default=False)
    date_joined = models.DateTimeField(_("Data de entrada"), default=timezone.now)

    # Consensus
    terms = models.BooleanField(_("Aceitou os termos e condições da plataforma?"), default=False)
    receive_emails = models.BooleanField(_("Aceitou receber comunicações via e-mail?"), default=False)

    objects = UserManager()

    EMAIL_FIELD = "email"
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def get_full_name(self):
        """
        Retorna o nome completo do usuário ou o email se os nomes não estiverem disponíveis.
        """
        if self.first_name or self.last_name:
            full_name = f"{self.first_name} {self.last_name}".strip()
            return full_name if full_name else self.email
        return self.email

    def get_short_name(self):
        """
        Retorna o primeiro nome ou a parte local do email.

        Usado em saudações e notificações.
        """
        return self.first_name or self.email.split('@')[0]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._excluded_fields = ["pkid", "id", "created_at", "created_by", "updated_at", "updated_by", "deleted_at",
                                 "deleted_by",]
        self._original_state = self._get_current_state()

    def _get_current_state(self):
        return {key: value for key, value in self.__dict__.items() if key not in self._excluded_fields}

    def __str__(self):
       return self.get_full_name()
