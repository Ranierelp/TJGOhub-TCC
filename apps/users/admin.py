import io

import chardet
import pandas as pd
from django.contrib import admin, messages
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.hashers import make_password
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError
from django.db.models import F, Q
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import path
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.commons.admin import BaseAdmin
from apps.users import models


class ProfileInline(admin.StackedInline):
    model = models.Profile
    extra = 0
    max_num = 1
    fk_name = "user"
    readonly_fields = ("id", "created_at", "created_by", "updated_at", "updated_by", "deleted_at", "deleted_by")
    exclude = ("address",)

    def has_delete_permission(self, request, obj=None):
        return False

    def get_fields(self, request, obj=None):
        fields = super(ProfileInline, self).get_fields(request, obj)
        if not request.user.is_superuser:
            fields = [field for field in fields if field not in [
                "id", "created_at", "created_by", "updated_at", "updated_by", "deleted_at", "deleted_by"
            ]]
        return fields


@admin.register(models.User)
class UserAdmin(UserAdmin, BaseAdmin):
    list_display = ("profile_name", "cpf_cnpj", "email", "is_active", "is_staff", "is_superuser",)
    list_filter = ("is_active", "is_staff", "is_superuser",)
    date_hierarchy = "created_at"
    search_fields = ("user__name", "email", "username", "cpf_cnpj",)
    ordering = ("user__name", "-created_at")
    inlines = (ProfileInline,)
    change_list_template = "admin/change_list.html"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(profile_name=F("user__name"))
        return qs.order_by("profile_name")

    def profile_name(self, obj):
        return obj.get_profile().name if obj.get_profile() else obj.email

    profile_name.admin_order_field = "profile_name"
    profile_name.short_description = "Nome"

    fieldsets = (
        (
            _("Credenciais"),
            {
                "fields": (
                    "email",
                    # "username",
                    "password",
                )
            },
        ),
        (
            _("Documentos"),
            {
                "fields": (
                    "cpf_cnpj",
                    "rg",
                )
            },
        ),
        (
            _("Grupos e permissões"),
            {
                "fields": (
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            _("Status"),
            {
                "fields": (
                    "status",
                    "is_active",
                    "first_login_accomplished",
                )
            },
        ),
        (
            _("Concessões e Contatos"),
            {
                "fields": (
                    "terms",
                    "receive_emails",
                    "other_emails",
                )
            },
        ),
        (
            _("Sistema"),
            {
                "fields": (
                    "id",
                    "last_login",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "cpf_cnpj", "password1", "password2"),
            },
        ),
        (
            _("Permissões"),
            {
                "classes": ("wide",),
                "fields": ("is_staff", "is_superuser", "groups",),
            }
        ),
    )

    def user_profile_name(self, obj):
        return obj.get_profile().name if obj.get_profile() else obj.email

    user_profile_name.short_description = "Nome"

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ("last_login", "id", "date_joined")
        return self.readonly_fields

    def get_fieldsets(self, request, obj=None):
        fieldsets = super(UserAdmin, self).get_fieldsets(request, obj)
        if not request.user.is_superuser:
            new_fieldsets = []
            for name, data in fieldsets:
                fields = [field for field in data["fields"] if field not in [
                    "is_staff", "is_superuser", "groups", "user_permissions", "id", "status",
                    "first_login_accomplished",
                ]]
                if fields:
                    new_fieldsets.append((name, {"fields": fields}))
            return new_fieldsets
        return fieldsets

    def get_list_filter(self, request):
        if not request.user.is_superuser:
            return ("is_active",)
        return ("is_active", "is_staff", "is_superuser",)

    def get_list_display(self, request):
        if not request.user.is_superuser:
            return ("profile_name", "cpf_cnpj", "email", "is_active",)
        return ("profile_name", "cpf_cnpj", "email", "is_active", "is_staff", "is_superuser",)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-users-csv/', self.import_users_csv),
            path('change-password-csv/', self.import_password_csv),
        ]
        return custom_urls + urls

    def import_users_csv(self, request):
        form = '''
                <form method="post" enctype="multipart/form-data">
                    <input type="file" name="csv_file" accept=".csv">
                    <input type="submit" value="Upload">
                </form>
                '''
        if request.method == "POST":
            if "csv_file" not in request.FILES:
                self.message_user(request, "Por favor, selecione um arquivo CSV.", level=messages.ERROR)
                return render(request, "admin/users/csv_form.html", {"form": form})
            csv_file = request.FILES["csv_file"]
            if not csv_file.name.endswith(".csv"):
                self.message_user(request, "Por favor, envie um arquivo CSV.")
                return HttpResponseRedirect(request.path_info)

            # Detectar a codificação do arquivo CSV
            raw_data = csv_file.read()
            result = chardet.detect(raw_data)
            encoding = result['encoding']
            csv_file.seek(0)

            # Ler o arquivo CSV usando a codificação detectada
            df = pd.read_csv(io.StringIO(raw_data.decode(encoding)), sep=";")

            created = False
            user = None

            for _index, row in df.iterrows():
                if len(str(row["email"]).split()) > 1:
                    email = str(row["email"]).split()[0].replace(" ", "").lower()
                else:
                    email = str(row["email"]).replace(" ", "").lower()

                user = models.User.objects.filter(Q(email=email))
                adm = models.User.objects.get(email="admin@exemple.com.br")

                try:
                    user, created = models.User.objects.filter(
                        Q(email=email)
                    ).get_or_create(
                        email=email,
                        defaults={
                            "cpf_cnpj": str(row["cpf_cnpj"]).replace("-", "").replace("/", "").replace(".", ""),
                            "created_by": adm
                        }
                    )

                    if created:
                        password = row["password"] if "password" in row and not pd.isna(row["password"]) else models.User.objects.make_random_password()
                        user.set_password(password)
                        user.save()

                        LogEntry.objects.log_action(
                            user_id=request.user.pkid,
                            content_type_id=ContentType.objects.get_for_model(user).pk,
                            object_id=user.pk,
                            object_repr=str(user),
                            action_flag=ADDITION,
                            change_message=_('Created') + ' ' + str(user)
                        )

                        try:
                            profile, created = models.Profile.objects.filter(user=user).get_or_create(
                                name=row["name"],
                                user=user,
                                defaults={
                                    "name": row["name"],
                                    "created_by": adm
                                }
                            )

                            if created:
                                LogEntry.objects.log_action(
                                    user_id=request.user.pkid,
                                    content_type_id=ContentType.objects.get_for_model(profile).pk,
                                    object_id=profile.pk,
                                    object_repr=str(profile),
                                    action_flag=ADDITION,
                                    change_message=_('Created') + ' ' + str(profile)
                                )
                        except IntegrityError:
                            continue

                except IntegrityError:
                    continue

            self.message_user(request, "Usuários importados com sucesso!")
            return HttpResponseRedirect("../")

        return render(request, "admin/users/csv_form.html", {"form": form})

    def import_password_csv(self, request):
        form = '''
                <form method="post" enctype="multipart/form-data">
                    <input type="file" name="csv_file" accept=".csv">
                    <input type="submit" value="Upload">
                </form>
                '''
        if request.method == "POST":
            if "csv_file" not in request.FILES:
                self.message_user(request, "Por favor, selecione um arquivo CSV.", level=messages.ERROR)
                return render(request, "admin/users/csv_form.html", {"form": form})
            csv_file = request.FILES["csv_file"]
            if not csv_file.name.endswith(".csv"):
                self.message_user(request, "Por favor, envie um arquivo CSV.")
                return HttpResponseRedirect(request.path_info)

            # Detectar a codificação do arquivo CSV
            raw_data = csv_file.read()
            result = chardet.detect(raw_data)
            encoding = result['encoding']
            csv_file.seek(0)

            # Ler o arquivo CSV usando a codificação detectada
            df = pd.read_csv(io.StringIO(raw_data.decode(encoding)), sep=";")

            for index, row in df.iterrows():
                try:
                    email = str(row["email"]).replace(" ", "").lower()
                    password = make_password(str(row["password"]))
                except KeyError:
                    messages.error(request, "Erro ao importar usuários devido à formatação do arquivo inserido.")
                    return HttpResponseRedirect("../")

                adm = models.User.objects.get(email="admin@exemple.com.br")

                try:
                    user = models.User.objects.get(email=email)
                    user.password = password
                    user.updated_by = adm
                    user.updated_at = timezone.now()
                    user.save()

                    LogEntry.objects.log_action(
                        user_id=request.user.pkid,
                        content_type_id=ContentType.objects.get_for_model(user).pk,
                        object_id=user.pk,
                        object_repr=str(user),
                        action_flag=CHANGE,
                        change_message=_('Updated') + ' ' + str(user)
                    )
                except models.User.DoesNotExist:
                    messages.error(request, f"Arquivo com usuários inválido: {row['email']}.")
                    return HttpResponseRedirect("../")

            self.message_user(request, "Senhas dos usuários modificadas com sucesso!")
            return HttpResponseRedirect("../")

        return render(request, "admin/users/change_csv_form.html", {"form": form})
