from django.db.models import Count
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view
from apps.results.models import TestResult
from apps.results.api.v1.serializers import TestResultListSerializer
from apps.commons.api.v1.viewsets import BaseModelApiViewSet
from apps.runs.models import TestRun
from .serializers import TestRunSerializer, TestRunListSerializer
from .filters import TestRunFilter


@extend_schema_view(
    list=extend_schema(summary="Lista execuções de teste", tags=["Execuções"]),
    retrieve=extend_schema(summary="Detalha uma execução", tags=["Execuções"]),
    create=extend_schema(summary="Cria uma execução", tags=["Execuções"]),
    update=extend_schema(summary="Atualiza uma execução (PUT)", tags=["Execuções"]),
    partial_update=extend_schema(summary="Atualiza parcialmente (PATCH)", tags=["Execuções"]),
    destroy=extend_schema(summary="Arquiva uma execução (soft delete)", tags=["Execuções"]),
)
class TestRunViewSet(BaseModelApiViewSet):
    """
    ViewSet para gerenciamento de execuções de teste.

    ## Operações padrão
    - GET    /runs/         → list
    - POST   /runs/         → create
    - GET    /runs/{id}/    → retrieve
    - PUT    /runs/{id}/    → update
    - PATCH  /runs/{id}/    → partial_update
    - DELETE /runs/{id}/    → destroy (soft delete)

    ## Actions de ciclo de vida
    - POST /runs/{id}/start/    → PENDING → RUNNING
    - POST /runs/{id}/complete/ → RUNNING → COMPLETED (recalcula métricas)
    - POST /runs/{id}/fail/     → * → FAILED
    - POST /runs/{id}/cancel/   → * → CANCELLED

    ## Actions de consulta
    - GET /runs/by-project/{uuid}/     → execuções de um projeto
    - GET /runs/by-environment/{uuid}/ → execuções de um ambiente
    - GET /runs/{id}/results/          → resultados desta execução (paginados)
    """

    model = TestRun
    filterset_class = TestRunFilter
    search_fields = ["run_id", "branch", "commit_sha", "commit_message", "project__name"]
    ordering_fields = ["started_at", "created_at", "status", "total_tests"]
    ordering = ["-started_at", "-created_at"]

    def get_queryset(self):
        return (
            TestRun.objects.all()
            .select_related(
                "project", "environment", "triggered_by",
                "created_by", "updated_by"
            )
            .prefetch_related("tags")
            .annotate(_results_count=Count("test_results", distinct=True))
            .order_by("-started_at", "-created_at")
        )

    def get_serializer_class(self):
        if self.action == "list":
            return TestRunListSerializer
        return TestRunSerializer

    def perform_create(self, serializer):
        """Preenche triggered_by com o usuário autenticado."""
        serializer.validated_data["triggered_by"] = self.request.user
        super().perform_create(serializer)

    # =========================================================================
    # ACTIONS — CICLO DE VIDA
    # =========================================================================

    @extend_schema(
        summary="Inicia execução",
        description="Transição: PENDING → RUNNING. Registra started_at.",
        tags=["Execuções"],
        responses={200: TestRunSerializer},
    )
    @action(detail=True, methods=["post"], url_path="start")
    def start(self, request, id=None):
        run = self.get_object()
        try:
            run.start()
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            TestRunSerializer(run, context={"request": request}).data
        )

    @extend_schema(
        summary="Conclui execução",
        description="Transição: RUNNING → COMPLETED. Recalcula métricas a partir dos TestResults.",
        tags=["Execuções"],
        responses={200: TestRunSerializer},
    )
    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, id=None):
        run = self.get_object()
        try:
            run.complete()
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            TestRunSerializer(run, context={"request": request}).data
        )

    @extend_schema(
        summary="Marca execução como falhada",
        description="Transição: qualquer estado não-finalizado → FAILED.",
        tags=["Execuções"],
        responses={200: TestRunSerializer},
    )
    @action(detail=True, methods=["post"], url_path="fail")
    def fail(self, request, id=None):
        run = self.get_object()
        try:
            run.fail()
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            TestRunSerializer(run, context={"request": request}).data
        )

    @extend_schema(
        summary="Cancela execução",
        description="Transição: qualquer estado não-finalizado → CANCELLED.",
        tags=["Execuções"],
        responses={200: TestRunSerializer},
    )
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, id=None):
        run = self.get_object()
        try:
            run.cancel(user=request.user)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            TestRunSerializer(run, context={"request": request}).data
        )

    @extend_schema(
        summary="Recalcula métricas",
        description=(
            "Força o recálculo de total_tests, passed_tests, failed_tests, etc. "
            "Útil se o parser falhou ou se resultados foram alterados manualmente."
        ),
        tags=["Execuções"],
        responses={200: TestRunSerializer},
    )
    @action(detail=True, methods=["post"], url_path="recalculate-metrics")
    def recalculate_metrics(self, request, id=None):
        run = self.get_object()
        run.calculate_metrics()
        run.save(update_fields=[
            "total_tests", "passed_tests", "failed_tests",
            "skipped_tests", "flaky_tests", "duration_seconds", "updated_at"
        ])
        return Response(
            TestRunSerializer(run, context={"request": request}).data
        )

    # =========================================================================
    # ACTIONS — CONSULTA
    # =========================================================================

    @extend_schema(
        summary="Execuções de um projeto",
        tags=["Execuções"],
        responses={200: TestRunListSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path=r"by-project/(?P<project_id>[^/.]+)")
    def by_project(self, request, project_id=None):
        qs = self.get_queryset().filter(project__id=project_id)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = TestRunListSerializer(page, many=True, context={"request": request})
            return self.get_paginated_response(serializer.data)
        serializer = TestRunListSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)

    @extend_schema(
        summary="Execuções de um ambiente",
        tags=["Execuções"],
        responses={200: TestRunListSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path=r"by-environment/(?P<environment_id>[^/.]+)")
    def by_environment(self, request, environment_id=None):
        qs = self.get_queryset().filter(environment__id=environment_id)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = TestRunListSerializer(page, many=True, context={"request": request})
            return self.get_paginated_response(serializer.data)
        serializer = TestRunListSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)

    @extend_schema(
        summary="Resultados de uma execução",
        description="Retorna os TestResults paginados desta execução.",
        tags=["Execuções"],
    )
    @action(detail=True, methods=["get"], url_path="results")
    def results(self, request, id=None):
        """
        Atalho para listar os resultados de uma execução específica.
        Evita que o front precise filtrar em /results/?test_run=<id>.
        Suporta ?status=PASSED|FAILED|FLAKY|SKIPPED para filtrar por status.
        """

        run = TestRun.objects.filter(id=id).first()
        if not run:
            return Response(
                {"detail": "Execução não encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )

        qs = (
            run.test_results
            .select_related("test_case")
            .order_by("executed_at")
        )

        status_param = request.query_params.get("status")
        if status_param:
            valid_statuses = [
                TestResult.STATUS_PASSED,
                TestResult.STATUS_FAILED,
                TestResult.STATUS_SKIPPED,
                TestResult.STATUS_FLAKY,
            ]
            if status_param not in valid_statuses:
                return Response(
                    {"detail": f"Status inválido. Valores aceitos: {', '.join(valid_statuses)}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs = qs.filter(status=status_param)

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = TestResultListSerializer(page, many=True, context={"request": request})
            return self.get_paginated_response(serializer.data)
        serializer = TestResultListSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)
