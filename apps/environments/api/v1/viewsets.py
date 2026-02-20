from django.db.models import Count
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view

from apps.commons.api.v1.viewsets import BaseModelApiViewSet
from apps.environments.models import Environment
from .serializers import EnvironmentSerializer, EnvironmentListSerializer
from .filters import EnvironmentFilter


@extend_schema_view(
    list=extend_schema(
        summary="Lista ambientes ativos",
        tags=["Ambientes"],
    ),
    retrieve=extend_schema(
        summary="Detalha um ambiente",
        tags=["Ambientes"],
    ),
    create=extend_schema(
        summary="Cria um novo ambiente",
        tags=["Ambientes"],
    ),
    update=extend_schema(
        summary="Atualiza um ambiente (PUT)",
        tags=["Ambientes"],
    ),
    partial_update=extend_schema(
        summary="Atualiza um ambiente parcialmente (PATCH)",
        tags=["Ambientes"],
    ),
    destroy=extend_schema(
        summary="Arquiva um ambiente (soft delete)",
        tags=["Ambientes"],
    ),
)
class EnvironmentViewSet(BaseModelApiViewSet):
    """
    ViewSet completo para gerenciamento de ambientes de execução.

    ## Operações padrão
    - GET    /environments/            → list
    - POST   /environments/            → create
    - GET    /environments/{id}/       → retrieve
    - PUT    /environments/{id}/       → update
    - PATCH  /environments/{id}/       → partial_update
    - DELETE /environments/{id}/       → destroy (soft delete)

    ## Actions customizadas
    - GET  /environments/by-project/{project_id}/  → ambientes de um projeto
    - POST /environments/{id}/archive/             → arquiva ambiente
    - POST /environments/{id}/activate/            → reativa ambiente
    """

    model = Environment
    filterset_class = EnvironmentFilter
    search_fields = ["base_url", "project__name"]
    ordering_fields = ["env_type", "created_at"]
    ordering = ["project", "env_type"]

    def get_queryset(self):
        return (
            Environment.objects.all()
            .select_related("project", "created_by", "updated_by")
            .annotate(
                _test_runs_count=Count("test_runs", distinct=True),
            )
        )

    def get_serializer_class(self):
        if self.action == "list":
            return EnvironmentListSerializer
        return EnvironmentSerializer

    # =========================================================================
    # ACTIONS CUSTOMIZADAS
    # =========================================================================

    @extend_schema(
        summary="Ambientes de um projeto",
        description="Retorna todos os ambientes ativos de um projeto específico.",
        tags=["Ambientes"],
        responses={200: EnvironmentListSerializer(many=True)},
    )
    @action(
        detail=False,
        methods=["get"],
        url_path=r"by-project/(?P<project_id>[^/.]+)",
    )
    def by_project(self, request, project_id=None):
        """
        Atalho para listar ambientes de um projeto sem precisar usar o filtro.
        GET /api/v1/environments/by-project/<project_uuid>/
        """
        qs = self.get_queryset().filter(project__id=project_id)
        serializer = EnvironmentListSerializer(
            qs, many=True, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Arquiva ambiente",
        description="Soft delete no ambiente. O histórico de execuções é preservado.",
        tags=["Ambientes"],
        responses={200: {"type": "object", "properties": {"detail": {"type": "string"}}}},
    )
    @action(detail=True, methods=["post"], url_path="archive")
    def archive(self, request, id=None):
        """Arquiva (soft delete) o ambiente."""
        environment = self.get_object()

        if not environment.is_active:
            return Response(
                {"detail": "O ambiente já está arquivado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        environment.delete(deleted_by=request.user, deleted_at=timezone.now())
        return Response(
            {"detail": "Ambiente arquivado com sucesso."},
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Reativa ambiente",
        description="Reativa um ambiente previamente arquivado.",
        tags=["Ambientes"],
        responses={200: EnvironmentSerializer},
    )
    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, id=None):
        """Reativa um ambiente arquivado. Busca em all_objects (inclui inativos)."""
        environment = Environment.all_objects.filter(id=id).first()

        if not environment:
            return Response(
                {"detail": "Ambiente não encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if environment.is_active:
            return Response(
                {"detail": "O ambiente já está ativo."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        environment.is_active = True
        environment.deleted_at = None
        environment.deleted_by = None
        environment.updated_by = request.user
        environment.save(
            update_fields=[
                "is_active", "deleted_at", "deleted_by", "updated_by", "updated_at"
            ]
        )

        serializer = EnvironmentSerializer(
            environment, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)
