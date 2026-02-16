from django.db import models
from django.db.models import Count, IntegerField, Q, Sum
from django.db.models.functions import Cast, Substr
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from apps.commons.models import BaseModel


class TestRun(BaseModel):
    """
    Execução de Testes - Agrupa resultados de uma rodada de testes.

    Criado quando CI/CD executa testes e envia resultados para o Hub.
    Contém métricas agregadas e rastreabilidade Git.
    """

    # Status possíveis
    STATUS_PENDING = 'PENDING'
    STATUS_RUNNING = 'RUNNING'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_FAILED = 'FAILED'
    STATUS_CANCELLED = 'CANCELLED'

    STATUS_CHOICES = [
        (STATUS_PENDING, _('Pendente')),
        (STATUS_RUNNING, _('Em Execução')),
        (STATUS_COMPLETED, _('Concluído')),
        (STATUS_FAILED, _('Falhou')),
        (STATUS_CANCELLED, _('Cancelado')),
    ]

    # Tipos de disparo
    TRIGGER_MANUAL = 'manual'
    TRIGGER_API = 'api'
    TRIGGER_SCHEDULED = 'scheduled'

    TRIGGER_CHOICES = [
        (TRIGGER_MANUAL, _('Manual')),
        (TRIGGER_API, _('API (CI/CD)')),
        (TRIGGER_SCHEDULED, _('Agendado')),
    ]

    class Meta(BaseModel.Meta):
        verbose_name = _("Execução de Teste")
        verbose_name_plural = _("Execuções de Teste")
        ordering = ['-started_at', '-created_at']

        # Índices para performance
        indexes = [
            models.Index(fields=['project', 'environment', '-started_at']),
            models.Index(fields=['run_id']),
            models.Index(fields=['status']),
            models.Index(fields=['branch']),
            models.Index(fields=['-started_at']),
        ]

    # =============================================================================
    # CAMPOS - IDENTIFICAÇÃO
    # =============================================================================

    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.PROTECT,
        related_name='test_runs',
        verbose_name=_("Projeto")
    )

    environment = models.ForeignKey(
        'environments.Environment',
        on_delete=models.PROTECT,
        related_name='test_runs',
        verbose_name=_("Ambiente")
    )

    run_id = models.CharField(
        _("ID da Execução"),
        max_length=100,
        unique=True,
        help_text=_("ID único da execução (ex: 'run-20260214-001')")
    )

    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )

    trigger_type = models.CharField(
        _("Tipo de Disparo"),
        max_length=20,
        choices=TRIGGER_CHOICES,
        default=TRIGGER_API
    )

    # =============================================================================
    # CAMPOS - INTEGRAÇÃO GIT
    # =============================================================================

    branch = models.CharField(
        _("Branch"),
        max_length=255,
        blank=True,
        help_text=_("Branch Git (ex: 'main', 'develop')")
    )

    commit_sha = models.CharField(
        _("Commit SHA"),
        max_length=40,
        blank=True,
        help_text=_("Hash do commit Git")
    )

    commit_message = models.TextField(
        _("Mensagem do Commit"),
        blank=True
    )

    # =============================================================================
    # CAMPOS - MÉTRICAS
    # =============================================================================

    total_tests = models.IntegerField(
        _("Total de Testes"),
        default=0
    )

    passed_tests = models.IntegerField(
        _("Testes Aprovados"),
        default=0
    )

    failed_tests = models.IntegerField(
        _("Testes Falhados"),
        default=0
    )

    skipped_tests = models.IntegerField(
        _("Testes Pulados"),
        default=0
    )

    flaky_tests = models.IntegerField(
        _("Testes Instáveis"),
        default=0
    )

    duration_seconds = models.FloatField(
        _("Duração (segundos)"),
        default=0.0
    )

    # =============================================================================
    # CAMPOS - TIMESTAMPS
    # =============================================================================

    started_at = models.DateTimeField(
        _("Iniciado em"),
        null=True,
        blank=True
    )

    completed_at = models.DateTimeField(
        _("Concluído em"),
        null=True,
        blank=True
    )

    # =============================================================================
    # RELACIONAMENTOS
    # =============================================================================

    triggered_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='test_runs_triggered',
        verbose_name=_("Disparado por")
    )

    tags = models.ManyToManyField(
        'tags.Tag',
        blank=True,
        related_name='test_runs',
        verbose_name=_("Tags")
    )

    # =============================================================================
    # MÉTODOS
    # =============================================================================

    def __str__(self):
        return f"{self.run_id} - {self.project.name} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        """Override do save para gerar run_id."""
        if not self.run_id:
            self.run_id = self._generate_run_id()
        super().save(*args, **kwargs)

    def clean(self):
        """Validações customizadas."""
        super().clean()

        # Validar que started_at <= completed_at
        if self.started_at and self.completed_at:
            if self.completed_at < self.started_at:
                raise ValidationError({
                    'completed_at': _("Data de conclusão não pode ser anterior ao início.")
                })

    # =============================================================================
    # MÉTODOS DE NEGÓCIO
    # =============================================================================

    def start(self):
        """Inicia a execução."""
        if self.status != self.STATUS_PENDING:
            raise ValidationError(
                _("Apenas execuções pendentes podem ser iniciadas.")
            )

        self.status = self.STATUS_RUNNING
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at', 'updated_at'])

    def complete(self):
        """Marca como concluída."""
        if self.status != self.STATUS_RUNNING:
            raise ValidationError(
                _("Apenas execuções em andamento podem ser concluídas.")
            )

        self.status = self.STATUS_COMPLETED
        self.completed_at = timezone.now()
        self.calculate_metrics()
        self.save(update_fields=[
            'status', 'completed_at',
            'total_tests', 'passed_tests', 'failed_tests',
            'skipped_tests', 'flaky_tests', 'duration_seconds',
            'updated_at'
        ])

    def fail(self):
        """Marca como falhada."""
        if self.status in [self.STATUS_COMPLETED, self.STATUS_CANCELLED]:
            raise ValidationError(
                _("Não é possível marcar como falhada uma execução já finalizada.")
            )

        self.status = self.STATUS_FAILED
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at', 'updated_at'])

    def cancel(self, user=None):
        """Cancela a execução."""
        if self.status in [self.STATUS_COMPLETED, self.STATUS_FAILED]:
            raise ValidationError(
                _("Não é possível cancelar execução já finalizada.")
            )

        self.status = self.STATUS_CANCELLED
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at', 'updated_at'])

    def calculate_metrics(self):
        """
        Recalcula métricas agregadas a partir dos TestResults.

        Atualiza:
        - total_tests
        - passed_tests
        - failed_tests
        - skipped_tests
        - flaky_tests
        - duration_seconds
        """
        results = self.test_results.aggregate(
            total=Count('id'),
            passed=Count('id', filter=Q(status='PASSED')),
            failed=Count('id', filter=Q(status='FAILED')),
            skipped=Count('id', filter=Q(status='SKIPPED')),
            flaky=Count('id', filter=Q(status='FLAKY')),
            total_duration=Sum('duration_seconds')
        )

        self.total_tests = results['total'] or 0
        self.passed_tests = results['passed'] or 0
        self.failed_tests = results['failed'] or 0
        self.skipped_tests = results['skipped'] or 0
        self.flaky_tests = results['flaky'] or 0
        self.duration_seconds = results['total_duration'] or 0.0

    def get_success_rate(self):
        """
        Calcula taxa de sucesso.

        Returns:
            float: Percentual (0-100)
        """
        if self.total_tests == 0:
            return 0.0

        return round((self.passed_tests / self.total_tests) * 100, 2)

    def get_results(self):
        """
        Retorna resultados da execução.

        Returns:
            QuerySet de TestResult
        """
        return self.test_results.select_related('test_case').order_by('executed_at')

    def get_failed_results(self):
        """Retorna apenas resultados falhados."""
        return self.test_results.filter(status='FAILED').select_related('test_case')

    def _generate_run_id(self):
        """
        Gera ID único para a execução.

        Formato: run-YYYYMMDD-NNN
        Exemplo: run-20260214-001
        """
        today = timezone.now().strftime('%Y%m%d')
        prefix = f"run-{today}-"
        prefix_len = len(prefix)

        # Buscar maior número do dia (inclui inativos para evitar colisão)
        last_run = (
            TestRun.all_objects
            .filter(run_id__startswith=prefix)
            .annotate(
                run_num=Cast(
                    Substr('run_id', prefix_len + 1),
                    output_field=IntegerField()
                )
            )
            .order_by('-run_num')
            .first()
        )

        new_num = (last_run.run_num + 1) if last_run else 1

        return f"{prefix}{new_num:03d}"

    # =============================================================================
    # PROPERTIES
    # =============================================================================

    @property
    def is_pending(self):
        """Verifica se está pendente."""
        return self.status == self.STATUS_PENDING

    @property
    def is_running(self):
        """Verifica se está executando."""
        return self.status == self.STATUS_RUNNING

    @property
    def is_completed(self):
        """Verifica se foi concluída."""
        return self.status == self.STATUS_COMPLETED

    @property
    def is_failed(self):
        """Verifica se falhou."""
        return self.status == self.STATUS_FAILED

    @property
    def is_cancelled(self):
        """Verifica se foi cancelada."""
        return self.status == self.STATUS_CANCELLED

    @property
    def is_finished(self):
        """Verifica se terminou (concluída, falhou ou cancelada)."""
        return self.status in [
            self.STATUS_COMPLETED,
            self.STATUS_FAILED,
            self.STATUS_CANCELLED
        ]

    @property
    def duration_formatted(self):
        """
        Retorna duração formatada.

        Returns:
            str: "2m 30s" ou "45s"
        """
        if not self.duration_seconds:
            return "0s"

        minutes = int(self.duration_seconds // 60)
        seconds = int(self.duration_seconds % 60)

        if minutes > 0:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"

    @property
    def success_rate(self):
        """Atalho para get_success_rate()."""
        return self.get_success_rate()
