# apps/projects/api/v1/viewsets.py

from django.db.models import Count
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view

from apps.commons.api.v1.viewsets import BaseModelApiViewSet
from apps.projects.models import Project
from .serializers import ProjectSerializer, ProjectListSerializer
from .filters import ProjectFilter


@extend_schema_view(
    list=extend_schema(
        summary="Lista projetos ativos",
        tags=["Projetos"],
    ),
    retrieve=extend_schema(
        summary="Detalha um projeto",
        tags=["Projetos"],
    ),
    create=extend_schema(
        summary="Cria um novo projeto",
        tags=["Projetos"],
    ),
    update=extend_schema(
        summary="Atualiza um projeto (PUT)",
        tags=["Projetos"],
    ),
    partial_update=extend_schema(
        summary="Atualiza um projeto parcialmente (PATCH)",
        tags=["Projetos"],
    ),
    destroy=extend_schema(
        summary="Arquiva um projeto (soft delete)",
        tags=["Projetos"],
    ),
)
class ProjectViewSet(BaseModelApiViewSet):
    """
    ViewSet completo para gerenciamento de projetos.

    ## Operações padrão (herdadas de BaseModelApiViewSet)
    - `GET    /projects/`          → list
    - `POST   /projects/`          → create
    - `GET    /projects/{id}/`     → retrieve
    - `PUT    /projects/{id}/`     → update
    - `PATCH  /projects/{id}/`     → partial_update
    - `DELETE /projects/{id}/`     → destroy (soft delete via BaseAdmin)

    ## Actions customizadas
    - `GET  /projects/mine/`           → Projetos do usuário autenticado
    - `POST /projects/{id}/archive/`   → Arquiva projeto
    - `POST /projects/{id}/activate/`  → Reativa projeto arquivado
    """

    model = Project
    filterset_class = ProjectFilter
    search_fields = ["name", "slug", "description"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """
        Queryset base com select_related e annotations de contadores.

        As annotations (_environments_count, etc.) são consumidas pelos
        SerializerMethodFields sem gerar queries adicionais.
        """
        return (
            Project.all_objects.all()
            .select_related("created_by", "updated_by")
            .annotate(
                _environments_count=Count("environments", distinct=True),
                _test_cases_count=Count("test_cases", distinct=True),
                _test_runs_count=Count("test_runs", distinct=True),
            )
        )

    def get_serializer_class(self):
        """Usa serializer compacto na listagem, completo nos demais actions."""
        if self.action == "list":
            return ProjectListSerializer
        return ProjectSerializer

    # =========================================================================
    # ACTIONS CUSTOMIZADAS
    # =========================================================================

    @extend_schema(
        summary="Meus projetos",
        description="Retorna apenas os projetos criados pelo usuário autenticado.",
        tags=["Projetos"],
        responses={200: ProjectListSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="mine")
    def mine(self, request):
        """Projetos criados pelo usuário autenticado."""
        qs = self.get_queryset().filter(created_by=request.user)
        serializer = ProjectListSerializer(
            qs, many=True, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Arquiva projeto",
        description=(
            "Realiza soft delete no projeto. O registro não é removido do banco — "
            "apenas marcado como inativo. Ambientes e casos de teste preservados."
        ),
        tags=["Projetos"],
        responses={200: {"type": "object", "properties": {"detail": {"type": "string"}}}},
    )
    @action(detail=True, methods=["post"], url_path="archive")
    def archive(self, request, id=None):
        """Arquiva (soft delete) o projeto."""
        project = self.get_object()

        if not project.is_active:
            return Response(
                {"detail": "O projeto já está arquivado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        project.delete(deleted_by=request.user, deleted_at=timezone.now())
        return Response(
            {"detail": "Projeto arquivado com sucesso."},
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Reativa projeto",
        description="Reativa um projeto previamente arquivado.",
        tags=["Projetos"],
        responses={200: ProjectSerializer},
    )
    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, id=None):
        """Reativa um projeto arquivado. Busca em all_objects (inclui inativos)."""
        # all_objects porque o projeto está inativo e o manager padrão o excluiria
        project = Project.all_objects.filter(id=id).first()

        if not project:
            return Response(
                {"detail": "Projeto não encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if project.is_active:
            return Response(
                {"detail": "O projeto já está ativo."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        project.is_active = True
        project.deleted_at = None
        project.deleted_by = None
        project.updated_by = request.user
        project.save(update_fields=["is_active", "deleted_at", "deleted_by", "updated_by", "updated_at"])

        serializer = ProjectSerializer(project, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)
