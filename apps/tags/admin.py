from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.db.models import Count
from django.core.exceptions import ValidationError

from .models import Tag

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    """
    Admin para gerenciamento de tags.

    Features:
    - Preview de cor ao lado do nome
    - Contador de usos (casos de teste + execuções)
    - Proteção contra deleção se em uso
    - Widget de cor
    """

    # =============================================================================
    # LISTAGEM
    # =============================================================================

    list_display = (
        'name_with_color',
        'color_preview',
        'description_short',
        'usage_count_display',
        'created_at',
    )

    list_filter = (
        'created_at',
    )

    search_fields = (
        'name',
        'description',
    )

    ordering = ('name',)

    list_per_page = 50

    # =============================================================================
    # FORMULÁRIO
    # =============================================================================

    fieldsets = (
        (
            _('Informações da Tag'),
            {
                'fields': (
                    'name',
                    'color',
                    'color_preview_form',
                    'description',
                )
            }
        ),
        (
            _('Informações do Sistema'),
            {
                'classes': ('collapse',),
                'fields': (
                    'id',
                    'created_at',
                )
            }
        ),
    )

    readonly_fields = ('id', 'created_at', 'color_preview_form')

    # =============================================================================
    # COLUNAS CUSTOMIZADAS
    # =============================================================================

    @admin.display(description=_('Tag'), ordering='name')
    def name_with_color(self, obj):
        """Nome da tag com badge colorido."""
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 12px; '
            'border-radius: 4px; font-weight: bold; display: inline-block;">'
            '{}</span>',
            obj.color,
            obj.name
        )

    @admin.display(description=_('Cor'))
    def color_preview(self, obj):
        """Preview da cor (quadrado colorido + código hex)."""
        return format_html(
            '<div style="display: flex; align-items: center; gap: 8px;">'
            '<div style="width: 30px; height: 30px; background-color: {}; '
            'border: 2px solid #ddd; border-radius: 4px;"></div>'
            '<code>{}</code>'
            '</div>',
            obj.color,
            obj.color
        )

    @admin.display(description=_('Descrição'))
    def description_short(self, obj):
        """Descrição truncada."""
        if not obj.description:
            return format_html('<span style="color: gray;">-</span>')

        if len(obj.description) > 50:
            return obj.description[:47] + '...'
        return obj.description

    @admin.display(description=_('Uso'))
    def usage_count_display(self, obj):
        """Contador de uso com breakdown."""
        # Usar contadores anotados se disponíveis
        test_cases = getattr(obj, '_test_cases_count', None)
        test_runs = getattr(obj, '_test_runs_count', None)

        # Fallback para query direta
        if test_cases is None:
            test_cases = obj.test_cases.filter(is_active=True).count()
        if test_runs is None:
            test_runs = 0
            if hasattr(obj, 'test_runs'):
                test_runs = obj.test_runs.count()

        total = test_cases + test_runs

        if total == 0:
            return format_html('<span style="color: gray;">Não usado</span>')

        return format_html(
            '<span style="font-weight: bold;" title="Casos: {} | Execuções: {}">'
            '📊 {} uso(s)</span>',
            test_cases,
            test_runs,
            total
        )

    def color_preview_form(self, obj):
        """Preview grande da cor no formulário."""
        if not obj or not obj.color:
            return '-'

        return format_html(
            '<div style="width: 100px; height: 100px; background-color: {}; '
            'border: 2px solid #ddd; border-radius: 8px; margin: 10px 0;"></div>'
            '<p><strong>Código:</strong> <code>{}</code></p>'
            '<p><strong>RGB:</strong> {}</p>',
            obj.color,
            obj.color,
            obj.color_rgb if hasattr(obj, 'color_rgb') else 'N/A'
        )

    color_preview_form.short_description = _('Preview da Cor')

    # =============================================================================
    # OTIMIZAÇÕES DE QUERY
    # =============================================================================

    def get_queryset(self, request):
        """Otimiza queries com contadores."""
        qs = super().get_queryset(request)

        # Adiciona contadores via anotação
        qs = qs.annotate(
            _test_cases_count=Count('test_cases', distinct=True),
        )

        # test_runs só depois que o model existir
        # qs = qs.annotate(
        #     _test_runs_count=Count('test_runs', distinct=True),
        # )

        return qs

    # =============================================================================
    # PROTEÇÃO CONTRA DELEÇÃO
    # =============================================================================

    def has_delete_permission(self, request, obj=None):
        """Impede deleção se tag estiver em uso."""
        if obj is None:
            return True

        # Verificar se está em uso
        test_cases_count = obj.test_cases.filter(is_active=True).count()
        test_runs_count = 0
        if hasattr(obj, 'test_runs'):
            test_runs_count = obj.test_runs.count()

        # Apenas superuser pode deletar tags em uso
        if test_cases_count > 0 or test_runs_count > 0:
            return request.user.is_superuser

        return True

    def delete_model(self, request, obj):
        """Override para validar antes de deletar."""
        usage = obj.get_usage_count()

        if usage['total'] > 0 and not request.user.is_superuser:
            self.message_user(
                request,
                _(f"Não é possível deletar '{obj.name}'. "
                  f"Tag está em uso em {usage['total']} item(s)."),
                level='ERROR'
            )
            return

        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        """Override para validar deleção em lote."""
        cannot_delete = []

        for obj in queryset:
            usage = obj.get_usage_count()
            if usage['total'] > 0 and not request.user.is_superuser:
                cannot_delete.append(obj.name)

        if cannot_delete:
            self.message_user(
                request,
                _(f"Não foi possível deletar algumas tags em uso: {', '.join(cannot_delete)}"),
                level='WARNING'
            )
            # Remove tags em uso do queryset
            queryset = queryset.exclude(name__in=cannot_delete)

        # Deleta apenas as tags não usadas
        super().delete_queryset(request, queryset)

