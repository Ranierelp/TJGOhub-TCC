from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.db.models import Count

from apps.commons.admin import BaseAdmin
from apps.projects.models import Project


@admin.register(Project)
class ProjectAdmin(BaseAdmin):
    """
    Admin para gerenciamento de projetos.

    Funcionalidades:
    - Listagem com contadores (ambientes, casos de teste, execuções)
    - Busca por nome e slug
    - Filtros por status e data
    - Ações em lote (arquivar, reativar)
    - Campos readonly automáticos
    """

    # =============================================================================
    # LISTAGEM
    # =============================================================================

    list_display = (
        'name',
        'slug',
        'status_badge',
        'environments_count_display',
        'test_cases_count_display',
        'test_runs_count_display',
        'created_by',
        'created_at',
    )

    list_filter = (
        'is_active',
        'created_at',
        'updated_at',
    )

    search_fields = (
        'name',
        'slug',
        'description',
    )

    ordering = ('-created_at',)

    # Mostrar N registros por página
    list_per_page = 25

    # =============================================================================
    # FORMULÁRIO
    # =============================================================================

    fieldsets = (
        (
            _('Informações Básicas'),
            {
                'fields': (
                    'name',
                    'slug',
                    'description',
                )
            }
        ),
        (
            _('Status'),
            {
                'fields': (
                    'is_active',
                )
            }
        ),
        (
            _('Rastreabilidade'),
            {
                'classes': ('collapse',),  # Seção recolhida por padrão
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

    # Campos que não podem ser editados
    readonly_fields = BaseAdmin.readonly_fields + ('slug', 'is_active')

    # Campos que aparecem ao criar (excluir readonly)
    def get_fields(self, request, obj=None):
        """Remove campos readonly ao criar novo projeto."""
        fields = super().get_fields(request, obj)
        if obj is None:  # Criando novo
            # Remove campos de rastreabilidade que serão preenchidos automaticamente
            exclude = ['id', 'created_at', 'created_by', 'updated_at', 'updated_by', 'deleted_at', 'deleted_by', 'slug']
            return [f for f in fields if f not in exclude]
        return fields

    # =============================================================================
    # COLUNAS CUSTOMIZADAS
    # =============================================================================

    @admin.display(description=_('Status'), ordering='is_active')
    def status_badge(self, obj):
        """Exibe badge colorido do status."""
        if obj.is_active:
            color = 'green'
            text = 'Ativo'
            icon = '✓'
        else:
            color = 'gray'
            text = 'Arquivado'
            icon = '✗'

        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{} {}</span>',
            color,
            icon,
            text
        )

    @admin.display(description=_('Ambientes'))
    def environments_count_display(self, obj):
        """Exibe contagem de ambientes com link."""
        count = obj.environments.filter(is_active=True).count()

        if count == 0:
            return format_html('<span style="color: gray;">0</span>')

        # Link para filtrar ambientes deste projeto
        url = reverse('admin:environments_environment_changelist') + f'?project__id__exact={obj.pk}'
        return format_html(
            '<a href="{}" style="font-weight: bold;">{}</a>',
            url,
            count
        )

    @admin.display(description=_('Casos de Teste'))
    def test_cases_count_display(self, obj):
        """Exibe contagem de casos de teste com link."""
        count = obj.test_cases.filter(is_active=True).count()

        if count == 0:
            return format_html('<span style="color: gray;">0</span>')

        # Link para filtrar casos de teste deste projeto
        url = reverse('admin:cases_testcase_changelist') + f'?project__id__exact={obj.pk}'
        return format_html(
            '<a href="{}" style="font-weight: bold; color: blue;">{}</a>',
            url,
            count
        )

    @admin.display(description=_('Execuções'))
    def test_runs_count_display(self, obj):
        """Exibe contagem de execuções com link."""
        count = obj.test_runs.count()

        if count == 0:
            return format_html('<span style="color: gray;">0</span>')

        # Link para filtrar execuções deste projeto
        url = reverse('admin:runs_testrun_changelist') + f'?project__id__exact={obj.pk}'
        return format_html(
            '<a href="{}" style="font-weight: bold; color: green;">{}</a>',
            url,
            count
        )

    # =============================================================================
    # OTIMIZAÇÕES DE QUERY
    # =============================================================================

    def get_queryset(self, request):
        """Otimiza queries com select_related e prefetch_related."""
        # all_objects inclui projetos arquivados (is_active=False)
        # Necessário para que o filtro is_active funcione no admin
        return (
            Project.all_objects.all()
            .select_related("created_by")
            .annotate(
                _environments_count=Count("environments", distinct=True),
                _test_cases_count=Count("test_cases", distinct=True),
                _test_runs_count=Count("test_runs", distinct=True),
            )
        )

    # =============================================================================
    # AÇÕES EM LOTE
    # =============================================================================

    actions = ['archive_projects', 'activate_projects']

    @admin.action(description=_('Arquivar projetos selecionados'))
    def archive_projects(self, request, queryset):
        """Arquiva projetos selecionados."""
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            _(f'{updated} projeto(s) arquivado(s) com sucesso.'),
        )

    @admin.action(description=_('Reativar projetos selecionados'))
    def activate_projects(self, request, queryset):
        """Reativa projetos arquivados."""
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            _(f'{updated} projeto(s) reativado(s) com sucesso.'),
        )

    # =============================================================================
    # CUSTOMIZAÇÕES EXTRAS
    # =============================================================================

    def has_delete_permission(self, request, obj=None):
        """
        Desabilita deleção hard delete.

        Projetos devem ser arquivados, não deletados.
        """
        # Apenas superusuários podem deletar permanentemente
        return request.user.is_superuser
