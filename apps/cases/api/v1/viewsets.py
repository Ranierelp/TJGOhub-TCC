from django.db.models import Count
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view

from apps.commons.api.v1.viewsets import BaseModelApiViewSet
from apps.cases.models import TestCase
from .serializers import (
    TestCaseSerializer,
    TestCaseListSerializer,
    TestCaseAttachmentSerializer,
    TestCaseAttachmentWriteSerializer,
)
from .filters import TestCaseFilter


@extend_schema_view(
    list=extend_schema(summary="Lista casos de teste", tags=["Casos de Teste"]),
    retrieve=extend_schema(summary="Detalha um caso de teste", tags=["Casos de Teste"]),
    create=extend_schema(summary="Cria um caso de teste", tags=["Casos de Teste"]),
    update=extend_schema(summary="Atualiza um caso de teste (PUT)", tags=["Casos de Teste"]),
    partial_update=extend_schema(summary="Atualiza parcialmente (PATCH)", tags=["Casos de Teste"]),
    destroy=extend_schema(summary="Arquiva um caso de teste (soft delete)", tags=["Casos de Teste"]),
)
class TestCaseViewSet(BaseModelApiViewSet):
    """
    ViewSet completo para gerenciamento de casos de teste.

    ## Operações padrão
    - GET    /test-cases/           → list
    - POST   /test-cases/           → create
    - GET    /test-cases/{id}/      → retrieve
    - PUT    /test-cases/{id}/      → update
    - PATCH  /test-cases/{id}/      → partial_update
    - DELETE /test-cases/{id}/      → destroy (soft delete)

    ## Actions customizadas
    - POST /test-cases/{id}/activate/          → reativa caso arquivado
    - POST /test-cases/{id}/change-status/     → muda status (DRAFT/ACTIVE/DEPRECATED)
    - GET  /test-cases/by-project/{uuid}/      → casos de um projeto específico
    """

    model = TestCase
    filterset_class = TestCaseFilter
    search_fields = ["case_id", "title", "module", "playwright_id", "objective"]
    ordering_fields = ["case_id", "title", "status", "module", "created_at"]
    ordering = ["project", "case_id"]

    def get_queryset(self):
        return (
            TestCase.objects.all()
            .select_related("project", "created_by", "updated_by", "last_modified_by")
            .prefetch_related("tags", "attachments")
            .annotate(_attachments_count=Count("attachments", distinct=True))
            .order_by("project", "case_id")
        )

    def get_serializer_class(self):
        if self.action == "list":
            return TestCaseListSerializer
        return TestCaseSerializer

    def perform_update(self, serializer):
        """
        Sobrescreve para preencher last_modified_by além do updated_by padrão.
        last_modified_by é específico de TestCase — rastreia quem editou o conteúdo.
        """
        serializer.validated_data["last_modified_by"] = self.request.user
        super().perform_update(serializer)

    # =========================================================================
    # ACTIONS CUSTOMIZADAS
    # =========================================================================

    @extend_schema(
        summary="Casos de teste de um projeto",
        tags=["Casos de Teste"],
        responses={200: TestCaseListSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path=r"by-project/(?P<project_id>[^/.]+)")
    def by_project(self, request, project_id=None):
        """Atalho para listar casos de teste de um projeto sem usar filtro."""
        qs = self.get_queryset().filter(project__id=project_id)
        serializer = TestCaseListSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)

    @extend_schema(
        summary="Muda status do caso de teste",
        description="Altera o status entre DRAFT, ACTIVE e DEPRECATED.",
        tags=["Casos de Teste"],
        request={"application/json": {"type": "object", "properties": {
            "status": {"type": "string", "enum": ["DRAFT", "ACTIVE", "DEPRECATED"]}
        }}},
        responses={200: TestCaseSerializer},
    )
    @action(detail=True, methods=["post"], url_path="change-status")
    def change_status(self, request, id=None):
        """Altera o status do caso de teste."""
        test_case = self.get_object()
        new_status = request.data.get("status")

        valid = [TestCase.STATUS_DRAFT, TestCase.STATUS_ACTIVE, TestCase.STATUS_DEPRECATED]
        if new_status not in valid:
            return Response(
                {"detail": f"Status inválido. Valores aceitos: {', '.join(valid)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        test_case.status = new_status
        test_case.last_modified_by = request.user
        test_case.updated_by = request.user
        test_case.save(update_fields=["status", "last_modified_by", "updated_by", "updated_at"])

        serializer = TestCaseSerializer(test_case, context={"request": request})
        return Response(serializer.data)

    @extend_schema(
        summary="Reativa caso de teste arquivado",
        tags=["Casos de Teste"],
        responses={200: TestCaseSerializer},
    )
    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, id=None):
        """Reativa um caso de teste arquivado. Busca em all_objects."""
        test_case = TestCase.all_objects.filter(id=id).first()

        if not test_case:
            return Response(
                {"detail": "Caso de teste não encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if test_case.is_active:
            return Response(
                {"detail": "O caso de teste já está ativo."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        test_case.is_active = True
        test_case.deleted_at = None
        test_case.deleted_by = None
        test_case.updated_by = request.user
        test_case.save(
            update_fields=["is_active", "deleted_at", "deleted_by", "updated_by", "updated_at"]
        )

        serializer = TestCaseSerializer(test_case, context={"request": request})
        return Response(serializer.data)

    @extend_schema(
        summary="Remove um anexo do caso de teste",
        tags=["Casos de Teste"],
        responses={204: None},
    )
    @action(detail=True, methods=["delete"], url_path=r"remove-attachment/(?P<attachment_id>[^/.]+)")
    def remove_attachment(self, request, id=None, attachment_id=None):
        """Remove um anexo/passo do caso de teste permanentemente."""
        test_case = self.get_object()
        attachment = test_case.attachments.filter(id=attachment_id).first()
        if not attachment:
            return Response(
                {"detail": "Anexo não encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )
        attachment.hard_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        summary="Atualiza um anexo existente do caso de teste",
        description="Aceita multipart/form-data. Todos os campos são opcionais (partial update).",
        tags=["Casos de Teste"],
        responses={200: TestCaseAttachmentSerializer},
    )
    @action(
        detail=True,
        methods=["patch"],
        url_path=r"update-attachment/(?P<attachment_id>[^/.]+)",
        parser_classes=[MultiPartParser, FormParser],
    )
    def update_attachment(self, request, id=None, attachment_id=None):
        """Atualiza descrição e/ou imagem de um anexo existente."""
        test_case = self.get_object()
        attachment = test_case.attachments.filter(id=attachment_id).first()
        if not attachment:
            return Response(
                {"detail": "Anexo não encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )
        write_serializer = TestCaseAttachmentWriteSerializer(
            attachment, data=request.data, partial=True
        )
        write_serializer.is_valid(raise_exception=True)
        write_serializer.save()
        read_serializer = TestCaseAttachmentSerializer(attachment, context={"request": request})
        return Response(read_serializer.data)

    @extend_schema(
        summary="Faz upload de anexo para o caso de teste",
        description="Aceita multipart/form-data com file, title, description, order.",
        tags=["Casos de Teste"],
        responses={201: TestCaseAttachmentSerializer},
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="add-attachment",
        parser_classes=[MultiPartParser, FormParser],
    )
    def add_attachment(self, request, id=None):
        """Faz upload de um anexo (imagem, PDF, etc) para o caso de teste."""
        test_case = self.get_object()

        write_serializer = TestCaseAttachmentWriteSerializer(data=request.data)
        write_serializer.is_valid(raise_exception=True)
        attachment = write_serializer.save(
            test_case=test_case,
            uploaded_by=request.user,
        )

        read_serializer = TestCaseAttachmentSerializer(attachment, context={"request": request})
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)
