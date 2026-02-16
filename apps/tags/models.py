from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
import uuid

class Tag(models.Model):
    """
    Tag para categorização de casos de teste e execuções.

    Tags são globais (compartilhadas entre projetos) e permitem:
    - Organizar testes por funcionalidade, módulo, prioridade
    - Filtrar casos de teste e execuções
    - Agrupar testes em relatórios

    Exemplos:
    - "Login", "Crítico", "Smoke Test", "Módulo Processos"
    """

    # Validador para cor hexadecimal
    color_validator = RegexValidator(
        regex=r'^#[0-9A-Fa-f]{6}$',
        message=_('Cor deve estar no formato hexadecimal (#RRGGBB)')
    )

    class Meta:
        verbose_name = _("Tag")
        verbose_name_plural = _("Tags")
        ordering = ['name']

        # Índices
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['slug']),
        ]

    # =============================================================================
    # CAMPOS
    # =============================================================================

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    name = models.CharField(
        _("Nome"),
        max_length=50,
        unique=True,
        help_text=_("Nome único da tag (ex: 'Login', 'Crítico')")
    )

    color = models.CharField(
        _("Cor"),
        max_length=7,
        default='#007bff',
        validators=[color_validator],
        help_text=_("Cor em hexadecimal para badges (ex: #007bff)")
    )

    description = models.TextField(
        _("Descrição"),
        blank=True,
        help_text=_("Descrição opcional da tag")
    )

    created_at = models.DateTimeField(
        _("Criado em"),
        auto_now_add=True
    )

    # =============================================================================
    # MÉTODOS
    # =============================================================================

    def __str__(self):
        """Representação string da tag."""
        return self.name

    def save(self, *args, **kwargs):
        """Sobrescreve save para normalizar nome e validar unicidade."""
        # Normalizar nome (capitalize)
        if self.name:
            self.name = self.name.strip()

        super().save(*args, **kwargs)

    def clean(self):
        """Validações customizadas."""
        super().clean()

        # Validar nome único (case-insensitive)
        if self.name:
            existing = Tag.objects.filter(
                name__iexact=self.name
            ).exclude(pk=self.pk)

            if existing.exists():
                raise ValidationError({
                    'name': _("Já existe uma tag com este nome.")
                })

    # =============================================================================
    # MÉTODOS DE NEGÓCIO
    # =============================================================================

    def get_test_cases(self):
        """
        Retorna todos os casos de teste com esta tag.

        Returns:
            QuerySet de TestCase
        """
        return self.test_cases.filter(is_active=True)

    def get_test_runs(self):
        """
        Retorna todas as execuções com esta tag.

        Returns:
            QuerySet de TestRun
        """
        if not hasattr(self, 'test_runs'):
            return []
        return self.test_runs.all()

    def get_usage_count(self):
        """
        Retorna total de usos da tag (casos + execuções).

        Returns:
            dict: {'test_cases': int, 'test_runs': int, 'total': int}
        """
        test_cases_count = self.test_cases.filter(is_active=True).count()
        test_runs_count = 0

        if hasattr(self, 'test_runs'):
            test_runs_count = self.test_runs.count()

        return {
            'test_cases': test_cases_count,
            'test_runs': test_runs_count,
            'total': test_cases_count + test_runs_count
        }

    def is_in_use(self):
        """
        Verifica se a tag está sendo usada.

        Returns:
            bool: True se em uso
        """
        usage = self.get_usage_count()
        return usage['total'] > 0

    # =============================================================================
    # PROPERTIES
    # =============================================================================

    @property
    def test_cases_count(self):
        """Retorna quantidade de casos de teste."""
        return self.test_cases.filter(is_active=True).count()

    @property
    def test_runs_count(self):
        """Retorna quantidade de execuções."""
        if hasattr(self, 'test_runs'):
            return self.test_runs.count()
        return 0

    @property
    def color_rgb(self):
        """
        Converte cor hexadecimal para RGB.

        Returns:
            tuple: (r, g, b)
        """
        hex_color = self.color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
