import django_filters
from apps.results.models import TestResult


class TestResultFilter(django_filters.FilterSet):
    """
    Filtros disponíveis para o endpoint de resultados.

    Exemplos:
        GET /api/v1/results/?test_run=<uuid>
        GET /api/v1/results/?status=FAILED
        GET /api/v1/results/?test_case=<uuid>
        GET /api/v1/results/?has_error=true
        GET /api/v1/results/?executed_at_after=2026-01-01
    """

    executed_at_after = django_filters.DateTimeFilter(
        field_name="executed_at",
        lookup_expr="gte",
        label="Executado após",
    )
    executed_at_before = django_filters.DateTimeFilter(
        field_name="executed_at",
        lookup_expr="lte",
        label="Executado antes de",
    )
    # Filtra resultados que têm ou não erro
    has_error = django_filters.BooleanFilter(
        field_name="error_message",
        lookup_expr="isnull",
        exclude=True,
        label="Tem erro",
    )
    status__in = django_filters.BaseInFilter(
        field_name="status",
        lookup_expr="in",
        label="Status (múltiplos)",
    )

    class Meta:
        model = TestResult
        fields = {
            "test_run":  ["exact"],
            "test_case": ["exact"],
            "status":    ["exact"],
            "retry_number": ["exact", "gte"],
        }
