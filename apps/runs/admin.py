# apps/runs/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.urls import reverse

from apps.commons.admin import BaseAdmin
from apps.runs.models import TestRun


@admin.register(TestRun)
class TestRunAdmin(BaseAdmin):
    """
    Admin para gerenciamento de execuções de teste.

    Features:
    - Dashboard com métricas visuais
    - Badge de status colorido
    - Taxa de sucesso com barra de progresso
    - Links para projeto e ambiente
    - Filtros avançados
    - Ações em lote
    """

    # =============================================================================
    # LISTAGEM
    # =============================================================================

    list_display = (
        'run_id',
        'project_link',
        'environment_link',
        'status_badge',
        'success_rate_display',
        'metrics_summary',
        'duration_display',
        'branch_commit',
        'triggered_by',
        'started_at',
    )

    list_filter = (
        'status',
        'trigger_type',
        'project',
        'environment',
        'branch',
        'started_at',
        'is_active',
    )

    search_fields = (
        'run_id',
        'branch',
        'commit_sha',
        'commit_message',
        'project__name',
        'environment__name',
    )

    ordering = ('-started_at', '-created_at')

    list_per_page = 25

    # Autocomplete
    autocomplete_fields = ['project', 'environment', 'triggered_by']

    # Filtro horizontal para tags
    filter_horizontal = ('tags',)

    # =============================================================================
    # FORMULÁRIO
    # =============================================================================

    fieldsets = (
        (
            _('Identificação'),
            {
                'fields': (
                    'run_id',
                    'project',
                    'environment',
                    'status',
                    'trigger_type',
                )
            }
        ),
        (
            _('Integração Git'),
            {
                'fields': (
                    'branch',
                    'commit_sha',
                    'commit_message',
                )
            }
        ),
        (
            _('Métricas'),
            {
                'fields': (
                    'total_tests',
                    'passed_tests',
                    'failed_tests',
                    'skipped_tests',
                    'flaky_tests',
                    'duration_seconds',
                )
            }
        ),
        (
            _('Timestamps'),
            {
                'fields': (
                    'started_at',
                    'completed_at',
                )
            }
        ),
        (
            _('Categorização'),
            {
                'fields': ('tags',)
            }
        ),
        (
            _('Rastreabilidade'),
            {
                'classes': ('collapse',),
                'fields': (
                    'id',
                    'triggered_by',
                    'created_at',
                    'created_by',
                    'updated_at',
                    'updated_by',
                    'deleted_at',
                    'deleted_by',
                    'is_active',
                )
            }
        ),
    )

    readonly_fields = BaseAdmin.readonly_fields + (
        'run_id',
        'triggered_by',
        'is_active',
    )

    # =============================================================================
    # COLUNAS CUSTOMIZADAS
    # =============================================================================

    @admin.display(description=_('Projeto'), ordering='project__name')
    def project_link(self, obj):
        """Link para o projeto."""
        url = reverse('admin:projects_project_change', args=[obj.project.pk])
        return format_html(
            '<a href="{}">{}</a>',
            url,
            obj.project.name
        )

    @admin.display(description=_('Ambiente'), ordering='environment__env_type')
    def environment_link(self, obj):
        """Link para o ambiente."""
        url = reverse('admin:environments_environment_change', args=[obj.environment.pk])

        # Badge colorido por tipo de ambiente
        env_colors = {
            'development': '#17a2b8',
            'staging': '#ffc107',
            'production': '#dc3545',
        }
        color = env_colors.get(obj.environment.env_type, '#6c757d')

        return format_html(
            '<a href="{}" style="color: {}; font-weight: bold;">{}</a>',
            url,
            color,
            obj.environment.get_env_type_display()
        )

    @admin.display(description=_('Status'), ordering='status')
    def status_badge(self, obj):
        """Badge colorido por status."""
        colors = {
            'PENDING': '#6c757d',
            'RUNNING': '#17a2b8',
            'COMPLETED': '#28a745',
            'FAILED': '#dc3545',
            'CANCELLED': '#ffc107',
        }

        icons = {
            'PENDING': '⏳',
            'RUNNING': '▶️',
            'COMPLETED': '✅',
            'FAILED': '❌',
            'CANCELLED': '⛔',
        }

        color = colors.get(obj.status, '#6c757d')
        icon = icons.get(obj.status, '📋')
        label = obj.get_status_display()

        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 12px; '
            'border-radius: 4px; font-weight: bold; display: inline-block;">'
            '{} {}</span>',
            color,
            icon,
            label
        )

    @admin.display(description=_('Taxa de Sucesso'))
    def success_rate_display(self, obj):
        """Taxa de sucesso com barra de progresso."""
        rate = obj.get_success_rate()

        # Cor baseada na taxa
        if rate >= 90:
            color = '#28a745'  # Verde
        elif rate >= 70:
            color = '#ffc107'  # Amarelo
        else:
            color = '#dc3545'  # Vermelho

        return format_html(
            '<div style="display: flex; align-items: center; gap: 8px;">'
            '<div style="flex: 1; background: #e9ecef; border-radius: 4px; height: 20px; overflow: hidden;">'
            '<div style="background: {}; width: {}%; height: 100%;"></div>'
            '</div>'
            '<span style="font-weight: bold; min-width: 50px;">{}%</span>'
            '</div>',
            color,
            rate,
            f"{rate:.1f}"
        )

    @admin.display(description=_('Testes'))
    def metrics_summary(self, obj):
        """Resumo visual das métricas."""
        if obj.total_tests == 0:
            return format_html('<span style="color: gray;">Sem testes</span>')

        flaky_html = ''
        if obj.flaky_tests > 0:
            flaky_html = f'<div style="color: #ffc107;">⚠ Flaky: {obj.flaky_tests}</div>'

        return format_html(
            '<div style="font-size: 11px; line-height: 1.4;">'
            '<div><strong>Total:</strong> {}</div>'
            '<div style="color: #28a745;">✓ Passou: {}</div>'
            '<div style="color: #dc3545;">✗ Falhou: {}</div>'
            '{}'
            '</div>',
            obj.total_tests,
            obj.passed_tests,
            obj.failed_tests,
            flaky_html
        )

    @admin.display(description=_('Duração'))
    def duration_display(self, obj):
        """Duração formatada."""
        if not obj.duration_seconds:
            return format_html('<span style="color: gray;">-</span>')

        return format_html(
            '<span style="font-family: monospace;">{}</span>',
            obj.duration_formatted
        )

    @admin.display(description=_('Branch / Commit'))
    def branch_commit(self, obj):
        """Branch e commit SHA."""
        if not obj.branch and not obj.commit_sha:
            return format_html('<span style="color: gray;">-</span>')

        branch = obj.branch or 'N/A'
        commit = obj.commit_sha[:7] if obj.commit_sha else 'N/A'

        return format_html(
            '<div style="font-size: 11px;">'
            '<div><strong>{}</strong></div>'
            '<code style="color: #6c757d;">{}</code>'
            '</div>',
            branch,
            commit
        )

    # =============================================================================
    # OTIMIZAÇÕES DE QUERY
    # =============================================================================

    def get_queryset(self, request):
        """Otimiza queries."""
        qs = super().get_queryset(request)

        # Carrega relações de uma vez
        qs = qs.select_related(
            'project',
            'environment',
            'triggered_by',
            'created_by',
            'updated_by'
        )

        # Prefetch tags
        qs = qs.prefetch_related('tags')

        return qs

    # =============================================================================
    # AÇÕES EM LOTE
    # =============================================================================

    actions = ['cancel_runs', 'recalculate_metrics']

    @admin.action(description=_('Cancelar execuções selecionadas'))
    def cancel_runs(self, request, queryset):
        """Cancela execuções em andamento."""
        cancelled = 0
        cannot_cancel = 0

        for test_run in queryset:
            if test_run.is_finished:
                cannot_cancel += 1
                continue

            try:
                test_run.cancel(user=request.user)
                cancelled += 1
            except Exception:
                cannot_cancel += 1

        if cancelled > 0:
            self.message_user(
                request,
                _(f'{cancelled} execução(ões) cancelada(s) com sucesso.')
            )

        if cannot_cancel > 0:
            self.message_user(
                request,
                _(f'{cannot_cancel} execução(ões) não puderam ser canceladas (já finalizadas).'),
                level='WARNING'
            )

    @admin.action(description=_('Recalcular métricas'))
    def recalculate_metrics(self, request, queryset):
        """Recalcula métricas a partir dos TestResults."""
        updated = 0

        for test_run in queryset:
            test_run.calculate_metrics()
            test_run.save(update_fields=[
                'total_tests', 'passed_tests', 'failed_tests',
                'skipped_tests', 'flaky_tests', 'duration_seconds',
                'updated_at',
            ])
            updated += 1

        self.message_user(
            request,
            _(f'Métricas de {updated} execução(ões) recalculadas.')
        )

    # =============================================================================
    # CUSTOMIZAÇÕES
    # =============================================================================

    def has_delete_permission(self, request, obj=None):
        """Apenas superuser pode deletar."""
        return request.user.is_superuser

    def save_model(self, request, obj, form, change):
        """Override para preencher triggered_by."""
        if not change and not obj.triggered_by:
            obj.triggered_by = request.user

        super().save_model(request, obj, form, change)
