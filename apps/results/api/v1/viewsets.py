# apps/results/api/v1/viewsets.py

from django.db.models import Count
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from drf_spectacular.utils import extend_schema, extend_schema_view


from apps.results.models import TestResult
from .serializers import TestResultSerializer, TestResultListSerializer
from .filters import TestResultFilter


@extend_schema_view(
    list=extend_schema(summary="Lista resultados de teste", tags=["Resultados"]),
    retrieve=extend_schema(summary="Detalha um resultado", tags=["Resultados"]),
)
class TestResultViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet,
):
    """
    ViewSet read-only para resultados de teste.

    Resultados são criados exclusivamente pelo parser XML (upload de JUnit XML
    via runs/upload-report/ — a ser implementado). Não há create, update nem
    destroy disponíveis via API para o usuário final.

    ## Operações disponíveis
    - GET /results/         → list (com filtros)
    - GET /results/{id}/    → retrieve

    ## Action
    - POST /results/{id}/mark-as-flaky/ → marca resultado como FLAKY
    """

    permission_classes = [IsAuthenticated]
    filterset_class = TestResultFilter
    search_fields = ["result_id", "error_message", "test_case__title", "test_run__run_id"]
    ordering_fields = ["executed_at", "status", "duration_seconds"]
    ordering = ["-executed_at"]
    lookup_field = "id"

    def get_queryset(self):
        return (
            TestResult.objects.all()
            .select_related(
                "test_run",
                "test_run__project",
                "test_case",
                "created_by",
            )
            .annotate(
                _artifacts_count=Count("artifacts", distinct=True)
            )
            .order_by("-executed_at")
        )

    def get_serializer_class(self):
        if self.action == "list":
            return TestResultListSerializer
        return TestResultSerializer

    # =========================================================================
    # ACTIONS
    # =========================================================================

    @extend_schema(
        summary="Marca resultado como flaky",
        description=(
            "Altera o status do resultado para FLAKY (instável). "
            "Usado quando um teste apresenta comportamento não determinístico."
        ),
        tags=["Resultados"],
        responses={200: TestResultSerializer},
    )
    @action(detail=True, methods=["post"], url_path="mark-as-flaky")
    def mark_as_flaky(self, request, id=None):
        result = self.get_object()

        if result.status == TestResult.STATUS_FLAKY:
            return Response(
                {"detail": "O resultado já está marcado como flaky."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result.mark_as_flaky()

        test_run = result.test_run
        test_run.calculate_metrics()
        test_run.save(update_fields=[
            'total_tests', 'passed_tests', 'failed_tests',
            'skipped_tests', 'flaky_tests', 'duration_seconds',
            'updated_at',
        ])

        serializer = TestResultSerializer(result, context={"request": request})
        return Response(serializer.data)

