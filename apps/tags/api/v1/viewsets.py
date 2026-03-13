from django.db.models import Count
from rest_framework import viewsets, mixins, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view

from apps.tags.models import Tag
from .serializers import TagSerializer
from .filters import TagFilter


@extend_schema_view(
    list=extend_schema(
        summary="Lista todas as tags",
        tags=["Tags"],
    ),
    retrieve=extend_schema(
        summary="Detalha uma tag",
        tags=["Tags"],
    ),
    create=extend_schema(
        summary="Cria uma nova tag",
        tags=["Tags"],
    ),
    update=extend_schema(
        summary="Atualiza uma tag (PUT)",
        tags=["Tags"],
    ),
    partial_update=extend_schema(
        summary="Atualiza uma tag parcialmente (PATCH)",
        tags=["Tags"],
    ),
    destroy=extend_schema(
        summary="Remove uma tag permanentemente",
        tags=["Tags"],
    ),
)
class TagViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    ViewSet para gerenciamento de tags.

    Tag não herda de BaseModel, por isso não usa BaseModelApiViewSet:
    - Não tem soft delete → destroy faz remoção física (com proteção se em uso)
    - Não tem rastreabilidade → sem created_by, updated_by
    - lookup_field é 'id' (UUID), consistente com o restante da API

    ## Operações
    - GET    /tags/        → list
    - POST   /tags/        → create
    - GET    /tags/{id}/   → retrieve
    - PUT    /tags/{id}/   → update
    - PATCH  /tags/{id}/   → partial_update
    - DELETE /tags/{id}/   → destroy (bloqueado se tag estiver em uso)
    """

    serializer_class = TagSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = TagFilter
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]
    lookup_field = "id"

    def get_queryset(self):
        return (
            Tag.objects.all()
            .annotate(_usage_count=Count("test_cases", distinct=True))
            .order_by("name")
        )

    def destroy(self, request, *args, **kwargs):
        """
        Remove a tag permanentemente.
        Bloqueado se a tag estiver associada a casos de teste ou execuções.
        """
        tag = self.get_object()

        if tag.test_cases.exists():
            return Response(
                {
                    "detail": (
                        f"Não é possível remover a tag '{tag.name}' pois ela está "
                        f"associada a {tag.test_cases.count()} caso(s) de teste. "
                        "Remova as associações antes de deletar a tag."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        tag.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
