from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.db.models import Count

from apps.commons.admin import BaseAdmin
from .models import TestCase, TestCaseAttachment


class TestCaseAttachmentInline(admin.TabularInline):
    """
    Inline para gerenciar anexos (imagens, PDFs) do caso de teste.

    Permite adicionar múltiplos anexos com preview de imagens.
    """

    model = TestCaseAttachment
    extra = 1

    fields = (
        'file',
        'title',
        'description',
        'attachment_type',
        'order',
        'preview_image',
        'uploaded_by',
    )

    readonly_fields = ('preview_image', 'uploaded_by')

    # Ordem padrão de exibição
    ordering = ('order', 'created_at')

    def preview_image(self, obj):
        """Exibe preview da imagem."""
        if not obj.file:
            return '-'

        if obj.is_image:
            return format_html(
                '<a href="{}" target="_blank">'
                '<img src="{}" style="max-width: 200px; max-height: 150px; '
                'border: 1px solid #ddd; border-radius: 4px; padding: 2px;" />'
                '</a>',
                obj.file.url,
                obj.file.url
            )
        else:
            # Para PDFs e outros arquivos
            return format_html(
                '<a href="{}" target="_blank">📄 Ver arquivo</a>',
                obj.file.url
            )

    preview_image.short_description = _('Preview')

    def get_queryset(self, request):
        """Otimiza query."""
        qs = super().get_queryset(request)
        return qs.select_related('uploaded_by')


# ============================================================================
# ADMIN - TEST CASE ATTACHMENT (Standalone)
# ============================================================================

@admin.register(TestCaseAttachment)
class TestCaseAttachmentAdmin(BaseAdmin):
    """
    Admin standalone para anexos (caso precise gerenciar separadamente).

    Normalmente os anexos são gerenciados via inline do TestCase.
    """

    list_display = (
        'test_case_link',
        'title',
        'attachment_type_badge',
        'order',
        'preview_thumb',
        'uploaded_by',
        'created_at',
    )

    list_filter = (
        'attachment_type',
        'test_case__project',
        'created_at',
    )

    search_fields = (
        'title',
        'description',
        'test_case__case_id',
        'test_case__title',
    )

    ordering = ('test_case', 'order', 'created_at')

    autocomplete_fields = ['test_case']

    readonly_fields = ('preview_full', 'uploaded_by', 'is_active', 'id','created_at', 'updated_at', 'deleted_at')

    fieldsets = (
        (
            _('Caso de Teste'),
            {
                'fields': ('test_case',)
            }
        ),
        (
            _('Informações do Anexo'),
            {
                'fields': (
                    'file',
                    'preview_full',
                    'title',
                    'description',
                    'attachment_type',
                    'order',
                )
            }
        ),
        (
            _('Rastreabilidade'),
            {
                'classes': ('collapse',),
                'fields': (
                    'id',
                    'uploaded_by',
                    'created_at',
                    'updated_at',
                    'deleted_at',
                )
            }
        ),
    )

    @admin.display(description=_('Caso de Teste'))
    def test_case_link(self, obj):
        """Link para o caso de teste."""
        url = reverse('admin:cases_testcase_change', args=[obj.test_case.pk])
        return format_html(
            '<a href="{}">{}</a>',
            url,
            obj.test_case
        )

    @admin.display(description=_('Tipo'))
    def attachment_type_badge(self, obj):
        """Badge colorido por tipo."""
        colors = {
            'IMAGE': '#28a745',
            'DOCUMENT': '#007bff',
            'OTHER': '#6c757d',
        }

        icons = {
            'IMAGE': '🖼️',
            'DOCUMENT': '📄',
            'OTHER': '📎',
        }

        color = colors.get(obj.attachment_type, '#6c757d')
        icon = icons.get(obj.attachment_type, '📎')
        label = obj.get_attachment_type_display()

        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{} {}</span>',
            color,
            icon,
            label
        )

    @admin.display(description=_('Preview'))
    def preview_thumb(self, obj):
        """Preview pequeno na listagem."""
        if obj.file and obj.is_image:
            return format_html(
                '<img src="{}" style="max-width: 50px; max-height: 50px;" />',
                obj.file.url
            )
        return '-'

    def preview_full(self, obj):
        """Preview grande no formulário."""
        if not obj.file:
            return '-'

        if obj.is_image:
            return format_html(
                '<a href="{}" target="_blank">'
                '<img src="{}" style="max-width: 600px; border: 1px solid #ddd; '
                'border-radius: 4px; padding: 5px;" />'
                '</a><br><br>'
                '<a href="{}" target="_blank" class="button">Abrir em nova aba</a>',
                obj.file.url,
                obj.file.url,
                obj.file.url
            )
        else:
            return format_html(
                '<a href="{}" target="_blank" class="button">📄 Baixar arquivo</a>',
                obj.file.url
            )

    preview_full.short_description = _('Preview do Arquivo')


# ============================================================================
# ADMIN - TEST CASE
# ============================================================================

@admin.register(TestCase)
class TestCaseAdmin(BaseAdmin):
    """
    Admin para gerenciamento de casos de teste.

    Features:
    - Inline para adicionar anexos com preview
    - Badge de status colorido
    - Filtros por projeto, status, módulo, tags
    - Busca por ID, título, playwright_id
    - Contadores de anexos e resultados
    - Ações em lote
    """

    # =============================================================================
    # LISTAGEM
    # =============================================================================

    list_display = (
        'case_id',
        'title',
        'project_link',
        'status_badge',
        'module_display',
        'attachments_count_display',
        'results_count_display',
        'playwright_link_display',
        'created_by',
        'created_at',
    )

    list_filter = (
        'status',
        'project',
        'module',
        'tags',
        'created_at',
        'is_active',
    )

    search_fields = (
        'case_id',
        'title',
        'playwright_id',
        'module',
        'objective',
        'project__name',
    )

    ordering = ('project', 'case_id')

    list_per_page = 25

    # Filtro horizontal para tags
    filter_horizontal = ('tags',)

    # Autocomplete para FKs
    autocomplete_fields = ['project', 'created_by', 'last_modified_by']

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
            _('Identificação'),
            {
                'fields': (
                    'case_id',
                    'title',
                    'slug',
                    'status',
                    'module',
                )
            }
        ),
        (
            _('Documentação'),
            {
                'fields': (
                    'objective',
                    'preconditions',
                    'postconditions',
                    'expected_result',
                    'observations',
                )
            }
        ),
        (
            _('Vínculo com Playwright'),
            {
                'fields': (
                    'test_title',
                    'playwright_id',
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
                    'last_modified_by',
                    'deleted_at',
                    'deleted_by',
                )
            }
        ),
    )

    readonly_fields = BaseAdmin.readonly_fields + (
        'slug',
        'last_modified_by',
        'is_active',
    )

    # Inline de anexos
    inlines = [TestCaseAttachmentInline]

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

    @admin.display(description=_('Status'), ordering='status')
    def status_badge(self, obj):
        """Badge colorido por status."""
        colors = {
            'DRAFT': '#6c757d',      # Cinza
            'ACTIVE': '#28a745',     # Verde
            'DEPRECATED': '#ffc107', # Amarelo
        }

        icons = {
            'DRAFT': '📝',
            'ACTIVE': '✅',
            'DEPRECATED': '⚠️',
        }

        color = colors.get(obj.status, '#6c757d')
        icon = icons.get(obj.status, '📋')
        label = obj.get_status_display()

        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold; display: inline-block;">'
            '{} {}</span>',
            color,
            icon,
            label
        )

    @admin.display(description=_('Módulo'))
    def module_display(self, obj):
        """Exibe módulo com formatação."""
        if not obj.module:
            return format_html('<span style="color: gray;">-</span>')
        return obj.module

    @admin.display(description=_('Anexos'))
    def attachments_count_display(self, obj):
        """Contador de anexos."""
        count = obj._attachments_count

        if count == 0:
            return format_html('<span style="color: gray;">0</span>')

        return format_html(
            '<span style="font-weight: bold; color: #007bff;">📎 {}</span>',
            count
        )

    @admin.display(description=_('Resultados'))
    def results_count_display(self, obj):
        """Contador de resultados (quando TestResult existir)."""
        if not hasattr(obj, 'test_results'):
            return format_html('<span style="color: gray;">-</span>')

        count = obj.test_results.count()

        if count == 0:
            return format_html('<span style="color: gray;">0</span>')

        # Link para filtrar resultados (futuro)
        return format_html(
            '<span style="font-weight: bold; color: green;">📊 {}</span>',
            count
        )

    @admin.display(description=_('Playwright'))
    def playwright_link_display(self, obj):
        """Indica se está vinculado ao Playwright."""
        if obj.has_playwright_link:
            return format_html(
                '<span style="color: green; font-weight: bold;" title="{}">'
                '🔗 {}</span>',
                obj.playwright_id,
                obj.playwright_id[:20] + '...' if len(obj.playwright_id) > 20 else obj.playwright_id
            )
        return format_html('<span style="color: gray;">-</span>')

    # =============================================================================
    # OTIMIZAÇÕES DE QUERY
    # =============================================================================

    def get_queryset(self, request):
        """Otimiza queries."""
        qs = super().get_queryset(request)

        # Carrega relações de uma vez
        qs = qs.select_related(
            'project',
            'created_by',
            'last_modified_by'
        )

        # Prefetch tags e anexos
        qs = qs.prefetch_related('tags', 'attachments')

        # Adiciona contadores via anotação
        qs = qs.annotate(
            _attachments_count=Count('attachments', distinct=True),
        )

        return qs

    # =============================================================================
    # AÇÕES EM LOTE
    # =============================================================================

    actions = [
        'change_to_active',
        'change_to_draft',
        'change_to_deprecated',
        'archive_cases',
    ]

    @admin.action(description=_('Marcar como ATIVO'))
    def change_to_active(self, request, queryset):
        """Muda status para ATIVO."""
        updated = 0
        for obj in queryset:
            obj.change_status(TestCase.STATUS_ACTIVE, user=request.user)
            updated += 1

        self.message_user(
            request,
            _(f'{updated} caso(s) marcado(s) como ATIVO.'),
        )

    @admin.action(description=_('Marcar como RASCUNHO'))
    def change_to_draft(self, request, queryset):
        """Muda status para RASCUNHO."""
        updated = 0
        for obj in queryset:
            obj.change_status(TestCase.STATUS_DRAFT, user=request.user)
            updated += 1

        self.message_user(
            request,
            _(f'{updated} caso(s) marcado(s) como RASCUNHO.'),
        )

    @admin.action(description=_('Marcar como DEPRECIADO'))
    def change_to_deprecated(self, request, queryset):
        """Muda status para DEPRECIADO."""
        updated = 0
        for obj in queryset:
            obj.change_status(TestCase.STATUS_DEPRECATED, user=request.user)
            updated += 1

        self.message_user(
            request,
            _(f'{updated} caso(s) marcado(s) como DEPRECIADO.'),
            level='WARNING'
        )

    @admin.action(description=_('Arquivar casos selecionados'))
    def archive_cases(self, request, queryset):
        """Arquiva casos de teste (soft delete)."""
        updated = 0
        for obj in queryset:
            obj.archive(user=request.user)
            updated += 1

        self.message_user(
            request,
            _(f'{updated} caso(s) arquivado(s) com sucesso.'),
            level='WARNING'
        )

    # =============================================================================
    # CUSTOMIZAÇÕES EXTRAS
    # =============================================================================

    def save_model(self, request, obj, form, change):
        """Override para preencher last_modified_by (BaseAdmin já trata created_by/updated_by)."""
        obj.last_modified_by = request.user
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        """Override para preencher uploaded_by nos anexos e tratar deleções."""
        instances = formset.save(commit=False)

        for instance in instances:
            if isinstance(instance, TestCaseAttachment):
                if not instance.pk:  # Novo anexo
                    instance.uploaded_by = request.user
            instance.save()

        for instance in formset.deleted_objects:
            instance.delete()

        formset.save_m2m()
