import os
from django.db import models
from django.core.validators import FileExtensionValidator
from django.utils.translation import gettext_lazy as _

from apps.commons.models import BaseModel


def artifact_upload_path(instance, filename):
    """
    Gera caminho de upload do artefato.

    Formato: artifacts/{project}/{run_id}/{result_id}/{filename}
    """
    result = instance.test_result
    run = result.test_run
    project = run.project

    return f"artifacts/{project.slug}/{run.run_id}/{result.result_id}/{filename}"


class Artifact(BaseModel):
    """
    Artefato de Teste (Screenshot, Vídeo, Trace, Log).

    Evidências geradas durante execução de testes.
    Armazenadas em storage privado (S3 ou filesystem).
    """

    # Tipos de artefato
    TYPE_SCREENSHOT = 'SCREENSHOT'
    TYPE_VIDEO = 'VIDEO'
    TYPE_TRACE = 'TRACE'
    TYPE_LOG = 'LOG'

    TYPE_CHOICES = [
        (TYPE_SCREENSHOT, _('Screenshot')),
        (TYPE_VIDEO, _('Vídeo')),
        (TYPE_TRACE, _('Trace do Playwright')),
        (TYPE_LOG, _('Log')),
    ]

    class Meta(BaseModel.Meta):
        verbose_name = _("Artefato de Teste")
        verbose_name_plural = _("Artefatos de Teste")
        ordering = ['-created_at']

        # Índices
        indexes = [
            models.Index(fields=['test_result', 'artifact_type']),
            models.Index(fields=['artifact_type', '-created_at']),
        ]

    # =============================================================================
    # CAMPOS - IDENTIFICAÇÃO
    # =============================================================================

    test_result = models.ForeignKey(
        'results.TestResult',
        on_delete=models.CASCADE,  # Se resultado deletado, artefatos também
        related_name='artifacts',
        verbose_name=_("Resultado do Teste")
    )

    artifact_type = models.CharField(
        _("Tipo de Artefato"),
        max_length=20,
        choices=TYPE_CHOICES
    )

    # =============================================================================
    # CAMPOS - ARQUIVO
    # =============================================================================

    file = models.FileField(
        _("Arquivo"),
        upload_to=artifact_upload_path,
        max_length=500
    )

    file_name = models.CharField(
        _("Nome do Arquivo"),
        max_length=255,
        help_text=_("Nome original do arquivo")
    )

    file_size = models.BigIntegerField(
        _("Tamanho do Arquivo"),
        help_text=_("Tamanho em bytes")
    )

    mime_type = models.CharField(
        _("MIME Type"),
        max_length=100,
        blank=True,
        help_text=_("Tipo de conteúdo (image/png, video/webm, etc)")
    )

    # =============================================================================
    # CAMPOS - METADADOS
    # =============================================================================

    title = models.CharField(
        _("Título"),
        max_length=255,
        help_text=_("Título descritivo do artefato")
    )

    description = models.TextField(
        _("Descrição"),
        blank=True,
        help_text=_("Descrição opcional")
    )

    thumbnail_path = models.CharField(
        _("Caminho do Thumbnail"),
        max_length=500,
        blank=True,
        help_text=_("Preview do artefato (se aplicável)")
    )

    # =============================================================================
    # CAMPOS - RASTREABILIDADE
    # =============================================================================

    uploaded_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='artifacts_uploaded',
        verbose_name=_("Enviado por")
    )

    # =============================================================================
    # MÉTODOS
    # =============================================================================

    def __str__(self):
        return f"{self.title} ({self.get_artifact_type_display()})"

    def save(self, *args, **kwargs):
        """Override do save para preencher metadados."""
        if self.file and not self.file_name:
            self.file_name = os.path.basename(self.file.name)

        if self.file and not self.file_size:
            self.file_size = self.file.size

        if not self.title:
            self.title = self.file_name

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Override delete para remover arquivo do storage."""
        # Se hard delete, remover arquivo
        if kwargs.get('hard_delete', False):
            if self.file:
                self.file.delete(save=False)
            if self.thumbnail_path:
                # Remover thumbnail também
                storage = self.file.storage
                storage.delete(self.thumbnail_path)

        super().delete(*args, **kwargs)

    # =============================================================================
    # MÉTODOS DE NEGÓCIO
    # =============================================================================

    def is_image(self):
        """Verifica se é imagem."""
        return self.artifact_type == self.TYPE_SCREENSHOT

    def is_video(self):
        """Verifica se é vídeo."""
        return self.artifact_type == self.TYPE_VIDEO

    def is_trace(self):
        """Verifica se é trace."""
        return self.artifact_type == self.TYPE_TRACE

    def is_log(self):
        """Verifica se é log."""
        return self.artifact_type == self.TYPE_LOG

    def get_file_url(self):
        """
        Retorna URL do arquivo.

        Returns:
            str: URL assinada (se S3) ou caminho local
        """
        if self.file:
            return self.file.url
        return None

    def get_thumbnail_url(self):
        """
        Retorna URL do thumbnail.

        Returns:
            str: URL do preview ou None
        """
        if self.thumbnail_path:
            return self.file.storage.url(self.thumbnail_path)
        return None

    def get_download_url(self):
        """
        Retorna URL para download com nome original.

        Returns:
            str: URL para download
        """
        # Implementar em view/API para forçar download
        return f"/api/v1/artifacts/{self.id}/download/"

    def format_file_size(self):
        """
        Formata tamanho do arquivo.

        Returns:
            str: "1.5 MB", "350 KB", etc
        """
        size = self.file_size

        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.1f} GB"

    # =============================================================================
    # PROPERTIES
    # =============================================================================

    @property
    def file_extension(self):
        """Retorna extensão do arquivo."""
        return os.path.splitext(self.file_name)[1].lower()

    @property
    def is_viewable(self):
        """Verifica se pode ser visualizado no navegador."""
        viewable_types = [self.TYPE_SCREENSHOT, self.TYPE_VIDEO]
        return self.artifact_type in viewable_types
