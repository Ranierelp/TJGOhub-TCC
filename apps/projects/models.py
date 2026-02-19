from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

from apps.commons.models import BaseModel

class Project(BaseModel):
    """
    Model para gerenciamento de projetos de teste.

    Um projeto agrupa ambientes, casos de teste e execuções relacionados
    a um sistema ou aplicação específica.

    Exemplos de projetos:
    - "TJGO Portal do Servidor"
    - "TJGO Sistema de Processos"
    - "TJGO PJe"
    """

    class Meta(BaseModel.Meta):
        verbose_name = _("Projeto")
        verbose_name_plural = _("Projetos")
        ordering = ["-created_at"]

        # Constraints para garantir unicidade
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                condition=models.Q(is_active=True),
                name="unique_project_name"
            ),
            models.UniqueConstraint(
                fields=["slug"],
                condition=models.Q(is_active=True),
                name="unique_project_slug"
            ),
        ]

        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["slug"]),
            models.Index(fields=["is_active", "-created_at"]),
        ]

    name = models.CharField(
        _("Nome"),
        max_length=255,
        help_text=_("Nome do projeto (ex: 'TJGO Portal do Servidor')")
    )

    slug = models.SlugField(
        _("Slug"),
        max_length=255,
        help_text=_("URL-friendly name (gerado automaticamente)")
    )

    description = models.TextField(
        _("Descrição"),
        blank=True,
        help_text=_("Descrição detalhada do projeto e seus objetivos")
    )

    # is_active vem do BaseModel
    # created_at, updated_at vem do BaseModel
    # created_by vem do BaseModel (relacionamento com User)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Override do save para gerar slug automaticamente."""
        if not self.slug:
            self.slug = self._generate_unique_slug()
        super().save(*args, **kwargs)

    def _generate_unique_slug(self):
        """Gera um slug único baseado no nome do projeto.

        Se o slug já existir em um projeto ativo, adiciona sufixo numérico
        (ex: tjgo-portal, tjgo-portal-2, tjgo-portal-3, ...).
        """
        base_slug = slugify(self.name)
        slug = base_slug
        counter = 1
        while Project.objects.filter(slug=slug, is_active=True).exclude(pk=self.pk).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        return slug

    def clean(self):
        if self.name:
            existing = Project.objects.filter(
                name__iexact=self.name,
                is_active=True
            ).exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError({
                    'name': _("Já existe um projeto ativo com este nome.")
                })

    # =============================================================================
    # MÉTODOS DE NEGÓCIO 
    # =============================================================================

    def archive(self):
        """
        Arquiva o projeto (soft delete).

        Projeto arquivado:
        - Não aparece em listagens normais
        - Não pode receber novos testes ou execuções
        - Pode ser reativado
        """
        self.is_active = False
        self.save(update_fields=['is_active', 'updated_at'])

    def activate(self):
        """Reativa um projeto arquivado."""
        self.is_active = True
        self.save(update_fields=['is_active', 'updated_at'])

    def get_active_environments(self):
        """
        Retorna ambientes ativos do projeto.

        Returns:
            QuerySet: Ambientes ativos ordenados por nome
        """
        return self.environments.filter(is_active=True).order_by('name')

    def get_test_cases_count(self):
        """
        Retorna contagem de casos de teste do projeto.

        Returns:
            dict: Contadores de casos por status
        """
        from django.db.models import Count, Q

        return self.test_cases.aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(status='ACTIVE')),
            draft=Count('id', filter=Q(status='DRAFT')),
            deprecated=Count('id', filter=Q(status='DEPRECATED'))
        )

    # =============================================================================
    # PROPERTIES ÚTEIS
    # =============================================================================

    @property
    def is_archived(self):
        """Verifica se o projeto está arquivado."""
        return not self.is_active

    @property
    def environments_count(self):
        """Retorna número de ambientes ativos."""
        return self.get_active_environments().count()

    @property
    def test_cases_total(self):
        """Retorna total de casos de teste."""
        return self.test_cases.filter(is_active=True).count()

    @property
    def test_runs_count(self):
        """Retorna número de execuções realizadas."""
        return self.test_runs.count()
