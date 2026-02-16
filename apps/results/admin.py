import csv
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.http import HttpResponse

from apps.commons.admin import BaseAdmin
from apps.results.models import TestResult


@admin.register(TestResult)
class TestResultAdmin(BaseAdmin):
    """Admin para resultados individuais de testes."""

    list_display = (
        'result_id',
        'test_run_link',
        'test_case_link',
        'status_badge',
        'duration_display',
        'error_preview',
        'artifacts_count',
        'executed_at',
    )

    list_filter = (
        'status',
        'test_run__project',
        'test_run',
        'executed_at',
    )

    search_fields = (
        'result_id',
        'error_message',
        'test_case__title',
        'test_run__run_id',
    )

    ordering = ('-executed_at',)
    list_per_page = 50
    autocomplete_fields = ['test_run', 'test_case']

    fieldsets = (
        (_('Identificação'), {
            'fields': ('result_id', 'test_run', 'test_case', 'status')
        }),
        (_('Métricas'), {
            'fields': ('duration_seconds', 'retry_number', 'executed_at')
        }),
        (_('Erro'), {
            'fields': ('error_message', 'stack_trace')
        }),
        (_('Metadados'), {
            'classes': ('collapse',),
            'fields': ('metadata',)
        }),
    )

    readonly_fields = (
        'result_id', 'test_run', 'test_case', 'status',
        'duration_seconds', 'retry_number', 'executed_at',
        'error_message', 'stack_trace', 'metadata'
    )

    @admin.display(description=_('Execução'))
    def test_run_link(self, obj):
        url = reverse('admin:runs_testrun_change', args=[obj.test_run.pk])
        return format_html('<a href="{}">{}</a>', url, obj.test_run.run_id)

    @admin.display(description=_('Caso'))
    def test_case_link(self, obj):
        if not obj.test_case:
            return format_html('<span style="color: #ffc107;">⚠️ Sem vínculo</span>')
        url = reverse('admin:cases_testcase_change', args=[obj.test_case.pk])
        return format_html('<a href="{}">{}</a>', url, obj.test_case.title)

    @admin.display(description=_('Status'))
    def status_badge(self, obj):
        colors = {
            'PASSED': '#28a745',
            'FAILED': '#dc3545',
            'SKIPPED': '#6c757d',
            'FLAKY': '#ffc107'
        }
        icons = {
            'PASSED': '✅',
            'FAILED': '❌',
            'SKIPPED': '⏭️',
            'FLAKY': '⚠️'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 12px; border-radius: 4px;">{} {}</span>',
            colors.get(obj.status, '#6c757d'),
            icons.get(obj.status, '📋'),
            obj.get_status_display()
        )

    @admin.display(description=_('Duração'))
    def duration_display(self, obj):
        if not obj.duration_seconds:
            return '-'
        color = '#28a745' if obj.duration_seconds < 5 else '#ffc107' if obj.duration_seconds < 30 else '#dc3545'
        return format_html('<span style="color: {};">{}</span>', color, obj.duration_formatted)

    @admin.display(description=_('Erro'))
    def error_preview(self, obj):
        if not obj.error_message:
            return '-'
        preview = obj.error_message[:60] + '...' if len(obj.error_message) > 60 else obj.error_message
        return format_html('<code style="color: #dc3545;">{}</code>', preview)

    @admin.display(description=_('Artefatos'))
    def artifacts_count(self, obj):
        count = obj.get_artifacts_count() if hasattr(obj, 'get_artifacts_count') else 0
        return f'📎 {count}' if count > 0 else '-'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('test_run', 'test_case', 'test_run__project')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    actions = ['mark_as_flaky', 'export_errors']

    @admin.action(description=_('Marcar como Flaky'))
    def mark_as_flaky(self, request, queryset):
        updated = 0
        for result in queryset:
            if result.status != TestResult.STATUS_FLAKY:
                result.mark_as_flaky()
                updated += 1
        self.message_user(request, f'{updated} resultado(s) marcado(s) como flaky.')

    @admin.action(description=_('Exportar erros CSV'))
    def export_errors(self, request, queryset):

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="errors.csv"'

        writer = csv.writer(response)
        writer.writerow(['ID', 'Caso', 'Status', 'Erro', 'Data'])

        for r in queryset.filter(status=TestResult.STATUS_FAILED):
            writer.writerow([
                r.result_id,
                r.test_name,
                r.get_status_display(),
                r.get_error_summary() if hasattr(r, 'get_error_summary') else r.error_message[:100],
                r.executed_at.strftime('%Y-%m-%d %H:%M:%S')
            ])

        return response
