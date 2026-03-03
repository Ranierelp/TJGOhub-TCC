# apps/core/models/test_result.py

from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from apps.commons.models import BaseModel


class TestResult(BaseModel):
    """
    Resultado Individual de Teste.

    Armazena o resultado de cada teste executado em uma TestRun.
    Criado quando Hub processa JUnit XML enviado pelo CI/CD.

    IMPORTANTE: test_case é NULLABLE para permitir:
    - Resultados de testes não catalogados
    - Preservar histórico se TestCase for deletado
    """

    # Status possíveis
    STATUS_PASSED = 'PASSED'
    STATUS_FAILED = 'FAILED'
    STATUS_SKIPPED = 'SKIPPED'
    STATUS_FLAKY = 'FLAKY'

    STATUS_CHOICES = [
        (STATUS_PASSED, _('Passou')),
        (STATUS_FAILED, _('Falhou')),
        (STATUS_SKIPPED, _('Pulado')),
        (STATUS_FLAKY, _('Instável (Flaky)')),
    ]

    class Meta(BaseModel.Meta):
        verbose_name = _("Resultado de Teste")
        verbose_name_plural = _("Resultados de Teste")
        ordering = ['-executed_at', '-created_at']

        # Índices para performance
        indexes = [
            models.Index(fields=['test_run', '-executed_at']),
            models.Index(fields=['test_case', '-executed_at']),
            models.Index(fields=['result_id']),
            models.Index(fields=['status']),
            models.Index(fields=['-executed_at']),
        ]

    # =============================================================================
    # CAMPOS - IDENTIFICAÇÃO
    # =============================================================================

    test_run = models.ForeignKey(
        'runs.TestRun',
        on_delete=models.CASCADE,  # Se TestRun deletado, resultados também são
        related_name='test_results',
        verbose_name=_("Execução de Teste")
    )

    test_case = models.ForeignKey(
        'cases.TestCase',
        on_delete=models.SET_NULL,  # Se TestCase deletado, resultado preservado
        related_name='test_results',
        verbose_name=_("Caso de Teste"),
        null=True,
        blank=True,
        help_text=_("Caso de teste (opcional - pode ser null se não catalogado)")
    )

    result_id = models.CharField(
        _("ID do Resultado"),
        max_length=200,
        unique=True,
        help_text=_("ID único do resultado")
    )

    title = models.CharField(
        _("Título do Teste"),
        max_length=500,
        blank=True,
        default="",
        help_text=_("Título do teste conforme reportado pelo Playwright")
    )

    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=STATUS_CHOICES
    )

    # =============================================================================
    # CAMPOS - MÉTRICAS E DETALHES
    # =============================================================================

    duration_seconds = models.FloatField(
        _("Duração (segundos)"),
        default=0.0
    )

    error_message = models.TextField(
        _("Mensagem de Erro"),
        blank=True,
        help_text=_("Mensagem de erro se teste falhou")
    )

    stack_trace = models.TextField(
        _("Stack Trace"),
        blank=True,
        help_text=_("Stack trace completo do erro")
    )

    retry_number = models.IntegerField(
        _("Número do Retry"),
        default=0,
        help_text=_("Qual tentativa foi esta (0 = primeira, 1 = primeiro retry, etc)")
    )

    metadata = models.JSONField(
        _("Metadados"),
        default=dict,
        blank=True,
        help_text=_("Informações extras em JSON (browser, viewport, etc)")
    )

    executed_at = models.DateTimeField(
        _("Executado em"),
        help_text=_("Quando o teste foi executado")
    )

    # =============================================================================
    # MÉTODOS
    # =============================================================================

    def __str__(self):
        test_name = self.test_case.title if self.test_case else "Sem vínculo"
        return f"{self.result_id} - {test_name} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        """Override do save para gerar result_id."""
        if not self.result_id:
            self.result_id = self._generate_result_id()

        if not self.executed_at:
            self.executed_at = timezone.now()

        super().save(*args, **kwargs)

    def clean(self):
        """Validações customizadas."""
        super().clean()

        # Se status é FAILED, deve ter error_message
        if self.status == self.STATUS_FAILED and not self.error_message:
            raise ValidationError({
                'error_message': _("Resultados com falha devem ter mensagem de erro.")
            })

    # =============================================================================
    # MÉTODOS DE NEGÓCIO
    # =============================================================================

    def mark_as_flaky(self):
        """Marca resultado como flaky (instável)."""
        self.status = self.STATUS_FLAKY
        self.save(update_fields=['status', 'updated_at'])

    def has_artifacts(self):
        """
        Verifica se tem artefatos anexados.

        Returns:
            bool: True se tem screenshots, vídeos, etc
        """
        return hasattr(self, 'artifacts') and self.artifacts.exists()

    def get_error_summary(self):
        """
        Retorna resumo do erro (primeira linha da mensagem).

        Returns:
            str: Primeira linha do error_message ou '-'
        """
        if not self.error_message:
            return '-'

        # Pega primeira linha
        first_line = self.error_message.split('\n')[0]

        # Trunca se muito longo
        if len(first_line) > 100:
            return first_line[:97] + '...'

        return first_line

    def get_artifacts_count(self):
        """Retorna quantidade de artefatos."""
        if hasattr(self, 'artifacts'):
            return self.artifacts.count()
        return 0

    def _generate_result_id(self):
        """
        Gera ID único para o resultado.

        Formato: result-{run_id}-{sequence}
        Exemplo: result-run-20260214-001-001
        """
        prefix = f"result-{self.test_run.run_id}-"

        # Buscar último resultado desta execução
        last_result = TestResult.objects.filter(
            test_run=self.test_run,
            result_id__startswith=prefix
        ).order_by('-result_id').first()

        if last_result:
            # Extrair número e incrementar
            last_num = int(last_result.result_id.split('-')[-1])
            new_num = last_num + 1
        else:
            new_num = 1

        return f"{prefix}{new_num:03d}"

    # =============================================================================
    # PROPERTIES
    # =============================================================================

    @property
    def is_passed(self):
        """Verifica se passou."""
        return self.status == self.STATUS_PASSED

    @property
    def is_failed(self):
        """Verifica se falhou."""
        return self.status == self.STATUS_FAILED

    @property
    def is_skipped(self):
        """Verifica se foi pulado."""
        return self.status == self.STATUS_SKIPPED

    @property
    def is_flaky(self):
        """Verifica se é flaky."""
        return self.status == self.STATUS_FLAKY

    @property
    def duration_formatted(self):
        """
        Retorna duração formatada.

        Returns:
            str: "5.3s" ou "1m 30s"
        """
        if not self.duration_seconds:
            return "0s"

        if self.duration_seconds < 60:
            return f"{self.duration_seconds:.1f}s"

        minutes = int(self.duration_seconds // 60)
        seconds = self.duration_seconds % 60
        return f"{minutes}m {seconds:.1f}s"

    @property
    def has_error(self):
        """Verifica se tem erro."""
        return bool(self.error_message or self.stack_trace)

    @property
    def test_name(self):
        """
        Retorna nome do teste.
        Prioriza o título salvo diretamente, depois o TestCase vinculado.

        Returns:
            str: Título do teste
        """
        if self.title:
            return self.title
        if self.test_case:
            return self.test_case.title
        return "Sem vínculo com caso de teste"
