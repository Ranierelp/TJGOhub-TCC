import django_filters
from apps.projects.models import Project


class ProjectFilter(django_filters.FilterSet):
    """
    Filtros disponíveis para o endpoint de projetos.

    Exemplos de uso:
        GET /api/v1/projects/?is_active=true
        GET /api/v1/projects/?name=TJGO
        GET /api/v1/projects/?created_at_after=2026-01-01&created_at_before=2026-12-31
        GET /api/v1/projects/?created_by=<uuid>
    """

    # Busca parcial e insensível a maiúsculas no nome
    name = django_filters.CharFilter(
        lookup_expr="icontains",
        label="Nome contém",
    )

    # Intervalo de datas de criação
    created_at_after = django_filters.DateTimeFilter(
        field_name="created_at",
        lookup_expr="gte",
        label="Criado após",
    )
    created_at_before = django_filters.DateTimeFilter(
        field_name="created_at",
        lookup_expr="lte",
        label="Criado antes de",
    )

    # FK precisa apontar pra __id (UUID). Sem isso, o ModelChoiceFilter
    # auto-gerado tentaria casar pelo pkid (int) e o front receberia 400.
    created_by = django_filters.UUIDFilter(
        field_name="created_by__id",
        label="Criado por (UUID)",
    )

    class Meta:
        model = Project
        fields = {
            "is_active": ["exact"],
            "slug": ["exact"],
        }
