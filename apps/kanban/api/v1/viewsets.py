from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, extend_schema_view

from apps.commons.api.v1.viewsets import BaseModelApiViewSet
from apps.kanban.models import KanbanColumn, DEFAULT_COLUMNS
from .serializers import (
    KanbanColumnSerializer,
    KanbanColumnReorderSerializer,
    KanbanBoardColumnSerializer,
)


@extend_schema_view(
    list=extend_schema(summary="Lista colunas do Kanban", tags=["Kanban"]),
    retrieve=extend_schema(summary="Detalha uma coluna", tags=["Kanban"]),
    create=extend_schema(summary="Cria uma nova coluna", tags=["Kanban"]),
    update=extend_schema(summary="Atualiza uma coluna (PUT)", tags=["Kanban"]),
    partial_update=extend_schema(summary="Atualiza parcialmente (PATCH)", tags=["Kanban"]),
    destroy=extend_schema(summary="Arquiva uma coluna (soft delete)", tags=["Kanban"]),
)
class KanbanColumnViewSet(BaseModelApiViewSet):
    """
    ViewSet para gerenciamento de colunas do Kanban.

    ## Operações padrão
    - GET    /kanban/columns/          → list (cria as 4 colunas padrão se não existirem)
    - POST   /kanban/columns/          → create
    - GET    /kanban/columns/{id}/     → retrieve
    - PUT    /kanban/columns/{id}/     → update
    - PATCH  /kanban/columns/{id}/     → partial_update
    - DELETE /kanban/columns/{id}/     → destroy (soft delete)

    ## Actions customizadas
    - POST /kanban/columns/reorder/    → reordena múltiplas colunas em uma só chamada
    """

    model = KanbanColumn
    serializer_class = KanbanColumnSerializer
    ordering = ['order']

    def get_queryset(self):
        return KanbanColumn.objects.all().select_related('project').order_by('order')

    def list(self, request, *args, **kwargs):
        """
        Lista as colunas.

        Se não existir nenhuma coluna global (project=null), cria automaticamente
        as 4 colunas padrão: Backlog, To Do, In Progress, Done.
        """
        # Seed automático: só roda uma vez, quando não há colunas globais
        if not KanbanColumn.objects.filter(project__isnull=True).exists():
            self._seed_default_columns(request.user)

        return super().list(request, *args, **kwargs)

    def _seed_default_columns(self, user):
        """Cria as 4 colunas padrão globais."""
        for col in DEFAULT_COLUMNS:
            KanbanColumn.objects.create(
                name=col['name'],
                color=col['color'],
                order=col['order'],
                project=None,
                created_by=user,
            )

    def destroy(self, request, *args, **kwargs):
        """
        Remove uma coluna do Kanban.

        Se a coluna tiver casos, é obrigatório informar `target_column_id`
        (query param ou body) para onde os casos serão movidos antes da remoção.
        Se a coluna estiver vazia, a remoção ocorre diretamente.
        """
        column = self.get_object()

        target_id = (
            request.query_params.get("target_column_id")
            or request.data.get("target_column_id")
        )

        from apps.cases.models import TestCase
        cases_count = TestCase.objects.filter(kanban_column=column).count()

        if cases_count > 0 and not target_id:
            return Response(
                {
                    "error": "Esta coluna possui casos. Informe 'target_column_id' para movê-los.",
                    "cases_count": cases_count,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if target_id:
            try:
                target = KanbanColumn.objects.get(id=target_id)
            except KanbanColumn.DoesNotExist:
                return Response(
                    {"error": "Coluna de destino não encontrada."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            TestCase.objects.filter(kanban_column=column).update(kanban_column=target)

        self.perform_destroy(column)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        summary="Reordena colunas em lote",
        tags=["Kanban"],
        request=KanbanColumnReorderSerializer,
        responses={200: KanbanColumnSerializer(many=True)},
    )
    @action(detail=False, methods=['post'], url_path='reorder',
            permission_classes=[IsAuthenticated])
    def reorder(self, request):
        """
        Atualiza a ordem de múltiplas colunas em uma única requisição.

        Body esperado:
            { "columns": [{"id": "<uuid>", "order": 0}, {"id": "<uuid>", "order": 1}] }
        """
        serializer = KanbanColumnReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        items = serializer.validated_data['columns']

        # Atualiza cada coluna com sua nova ordem
        updated_ids = []
        for item in items:
            updated = KanbanColumn.objects.filter(id=item['id']).update(order=item['order'])
            if updated:
                updated_ids.append(item['id'])

        # Retorna as colunas já na nova ordem
        columns = KanbanColumn.objects.filter(id__in=updated_ids).order_by('order')
        return Response(
            KanbanColumnSerializer(columns, many=True).data,
            status=status.HTTP_200_OK,
        )


class KanbanBoardView(APIView):
    """
    GET /api/v1/kanban/board/

    Retorna todas as colunas ativas com seus casos aninhados,
    ordenados por board_position. Aceita ?project=<uuid> para
    filtrar os casos por projeto.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Board completo do Kanban",
        description=(
            "Retorna colunas com casos aninhados ordenados por posição. "
            "Use ?project=<uuid> para filtrar casos de um projeto específico."
        ),
        tags=["Kanban"],
        responses={200: KanbanBoardColumnSerializer(many=True)},
    )
    def get(self, request):
        # Seed automático: cria as colunas padrão se ainda não existirem
        if not KanbanColumn.objects.filter(project__isnull=True).exists():
            for col in DEFAULT_COLUMNS:
                KanbanColumn.objects.create(
                    name=col['name'],
                    color=col['color'],
                    order=col['order'],
                    project=None,
                    created_by=request.user,
                )

        # Migração automática: casos sem coluna vão para o Backlog (coluna de menor order)
        from apps.cases.models import TestCase
        backlog = KanbanColumn.objects.filter(project__isnull=True).order_by('order').first()
        if backlog:
            TestCase.objects.filter(kanban_column__isnull=True).update(kanban_column=backlog)

        project_id = request.query_params.get("project")

        # Quando um projeto está selecionado, mostra globais + específicas dele.
        # Quando "Todos" (sem project_id), mostra absolutamente todas.
        columns_qs = KanbanColumn.objects.all().select_related("project")
        if project_id:
            from django.db.models import Q
            # Usar project__id (UUID) — project_id no FK aponta pro pkid (int)
            columns_qs = columns_qs.filter(Q(project__isnull=True) | Q(project__id=project_id))

        columns = columns_qs.order_by("order")
        serializer = KanbanBoardColumnSerializer(
            columns,
            many=True,
            context={"request": request, "project_id": project_id},
        )
        return Response(serializer.data)
