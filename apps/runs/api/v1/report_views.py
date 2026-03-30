"""
Endpoint de upload do relatório JSON gerado pelo Playwright Hub Reporter.

POST /api/v1/runs/upload-report/

Fluxo ASSÍNCRONO (com Celery):
    1. Recebe e valida o JSON
    2. Cria o TestRun com status PENDING (resposta imediata ~200ms)
    3. Enfileira a task de parse no Redis via Celery
    4. Retorna 202 Accepted com o run_id
    5. O Celery Worker processa em background e muda status para COMPLETED

Por que 202 e não 201?
    201 Created = "criei o recurso completo agora"
    202 Accepted = "recebi sua requisição e vou processar" ← semanticamente correto

Uso no CI/CD:
    curl -X POST https://hub.tjgo.jus.br/api/v1/runs/upload-report/ \\
      -H "Authorization: Bearer $TOKEN" \\
      -H "Content-Type: application/json" \\
      -d @test-results/tjgohub-report.json
"""

import logging

import requests
from django.conf import settings
from django.db import transaction
from drf_spectacular.utils import extend_schema, OpenApiExample
from rest_framework import status
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.environments.models import Environment
from apps.projects.models import Project
from apps.runs.api.v1.report_serializers import ReportUploadSerializer, TriggerPipelineSerializer
from apps.runs.models import TestRun
from apps.runs.tasks import parse_report_task

logger = logging.getLogger(__name__)


class UploadReportView(APIView):
    """
    Upload de relatório de testes do Playwright Hub.

    Recebe o JSON gerado pelo custom reporter (`tjgohub-reporter.ts`),
    cria o TestRun imediatamente e processa os resultados em background.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser]

    @extend_schema(
        summary="Upload de relatório de testes",
        description=(
            "Recebe o JSON gerado pelo tjgohub-reporter.ts do Playwright. "
            "Cria o TestRun com status PENDING e processa os resultados em background. "
            "Retorna 202 Accepted com o run_id para acompanhamento."
        ),
        tags=["Runs"],
        request=ReportUploadSerializer,
        responses={
            202: {"description": "Relatório aceito — processando em background"},
            400: {"description": "JSON inválido ou projeto/ambiente não encontrado"},
            500: {"description": "Erro interno ao criar o TestRun"},
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
        # 1. Valida o payload (projeto, ambiente, formato dos resultados)
        serializer = ReportUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        run_data = serializer.validated_data["run"]

        try:
            # 2. Busca as instâncias do banco (já validadas pelo serializer)
            project = Project.objects.get(id=run_data["project_id"])
            environment = Environment.objects.get(id=run_data["environment_id"])

            # 3. Cria o TestRun com status PENDING
            # Salvamos o mínimo necessário — o resto será preenchido pela task
            test_run = TestRun.objects.create(
                project=project,
                environment=environment,
                status=TestRun.STATUS_PENDING,
                trigger_type=run_data.get("trigger_type", TestRun.TRIGGER_API),
                triggered_by=request.user,
                created_by=request.user,
            )

        except Exception as exc:
            logger.exception("Erro ao criar TestRun: %s", exc)
            return Response(
                {"detail": f"Erro interno ao criar a execução: {str(exc)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # 4. Enfileira o parse para rodar em background após o commit
        #
        # Por que transaction.on_commit()?
        #   ATOMIC_REQUESTS=True envolve toda request em uma transaction.
        #   Se enfileirássemos a task ANTES do commit, o Celery Worker poderia
        #   tentar buscar o TestRun no banco antes dele ser visível → DoesNotExist.
        #   on_commit() garante que a task só vai para o Redis APÓS o commit.
        transaction.on_commit(
            lambda: parse_report_task.delay(
                run_id=str(test_run.id),
                report_data=serializer.validated_data,
                user_id=request.user.id,
            )
        )

        logger.info(
            "Relatório aceito | run_id=%s | resultados=%d",
            test_run.run_id,
            len(serializer.validated_data.get("results", [])),
        )

        # 5. Responde imediatamente — sem esperar o parse terminar
        return Response(
            {
                "run_id": test_run.run_id,
                "id": str(test_run.id),
                "status": TestRun.STATUS_PENDING,
                "detail": "Relatório recebido. Processando resultados em background.",
            },
            status=status.HTTP_202_ACCEPTED,
        )


class TriggerPipelineView(APIView):
    """
    Dispara uma pipeline no GitLab CI a partir da interface do TJGOHub.

    POST /api/v1/runs/trigger-pipeline/

    O backend faz a chamada autenticada ao GitLab usando o GITLAB_PRIVATE_TOKEN
    configurado no settings. O frontend não precisa expor o token.

    Fluxo:
        1. Valida project_id, environment_id e branch
        2. Chama POST /api/v4/projects/{id}/pipeline no GitLab
        3. Retorna gitlab_pipeline_id, web_url e status para o frontend
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    @extend_schema(
        summary="Disparar pipeline GitLab CI",
        description=(
            "Dispara uma pipeline no GitLab CI para o projeto e branch indicados. "
            "O token do GitLab fica no backend — o frontend apenas envia project_id, "
            "environment_id e branch."
        ),
        tags=["Runs"],
        request=TriggerPipelineSerializer,
        responses={
            200: {"description": "Pipeline disparada com sucesso"},
            400: {"description": "Dados inválidos ou projeto/ambiente não encontrado"},
            502: {"description": "Erro ao comunicar com o GitLab"},
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = TriggerPipelineSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        branch = serializer.validated_data["branch"]

        gitlab_url = settings.GITLAB_URL
        gitlab_token = settings.GITLAB_PRIVATE_TOKEN
        gitlab_proj_id = settings.GITLAB_PROJECT_ID

        if not gitlab_token or not gitlab_proj_id:
            return Response(
                {"detail": "GITLAB_PRIVATE_TOKEN ou GITLAB_PROJECT_ID não configurados no servidor."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        api_url = f"{gitlab_url}/api/v4/projects/{gitlab_proj_id}/pipeline"

        try:
            resp = requests.post(
                api_url,
                json={"ref": branch},
                headers={
                    "PRIVATE-TOKEN": gitlab_token,
                    "Content-Type": "application/json",
                },
                timeout=15,
            )
        except requests.RequestException as exc:
            logger.exception("Falha ao contatar o GitLab: %s", exc)
            return Response(
                {"detail": f"Não foi possível conectar ao GitLab: {str(exc)}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if resp.status_code not in (200, 201):
            logger.error("GitLab retornou %s: %s", resp.status_code, resp.text)
            return Response(
                {"detail": f"GitLab recusou a requisição ({resp.status_code}): {resp.text}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        data = resp.json()
        logger.info(
            "Pipeline disparada | gitlab_pipeline_id=%s | branch=%s | user=%s",
            data.get("id"),
            branch,
            request.user,
        )

        return Response(
            {
                "gitlab_pipeline_id": data["id"],
                "web_url": data["web_url"],
                "status": data["status"],
            },
            status=status.HTTP_200_OK,
        )
