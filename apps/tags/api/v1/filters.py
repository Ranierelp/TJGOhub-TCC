import django_filters
from apps.tags.models import Tag


class TagFilter(django_filters.FilterSet):
    """
    Filtros disponíveis para o endpoint de tags.

    Exemplos:
        GET /api/v1/tags/?name=login
        GET /api/v1/tags/?name=crítico
    """

    name = django_filters.CharFilter(
        lookup_expr="icontains",
        label="Nome contém",
    )

    class Meta:
        model = Tag
        fields = ["name"]
