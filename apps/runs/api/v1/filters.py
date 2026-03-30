import django_filters
from apps.runs.models import TestRun


class TestRunFilter(django_filters.FilterSet):
    """
    Filtros disponíveis para o endpoint de execuções.

    Exemplos:
        GET /api/v1/runs/?project=<uuid>
        GET /api/v1/runs/?environment=<uuid>
        GET /api/v1/runs/?status=COMPLETED
        GET /api/v1/runs/?status__in=COMPLETED,FAILED
        GET /api/v1/runs/?branch=main
        GET /api/v1/runs/?started_at_after=2026-01-01

    ATENÇÃO: BaseModel usa pkid (BigAutoField) como PK e id (UUIDField) como
    identificador externo. Os filtros project e environment precisam apontar
    para project__id e environment__id (UUID), não para o pkid (inteiro).
    """

    # Filtros UUID explícitos — evitam o ModelChoiceFilter padrão que buscaria
    # pelo pkid (inteiro) em vez do id (UUID)
    project = django_filters.UUIDFilter(
        field_name="project__id",
        lookup_expr="exact",
        label="Projeto (UUID)",
    )
    environment = django_filters.UUIDFilter(
        field_name="environment__id",
        lookup_expr="exact",
        label="Ambiente (UUID)",
    )

    branch = django_filters.CharFilter(
        lookup_expr="icontains",
        label="Branch contém",
    )
    started_at_after = django_filters.DateTimeFilter(
        field_name="started_at",
        lookup_expr="gte",
        label="Iniciado após",
    )
    started_at_before = django_filters.DateTimeFilter(
        field_name="started_at",
        lookup_expr="lte",
        label="Iniciado antes de",
    )
    status__in = django_filters.BaseInFilter(
        field_name="status",
        lookup_expr="in",
        label="Status (múltiplos)",
    )

    class Meta:
        model = TestRun
        fields = {
            "status":       ["exact"],
            "trigger_type": ["exact"],
            "is_active":    ["exact"],
        }
