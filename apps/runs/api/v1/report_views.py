"""
Endpoint de upload do relatório JSON gerado pelo Playwright Hub Reporter.

POST /api/v1/runs/upload-report/

Fluxo:
    1. Recebe o JSON (multipart ou application/json)
    2. Valida com ReportUploadSerializer
    3. Passa para ReportParserService
    4. Retorna o TestRun criado
"""

import logging

from drf_spectacular.utils import extend_schema, OpenApiExample
from rest_framework import status
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.runs.api.v1.report_serializers import ReportUploadSerializer
from apps.runs.api.v1.serializers import TestRunSerializer
from apps.runs.services.report_parser import ReportParserService

logger = logging.getLogger(__name__)


class UploadReportView(APIView):
    """
    Upload de relatório de testes do Playwright Hub.

    Recebe o JSON gerado pelo custom reporter (`tjgohub-reporter.ts`),
    cria o TestRun e todos os TestResults em uma única transação atômica.

    ## Uso no CI/CD

    ```bash
    curl -X POST \\
      https://hub.tjgo.jus.br/api/v1/runs/upload-report/ \\
      -H "Authorization: Bearer $TOKEN" \\
      -H "Content-Type: application/json" \\
      -d @test-results/tjgohub-report.json
    ```

    ## Resposta de sucesso (201)

    Retorna o TestRun criado com todas as métricas já calculadas.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser]

    @extend_schema(
        summary="Upload de relatório de testes",
        description=(
            "Recebe o JSON gerado pelo tjgohub-reporter.ts do Playwright, "
            "cria o TestRun e os TestResults em uma transação atômica."
        ),
        tags=["Runs"],
        request=ReportUploadSerializer,
        responses={
            201: TestRunSerializer,
            400: {"description": "JSON inválido ou projeto/ambiente não encontrado"},
            500: {"description": "Erro interno durante o parsing"},
        },
        examples=[
            OpenApiExample(
                "Exemplo de payload",
                value={
                    "run": {
                        "project_id": "uuid-do-projeto",
                        "environment_id": "uuid-do-ambiente",
                        "branch": "main",
                        "commit_sha": "abc123",
                        "commit_message": "feat: nova funcionalidade",
                        "trigger_type": "api",
                        "playwright_version": "1.57.0",
                        "started_at": "2026-02-24T01:44:35.218Z",
                        "finished_at": "2026-02-24T01:46:06.998Z",
                        "duration_seconds": 91.78,
                    },
                    "results": [
                        {
                            "title": "ID 033 Contador emite guia final zero",
                            "playwright_id": "id-033-contador-emite-guia-final-zero-com-sucesso",
                            "file": "emissao_guias/emitir_guia_final_zero.spec.ts",
                            "module": "emissao_guias",
                            "profile": "contador",
                            "status": "PASSED",
                            "retry_number": 0,
                            "duration_seconds": 9.048,
                            "executed_at": "2026-02-24T01:45:05.189Z",
                            "error_message": "",
                            "stack_trace": "",
                            "error_location": None,
                            "attachments": [],
                            "metadata": {
                                "worker_index": 7,
                                "parallel_index": 3,
                                "timeout_ms": 40000,
                                "stdout": [],
                                "stderr": [],
                            },
                        }
                    ],
                },
                request_only=True,
            )
        ],
    )
    def post(self, request, *args, **kwargs):
        # 1. Valida o payload
        serializer = ReportUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # 2. Executa o parsing
        try:
            service = ReportParserService(
                report_data=serializer.validated_data,
                user=request.user,
            )
            test_run = service.parse()

        except Exception as exc:
            logger.exception("Erro durante parsing do relatório: %s", exc)
            return Response(
                {"detail": f"Erro interno durante o parsing: {str(exc)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # 3. Retorna o TestRun criado
        response_serializer = TestRunSerializer(
            test_run,
            context={"request": request},
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

