from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.urls import reverse

from apps.commons.admin import BaseAdmin
from apps.environments.models import Environment

@admin.register(Environment)
class EnvironmentAdmin(BaseAdmin):
    """
    Admin para gerenciamento de ambientes de execução.

    Features:
    - Badge colorido por tipo de ambiente
    - Link para projeto
    - Contador de execuções
    - Filtros e buscas
    """

    # =============================================================================
    # LISTAGEM
    # =============================================================================

    list_display = (
        'project_link',
        'env_type_badge',
        'base_url_display',
        'test_runs_count_display',
        'is_active',
        'created_at',
    )

    list_filter = (
        'env_type',
        'is_active',
        'project',
        'created_at',
    )

    search_fields = (
        'base_url',
        'project__name',
    )

    ordering = ('project', 'env_type')

    list_per_page = 25

    # =============================================================================
    # FORMULÁRIO
    # =============================================================================

    fieldsets = (
        (
            _('Projeto'),
            {
                'fields': ('project',)
            }
        ),
        (
            _('Informações do Ambiente'),
            {
                'fields': (
                    'base_url',
                    'env_type',
                )
            }
        ),
        (
            _('Status'),
            {
                'fields': ('is_active',)
            }
        ),
        (
            _('Rastreabilidade'),
            {
                'classes': ('collapse',),
                'fields': (
                    'id',
                    'created_at',
                    'created_by',
                    'updated_at',
                    'updated_by',
                    'deleted_at',
                    'deleted_by',
                )
            }
        ),
    )

    readonly_fields = BaseAdmin.readonly_fields + ('is_active',)

    # Campos obrigatórios no form
    autocomplete_fields = ['project']

    # =============================================================================
    # COLUNAS CUSTOMIZADAS
    # =============================================================================

    @admin.display(description=_('Projeto'), ordering='project__name')
    def project_link(self, obj):
        """Link clicável para o projeto."""
        url = reverse('admin:projects_project_change', args=[obj.project.pk])
        return format_html(
            '<a href="{}">{}</a>',
            url,
            obj.project.name
        )

    @admin.display(description=_('Tipo'), ordering='env_type')
    def env_type_badge(self, obj):
        """Badge colorido por tipo de ambiente."""
        colors = {
            'development': '#17a2b8',  # Azul
            'staging': '#ffc107',      # Amarelo
            'production': '#dc3545',   # Vermelho
        }

        color = colors.get(obj.env_type, '#6c757d')
        label = obj.get_env_type_display()

        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold; display: inline-block;">'
            '{}</span>',
            color,
            label
        )

    @admin.display(description=_('URL'))
    def base_url_display(self, obj):
        """URL base com link clicável."""
        display_url = obj.base_url
        if len(display_url) > 50:
            display_url = display_url[:47] + '...'

        return format_html(
            '<a href="{}" target="_blank" title="{}">{}</a>',
            obj.base_url,
            obj.base_url,
            display_url
        )

    @admin.display(description=_('Execuções'))
    def test_runs_count_display(self, obj):
        """Contador de execuções com link."""
        count = 0
        if hasattr(obj, 'test_runs'):
            count = obj.test_runs.count()

        if count == 0:
            return format_html('<span style="color: gray;">0</span>')

        return format_html(
            '<span style="font-weight: bold; color: green;">{}</span>',
            count
        )

    # =============================================================================
    # OTIMIZAÇÕES DE QUERY
    # =============================================================================

    def get_queryset(self, request):
        """Otimiza queries."""
        qs = super().get_queryset(request)
        qs = qs.select_related('project', 'created_by')

        return qs

    # =============================================================================
    # AÇÕES EM LOTE
    # =============================================================================

    actions = ['activate_environments', 'deactivate_environments']

    @admin.action(description=_('Ativar ambientes selecionados'))
    def activate_environments(self, request, queryset):
        """Ativa ambientes selecionados."""
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            _(f'{updated} ambiente(s) ativado(s) com sucesso.'),
        )

    @admin.action(description=_('Desativar ambientes selecionados'))
    def deactivate_environments(self, request, queryset):
        """Desativa ambientes selecionados."""
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            _(f'{updated} ambiente(s) desativado(s) com sucesso.'),
        )
