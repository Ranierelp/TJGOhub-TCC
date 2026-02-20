import django_filters
from apps.environments.models import Environment


class EnvironmentFilter(django_filters.FilterSet):
    """
    Filtros disponíveis para o endpoint de ambientes.

    Exemplos de uso:
        GET /api/v1/environments/?project=<uuid>
        GET /api/v1/environments/?env_type=production
        GET /api/v1/environments/?env_type=development&is_active=true
    """

    env_type = django_filters.CharFilter(
        lookup_expr="exact",
        label="Tipo de ambiente",
    )

    class Meta:
        model = Environment
        fields = {
            "project":  ["exact"],
            "is_active": ["exact"],
        }
