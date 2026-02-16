from django.db import models
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from apps.commons.models import BaseModel


class TestCase(BaseModel):
    """
    Caso de Teste - Documenta testes e vincula com código Playwright.

    Faz a ponte entre:
    - Documentação de negócio (objetivo, pré-condições)
    - Código Playwright (spec_path, playwright_id)
    - Resultados (histórico de execuções)
    """

    # Status possíveis
    STATUS_DRAFT = 'DRAFT'
    STATUS_ACTIVE = 'ACTIVE'
    STATUS_DEPRECATED = 'DEPRECATED'

    STATUS_CHOICES = [
        (STATUS_DRAFT, _('Rascunho')),
        (STATUS_ACTIVE, _('Ativo')),
        (STATUS_DEPRECATED, _('Depreciado')),
    ]

    class Meta(BaseModel.Meta):
        verbose_name = _("Caso de Teste")
        verbose_name_plural = _("Casos de Teste")
        ordering = ['project', 'case_id']

        # Constraints
        constraints = [
            models.UniqueConstraint(
                fields=['project', 'case_id'],
                condition=models.Q(is_active=True),
                name='unique_case_id_per_project'
            ),
            models.UniqueConstraint(
                fields=['playwright_id'],
                condition=models.Q(is_active=True, playwright_id__isnull=False),
                name='unique_playwright_id'
            ),
        ]

        # Índices
        indexes = [
            models.Index(fields=['project', 'status', 'is_active']),
            models.Index(fields=['playwright_id']),
            models.Index(fields=['module']),
            models.Index(fields=['case_id']),
        ]

    # =============================================================================
    # CAMPOS - IDENTIFICAÇÃO
    # =============================================================================

    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.PROTECT,
        related_name='test_cases',
        verbose_name=_("Projeto")
    )

    case_id = models.CharField(
        _("ID do Caso"),
        max_length=50,
        help_text=_("ID único do caso no projeto (ex: TC-001)")
    )

    title = models.CharField(
        _("Título"),
        max_length=255,
        help_text=_("Título descritivo do caso de teste")
    )

    slug = models.SlugField(
        _("Slug"),
        max_length=255,
        help_text=_("URL-friendly name (gerado automaticamente)")
    )

    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        help_text=_("Status atual do caso de teste")
    )

    module = models.CharField(
        _("Módulo"),
        max_length=100,
        blank=True,
        help_text=_("Módulo ou funcionalidade (ex: 'Autenticação', 'Processos')")
    )

    # =============================================================================
    # CAMPOS - DOCUMENTAÇÃO
    # =============================================================================

    objective = models.TextField(
        _("Objetivo"),
        blank=True,
        help_text=_("O que este teste valida?")
    )

    preconditions = models.TextField(
        _("Pré-condições"),
        blank=True,
        help_text=_("Estado necessário antes da execução")
    )

    postconditions = models.TextField(
        _("Pós-condições"),
        blank=True,
        help_text=_("Estado esperado após a execução")
    )

    expected_result = models.TextField(
        _("Resultado Esperado"),
        blank=True,
        help_text=_("Resultado esperado do teste")
    )

    observations = models.TextField(
        _("Observações"),
        blank=True,
        help_text=_("Observações gerais, notas, etc.")
    )

    # =============================================================================
    # CAMPOS - VÍNCULO COM PLAYWRIGHT
    # =============================================================================

    test_title = models.CharField(
        _("Título no Playwright"),
        max_length=255,
        blank=True,
        help_text=_("Título exato do test() no código Playwright")
    )

    playwright_id = models.CharField(
        _("Playwright ID"),
        max_length=255,
        blank=True,
        null=True,
        help_text=_("ID único para vincular com código (ex: 'auth-login-valid')")
    )

    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='test_cases_created',
        verbose_name=_("Criado por")
    )

    last_modified_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='test_cases_modified',
        verbose_name=_("Última modificação por")
    )

    tags = models.ManyToManyField(
        'tags.Tag',
        blank=True,
        related_name='test_cases',
        verbose_name=_("Tags"),
        help_text=_("Tags para categorização")
    )

    # =============================================================================
    # MÉTODOS
    # =============================================================================

    def __str__(self):
        return f"{self.case_id} - {self.title}"

    def save(self, *args, **kwargs):
        """Override do save."""
        # Gerar slug
        if not self.slug:
            self.slug = slugify(f"{self.case_id}-{self.title}")

        # Atualizar last_modified_by se tiver usuário no kwargs
        if 'updated_by' in kwargs:
            self.last_modified_by = kwargs.pop('updated_by')

        super().save(*args, **kwargs)

    def clean(self):
        """Validações customizadas."""
        super().clean()

        # Validar case_id único por projeto
        if self.case_id and self.project_id:
            existing = TestCase.objects.filter(
                project=self.project,
                case_id__iexact=self.case_id,
                is_active=True
            ).exclude(pk=self.pk)

            if existing.exists():
                raise ValidationError({
                    'case_id': _("Já existe um caso de teste ativo com este ID neste projeto.")
                })

        # Validar playwright_id único globalmente
        if self.playwright_id:
            existing = TestCase.objects.filter(
                playwright_id__iexact=self.playwright_id,
                is_active=True
            ).exclude(pk=self.pk)

            if existing.exists():
                raise ValidationError({
                    'playwright_id': _("Já existe um caso de teste com este Playwright ID.")
                })

    # =============================================================================
    # MÉTODOS DE NEGÓCIO
    # =============================================================================

    def change_status(self, new_status, user=None):
        """
        Muda o status do caso de teste.

        Args:
            new_status: Novo status (DRAFT, ACTIVE, DEPRECATED)
            user: Usuário que está fazendo a mudança
        """
        if new_status not in [self.STATUS_DRAFT, self.STATUS_ACTIVE, self.STATUS_DEPRECATED]:
            raise ValueError(f"Status inválido: {new_status}")

        self.status = new_status
        if user:
            self.last_modified_by = user
        self.save(update_fields=['status', 'last_modified_by', 'updated_at'])

    def archive(self, user=None):
        """Arquiva o caso de teste (soft delete)."""
        self.is_active = False
        if user:
            self.last_modified_by = user
            self.deleted_by = user
        self.save(update_fields=['is_active', 'last_modified_by', 'deleted_by', 'updated_at'])

    def get_last_results(self, n=10):
        """
        Retorna os N últimos resultados deste caso de teste.

        Args:
            n: Número de resultados (padrão: 10)

        Returns:
            QuerySet de TestResult ordenado por data
        """
        if not hasattr(self, 'test_results'):
            return []

        return self.test_results.select_related(
            'test_run', 'test_run__environment'
        ).order_by('-executed_at')[:n]

    def calculate_flakiness(self):
        """
        Calcula taxa de instabilidade (flakiness) do teste.

        Returns:
            dict com métricas de flakiness
        """
        if not hasattr(self, 'test_results'):
            return {
                'flakiness_rate': 0.0,
                'total_runs': 0,
                'is_flaky': False
            }

        results = self.test_results.all()
        total = results.count()

        if total == 0:
            return {
                'flakiness_rate': 0.0,
                'total_runs': 0,
                'is_flaky': False
            }

        passed = results.filter(status='PASSED').count()
        failed = results.filter(status='FAILED').count()
        flaky = results.filter(status='FLAKY').count()

        # Taxa de falha
        failure_rate = (failed + flaky) / total

        # É considerado flaky se:
        # - Tem mais de 10 execuções
        # - Taxa de falha entre 5% e 95% (não é sempre sucesso nem sempre falha)
        is_flaky = total > 10 and 0.05 <= failure_rate <= 0.95

        return {
            'flakiness_rate': round(failure_rate * 100, 2),
            'total_runs': total,
            'passed': passed,
            'failed': failed,
            'flaky': flaky,
            'is_flaky': is_flaky
        }

    def get_success_rate(self):
        """
        Calcula taxa de sucesso do teste.

        Returns:
            float: Percentual de sucesso (0-100)
        """
        if not hasattr(self, 'test_results'):
            return 0.0

        total = self.test_results.count()
        if total == 0:
            return 0.0

        passed = self.test_results.filter(status='PASSED').count()
        return round((passed / total) * 100, 2)

    # =============================================================================
    # PROPERTIES
    # =============================================================================

    @property
    def is_draft(self):
        """Verifica se está em rascunho."""
        return self.status == self.STATUS_DRAFT

    @property
    def is_active_status(self):
        """Verifica se está ativo (não confundir com is_active do soft delete)."""
        return self.status == self.STATUS_ACTIVE

    @property
    def is_deprecated(self):
        """Verifica se está depreciado."""
        return self.status == self.STATUS_DEPRECATED

    @property
    def test_results_count(self):
        """Retorna quantidade de resultados."""
        if hasattr(self, 'test_results'):
            return self.test_results.count()
        return 0

    @property
    def has_playwright_link(self):
        """Verifica se está vinculado ao Playwright."""
        return bool(self.playwright_id)

def test_case_attachment_path(instance, filename):
    """Gera caminho para upload de anexos."""
    import os
    from datetime import datetime

    ext = os.path.splitext(filename)[1]
    new_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"

    return f"test_cases/{instance.test_case.project.slug}/{instance.test_case.case_id}/attachments/{new_filename}"


class TestCaseAttachment(BaseModel):
    """Anexo de caso de teste (imagens, PDFs, etc)."""

    TYPE_IMAGE = 'IMAGE'
    TYPE_DOCUMENT = 'DOCUMENT'
    TYPE_OTHER = 'OTHER'

    TYPE_CHOICES = [
        (TYPE_IMAGE, _('Imagem')),
        (TYPE_DOCUMENT, _('Documento')),
        (TYPE_OTHER, _('Outro')),
    ]

    class Meta(BaseModel.Meta):
        verbose_name = _("Anexo de Caso de Teste")
        verbose_name_plural = _("Anexos de Casos de Teste")
        ordering = ['test_case', 'order']

    test_case = models.ForeignKey(
        'cases.TestCase',
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name=_("Caso de Teste")
    )

    file = models.FileField(
        _("Arquivo"),
        upload_to=test_case_attachment_path
    )

    title = models.CharField(
        _("Título"),
        max_length=255
    )

    description = models.TextField(
        _("Descrição"),
        blank=True
    )

    attachment_type = models.CharField(
        _("Tipo"),
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_IMAGE
    )

    order = models.PositiveIntegerField(
        _("Ordem"),
        default=0
    )

    uploaded_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_("Enviado por")
    )

    def __str__(self):
        return f"{self.test_case.case_id} - {self.title}"

    @property
    def is_image(self):
        return self.attachment_type == self.TYPE_IMAGE
