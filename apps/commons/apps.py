"""Configuração da aplicação Commons.

Este módulo configura a aplicação Commons que contém modelos base
e utilitários compartilhados por todas as outras aplicações.
"""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.commons"
    verbose_name = _("Configurações Comuns")
