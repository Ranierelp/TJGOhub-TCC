from django.db import models

from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from apps.commons.models import BaseModel

class Environment(BaseModel):
    """
    Model para ambientes de execução de testes.

    Representa diferentes ambientes onde os testes podem ser executados:
    - Desenvolvimento
    - Homologação/Staging
    - Produção

    Cada ambiente possui uma URL base e configurações específicas.
    """

    # Tipos de ambiente
    ENV_TYPE_DEVELOPMENT = 'development'
    ENV_TYPE_STAGING = 'staging'
    ENV_TYPE_PRODUCTION = 'production'

    ENV_TYPE_CHOICES = [
        (ENV_TYPE_DEVELOPMENT, _('Desenvolvimento')),
        (ENV_TYPE_STAGING, _('Homologação')),
        (ENV_TYPE_PRODUCTION, _('Produção')),
    ]

    class Meta(BaseModel.Meta):
        verbose_name = _("Ambiente")
        verbose_name_plural = _("Ambientes")
        ordering = ['project', 'name']

        constraints = [
            models.UniqueConstraint(
                fields=['project', 'name'],
                condition=models.Q(is_active=True),
                name='unique_environment_name_per_project'
            ),
            models.UniqueConstraint(
                fields=['project', 'slug'],
                condition=models.Q(is_active=True),
                name='unique_environment_slug_per_project'
            ),
        ]

        indexes = [
            models.Index(fields=['project', 'is_active']),
            models.Index(fields=['env_type']),
            models.Index(fields=['name']),
        ]

    # ============================================================================
    # CAMPOS
    # ============================================================================

    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.PROTECT,  # Não permite deletar projeto com ambientes
        related_name='environments',
        verbose_name=_("Projeto"),
        help_text=_("Projeto ao qual este ambiente pertence")
    )

    name = models.CharField(
        _("Nome"),
        max_length=100,
        help_text=_("Nome do ambiente (ex: 'Desenvolvimento', 'Produção')")
    )

    slug = models.SlugField(
        _("Slug"),
        max_length=100,
        help_text=_("URL-friendly name (gerado automaticamente)")
    )

    base_url = models.URLField(
        _("URL Base"),
        max_length=500,
        help_text=_("URL base do ambiente (ex: https://dev.tjgo.jus.br)")
    )

    env_type = models.CharField(
        _("Tipo de Ambiente"),
        max_length=20,
        choices=ENV_TYPE_CHOICES,
        default=ENV_TYPE_DEVELOPMENT,
        help_text=_("Tipo do ambiente")
    )

    # ============================================================================
    # MÉTODOS
    # ============================================================================

    def __str__(self):
        return f"{self.project.name} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()

        # Validar URL
        if not self.base_url:
            raise ValidationError({
                'base_url': _("URL base é obrigatória.")
            })

        # Validar nome único por projeto
        if self.name and self.project_id:
            existing = Environment.objects.filter(
                project=self.project,
                name__iexact=self.name,
                is_active=True
            ).exclude(pk=self.pk)

            if existing.exists():
                raise ValidationError({
                    'name': _("Já existe um ambiente com este nome neste projeto.")
                })

    # ============================================================================
    # PROPERTIES SIMPLES
    # ============================================================================

    @property
    def is_production(self):
        return self.env_type == self.ENV_TYPE_PRODUCTION

    @property
    def test_runs_count(self):
        """Quantidade de execuções registradas neste ambiente."""
        return self.test_runs.count()
