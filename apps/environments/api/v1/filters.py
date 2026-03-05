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

    # Filtra por project__id (UUID) em vez de project (pkid inteiro).
    # O frontend sempre manda o UUID — sem isso, o filtro retorna vazio.
    project = django_filters.UUIDFilter(field_name="project__id")

    env_type = django_filters.CharFilter(
        lookup_expr="exact",
        label="Tipo de ambiente",
    )

    class Meta:
        model = Environment
        fields = {
            "is_active": ["exact"],
        }
