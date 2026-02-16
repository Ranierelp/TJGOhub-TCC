from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.urls import reverse

from apps.commons.admin import BaseAdmin
from apps.artifacts.models import Artifact


@admin.register(Artifact)
class ArtifactAdmin(BaseAdmin):
    """
    Admin para gerenciamento de artefatos de teste.

    Features:
    - Preview de imagens e vídeos
    - Download direto
    - Filtros por tipo
    - Badge por tipo de arquivo
    """

    # =============================================================================
    # LISTAGEM
    # =============================================================================

    list_display = (
        'title',
        'artifact_type_badge',
        'test_result_link',
        'preview_thumb',
        'file_name',
        'file_size_display',
        'uploaded_by',
        'created_at',
    )

    list_filter = (
        'artifact_type',
        'test_result__test_run__project',
        'test_result__test_run',
        'created_at',
        'is_active',
    )

    search_fields = (
        'title',
        'file_name',
        'description',
        'test_result__result_id',
        'test_result__test_run__run_id',
    )

    ordering = ('-created_at',)

    list_per_page = 50

    # Autocomplete
    autocomplete_fields = ['test_result', 'uploaded_by']

    # =============================================================================
    # FORMULÁRIO
    # =============================================================================

    fieldsets = (
        (
            _('Resultado do Teste'),
            {
                'fields': ('test_result',)
            }
        ),
        (
            _('Arquivo'),
            {
                'fields': (
                    'file',
                    'artifact_type',
                    'title',
                    'description',
                )
            }
        ),
        (
            _('Preview'),
            {
                'fields': ('preview_large',)
            }
        ),
        (
            _('Metadados'),
            {
                'classes': ('collapse',),
                'fields': (
                    'file_name',
                    'file_size',
                    'mime_type',
                    'thumbnail_path',
                )
            }
        ),
        (
            _('Sistema'),
            {
                'classes': ('collapse',),
                'fields': (
                    'id',
                    'uploaded_by',
                    'created_at',
                    'updated_at',
                )
            }
        ),
    )

    readonly_fields = (
        'file_name',
        'file_size',
        'mime_type',
        'thumbnail_path',
        'preview_large',
        'id',
        'uploaded_by',
        'created_at',
        'updated_at',
    )

    # =============================================================================
    # COLUNAS CUSTOMIZADAS
    # =============================================================================

    @admin.display(description=_('Tipo'), ordering='artifact_type')
    def artifact_type_badge(self, obj):
        """Badge colorido por tipo de artefato."""
        colors = {
            'SCREENSHOT': '#007bff',  # Azul
            'VIDEO': '#6f42c1',       # Roxo
            'TRACE': '#fd7e14',       # Laranja
            'LOG': '#6c757d',         # Cinza
        }

        icons = {
            'SCREENSHOT': '📸',
            'VIDEO': '🎥',
            'TRACE': '📊',
            'LOG': '📄',
        }

        color = colors.get(obj.artifact_type, '#6c757d')
        icon = icons.get(obj.artifact_type, '📎')
        label = obj.get_artifact_type_display()

        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 12px; '
            'border-radius: 4px; font-weight: bold; display: inline-block;">'
            '{} {}</span>',
            color,
            icon,
            label
        )

    @admin.display(description=_('Resultado'))
    def test_result_link(self, obj):
        """Link para o resultado do teste."""
        url = reverse('admin:results_testresult_change', args=[obj.test_result.pk])

        # Status do resultado
        status_colors = {
            'PASSED': '#28a745',
            'FAILED': '#dc3545',
            'SKIPPED': '#6c757d',
            'FLAKY': '#ffc107',
        }
        color = status_colors.get(obj.test_result.status, '#6c757d')

        return format_html(
            '<a href="{}" style="font-weight: bold;">{}</a><br>'
            '<span style="font-size: 11px; color: {};">{}</span>',
            url,
            obj.test_result.result_id,
            color,
            obj.test_result.get_status_display()
        )

    @admin.display(description=_('Preview'))
    def preview_thumb(self, obj):
        """Preview pequeno na listagem."""
        if obj.is_image():
            return format_html(
                '<a href="{}" target="_blank">'
                '<img src="{}" style="max-width: 80px; max-height: 60px; '
                'border: 1px solid #ddd; border-radius: 4px;" />'
                '</a>',
                obj.get_file_url(),
                obj.get_file_url()
            )
        elif obj.is_video():
            return format_html(
                '<a href="{}" target="_blank" style="font-size: 30px;">▶️</a>',
                obj.get_file_url()
            )
        else:
            return format_html('<span style="font-size: 24px;">📄</span>')

    @admin.display(description=_('Tamanho'))
    def file_size_display(self, obj):
        """Tamanho formatado."""
        return obj.format_file_size()

    def preview_large(self, obj):
        """Preview grande no formulário."""
        if not obj.file:
            return '-'

        if obj.is_image():
            return format_html(
                '<div style="margin: 20px 0;">'
                '<a href="{}" target="_blank">'
                '<img src="{}" style="max-width: 100%; max-height: 600px; '
                'border: 2px solid #ddd; border-radius: 8px; padding: 5px; '
                'background: white;" />'
                '</a>'
                '</div>'
                '<div style="margin: 10px 0;">'
                '<a href="{}" target="_blank" class="button">🔍 Ver em tamanho real</a> '
                '<a href="{}" class="button">⬇️ Download</a>'
                '</div>',
                obj.get_file_url(),
                obj.get_file_url(),
                obj.get_file_url(),
                obj.get_download_url()
            )
        elif obj.is_video():
            return format_html(
                '<div style="margin: 20px 0;">'
                '<video controls style="max-width: 100%; max-height: 600px; '
                'border: 2px solid #ddd; border-radius: 8px;">'
                '<source src="{}" type="{}">'
                'Seu navegador não suporta vídeo.'
                '</video>'
                '</div>'
                '<div style="margin: 10px 0;">'
                '<a href="{}" target="_blank" class="button">🔍 Abrir em nova aba</a> '
                '<a href="{}" class="button">⬇️ Download</a>'
                '</div>',
                obj.get_file_url(),
                obj.mime_type or 'video/webm',
                obj.get_file_url(),
                obj.get_download_url()
            )
        else:
            return format_html(
                '<div style="margin: 20px 0;">'
                '<div style="padding: 40px; text-align: center; background: #f8f9fa; '
                'border: 2px dashed #ddd; border-radius: 8px;">'
                '<span style="font-size: 64px;">{}</span><br>'
                '<strong>{}</strong><br>'
                '<span style="color: #6c757d;">{}</span>'
                '</div>'
                '</div>'
                '<div style="margin: 10px 0;">'
                '<a href="{}" class="button">⬇️ Download</a>'
                '</div>',
                '📄' if obj.is_log() else '📊',
                obj.file_name,
                obj.format_file_size(),
                obj.get_download_url()
            )

    preview_large.short_description = _('Preview do Arquivo')

    # =============================================================================
    # OTIMIZAÇÕES DE QUERY
    # =============================================================================

    def get_queryset(self, request):
        """Otimiza queries."""
        qs = super().get_queryset(request)

        return qs.select_related(
            'test_result',
            'test_result__test_run',
            'test_result__test_run__project',
            'uploaded_by',
            'created_by',
            'updated_by'
        )

    # =============================================================================
    # PROTEÇÕES
    # =============================================================================

    def has_delete_permission(self, request, obj=None):
        """Apenas superuser pode deletar (preservar evidências)."""
        return request.user.is_superuser

    def save_model(self, request, obj, form, change):
        """Preenche uploaded_by automaticamente."""
        if not change and not obj.uploaded_by:
            obj.uploaded_by = request.user

        super().save_model(request, obj, form, change)

    # =============================================================================
    # AÇÕES EM LOTE
    # =============================================================================

    actions = ['download_selected']

    @admin.action(description=_('Download selecionados (ZIP)'))
    def download_selected(self, request, queryset):
        """Cria ZIP com artefatos selecionados."""
        import zipfile
        import io
        from django.http import HttpResponse

        # Criar ZIP em memória
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for artifact in queryset:
                if artifact.file:
                    # Adicionar arquivo ao ZIP
                    file_content = artifact.file.read()
                    zip_file.writestr(artifact.file_name, file_content)

        # Preparar resposta
        zip_buffer.seek(0)
        response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
        response['Content-Disposition'] = 'attachment; filename="artifacts.zip"'

        self.message_user(
            request,
            f'{queryset.count()} artefato(s) baixado(s).'
        )

        return response


# =============================================================================
# ADMIN INLINE (para usar em TestResultAdmin)
# =============================================================================

class ArtifactInline(admin.TabularInline):
    """Inline para visualizar artefatos dentro de TestResult."""

    model = Artifact
    extra = 0
    can_delete = False

    fields = (
        'artifact_type_display',
        'title',
        'file_size_display',
        'preview_small',
        'download_link',
    )

    readonly_fields = (
        'artifact_type_display',
        'title',
        'file_size_display',
        'preview_small',
        'download_link',
    )

    def artifact_type_display(self, obj):
        """Tipo com ícone."""
        icons = {
            'SCREENSHOT': '📸',
            'VIDEO': '🎥',
            'TRACE': '📊',
            'LOG': '📄',
        }
        return f"{icons.get(obj.artifact_type, '📎')} {obj.get_artifact_type_display()}"

    artifact_type_display.short_description = _('Tipo')

    def file_size_display(self, obj):
        """Tamanho formatado."""
        return obj.format_file_size()

    file_size_display.short_description = _('Tamanho')

    def preview_small(self, obj):
        """Preview muito pequeno."""
        if obj.is_image():
            return format_html(
                '<img src="{}" style="max-width: 40px; max-height: 30px;" />',
                obj.get_file_url()
            )
        return '-'

    preview_small.short_description = _('Preview')

    def download_link(self, obj):
        """Link de download."""
        return format_html(
            '<a href="{}" class="button" target="_blank">⬇️</a>',
            obj.get_download_url()
        )

    download_link.short_description = _('Download')

    def has_add_permission(self, request, obj=None):
        """Não permite adicionar via inline."""
        return False
