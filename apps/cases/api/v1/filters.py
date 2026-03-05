import django_filters
from apps.cases.models import TestCase


class TestCaseFilter(django_filters.FilterSet):
    """
    Filtros disponíveis para o endpoint de casos de teste.

    Exemplos:
        GET /api/v1/test-cases/?project=<uuid>
        GET /api/v1/test-cases/?status=ACTIVE
        GET /api/v1/test-cases/?status__in=ACTIVE,DRAFT
        GET /api/v1/test-cases/?module=Autenticação
        GET /api/v1/test-cases/?tags=<uuid>
        GET /api/v1/test-cases/?title=login
        GET /api/v1/test-cases/?has_playwright_id=true
    """

    title = django_filters.CharFilter(
        lookup_expr="icontains",
        label="Título contém",
    )
    module = django_filters.CharFilter(
        lookup_expr="icontains",
        label="Módulo contém",
    )
    # Permite filtrar por múltiplos status: ?status__in=ACTIVE,DRAFT
    status__in = django_filters.BaseInFilter(
        field_name="status",
        lookup_expr="in",
        label="Status (múltiplos)",
    )
    # Filtra casos que têm ou não playwright_id preenchido
    has_playwright_id = django_filters.BooleanFilter(
        field_name="playwright_id",
        lookup_expr="isnull",
        exclude=True,
        label="Tem Playwright ID",
    )
    # Filtra por tag (UUID da tag)
    tags = django_filters.UUIDFilter(
        field_name="tags__id",
        label="Tag (UUID)",
    )
    # Filtra pelo UUID público do projeto — substitui o ModelChoiceFilter
    # auto-gerado que tentaria converter o UUID para pkid (inteiro)
    project = django_filters.UUIDFilter(
        field_name="project__id",
        label="Projeto (UUID)",
    )

    class Meta:
        model = TestCase
        fields = {
            "status":        ["exact"],
            "is_active":     ["exact"],
            "playwright_id": ["exact"],
        }
