from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.commons.models import BaseModel


# Valida formato de cor hexadecimal (#RRGGBB)
hex_color_validator = RegexValidator(
    regex=r'^#[0-9A-Fa-f]{6}$',
    message=_('Cor deve estar no formato hexadecimal (#RRGGBB)')
)

# Colunas padrão criadas automaticamente no primeiro uso do board
DEFAULT_COLUMNS = [
    {'name': 'Backlog', 'color': '#6b7280', 'order': 0},
    {'name': 'To Do', 'color': '#3b82f6', 'order': 1},
    {'name': 'In Progress', 'color': '#f59e0b', 'order': 2},
    {'name': 'Done', 'color': '#10b981', 'order': 3},
]


class KanbanColumn(BaseModel):
    """
    Coluna do board Kanban.

    Representa uma etapa do fluxo de trabalho (ex: Backlog, In Progress).
    Colunas com project=null são globais (valem para todos os projetos).
    """

    class Meta(BaseModel.Meta):
        verbose_name = _("Coluna Kanban")
        verbose_name_plural = _("Colunas Kanban")
        ordering = ['order']

    name = models.CharField(
        _("Nome"),
        max_length=100,
        help_text=_("Nome da coluna (ex: 'Backlog', 'In Progress')")
    )

    color = models.CharField(
        _("Cor"),
        max_length=7,
        default='#6366f1',
        validators=[hex_color_validator],
        help_text=_("Cor da coluna em hexadecimal (ex: #6366f1)")
    )

    order = models.PositiveIntegerField(
        _("Ordem"),
        default=0,
        help_text=_("Posição horizontal no board (0 = primeira coluna)")
    )

    # null = coluna global, visível para todos os projetos
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='kanban_columns',
        verbose_name=_("Projeto"),
        null=True,
        blank=True,
        help_text=_("Projeto ao qual pertence. Nulo = coluna global.")
    )

    def __str__(self):
        scope = self.project.name if self.project else 'Global'
        return f"{self.name} ({scope})"
