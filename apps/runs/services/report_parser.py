"""
Parser do relatório JSON gerado pelo custom reporter do Playwright.

Responsabilidade:
    Recebe o dict já validado pelo ReportUploadSerializer e cria:
    - 1 TestRun  (COMPLETED)
    - N TestResult (um por item em results[])
    - Vincula TestCase existente via playwright_id (opcional)
    - Atualiza métricas ao final

Uso:
    from apps.runs.services.report_parser import ReportParserService

    service = ReportParserService(report_data=validated_data, user=request.user)
    test_run = service.parse()
"""

import logging
from datetime import datetime, timezone as dt_timezone

from django.db import transaction
from django.utils import timezone

from apps.runs.models import TestRun
from apps.results.models import TestResult
from apps.cases.models import TestCase
from apps.projects.models import Project
from apps.environments.models import Environment

logger = logging.getLogger(__name__)


class ReportParserService:
    """
    Serviço de parsing do JSON do Playwright Hub.

    Args:
        report_data: dict já validado pelo ReportUploadSerializer
        user: User que está fazendo o upload (vira triggered_by e created_by)
    """

    # Mapeamento de status do reporter → status do modelo
    STATUS_MAP = {
        "PASSED":  TestResult.STATUS_PASSED,
        "FAILED":  TestResult.STATUS_FAILED,
        "SKIPPED": TestResult.STATUS_SKIPPED,
        "FLAKY":   TestResult.STATUS_FLAKY,
    }

    # Mapeamento de artifact content_type → artifact_type do modelo
    ARTIFACT_TYPE_MAP = {
        "video/webm":      "VIDEO",
        "video/mp4":       "VIDEO",
        "image/png":       "SCREENSHOT",
        "image/jpeg":      "SCREENSHOT",
        "image/gif":       "SCREENSHOT",
        "text/plain":      "LOG",
        "text/markdown":   "LOG",
        "application/zip": "TRACE",
    }

    def __init__(self, report_data: dict, user):
        self.data = report_data
        self.user = user
        self.run_data = report_data["run"]
        self.results_data = report_data["results"]

        # Cache de TestCase por playwright_id para evitar N+1
        self._test_case_cache: dict[str, TestCase | None] = {}

    # =========================================================================
    # ENTRADA PRINCIPAL
    # =========================================================================

    @transaction.atomic
    def parse(self) -> TestRun:
        """
        Modo síncrono: cria o TestRun e processa tudo na mesma chamada.

        Usado diretamente pela view quando Celery não está disponível,
        ou em testes automatizados.

        Returns:
            TestRun criado e salvo com métricas calculadas.
        """
        logger.info(
            "Iniciando parsing síncrono | projeto=%s | resultados=%d",
            self.run_data.get("project_id"),
            len(self.results_data),
        )

        test_run = self._create_test_run()
        self._finish_parse(test_run)
        return test_run

    @transaction.atomic
    def parse_into(self, test_run: TestRun) -> None:
        """
        Modo assíncrono: recebe um TestRun já existente (status PENDING)
        e preenche os resultados + métricas.

        Chamado pela Celery task após o TestRun ter sido criado pela view
        e commitado no banco.

        Args:
            test_run: TestRun já salvo com status PENDING
        """
        logger.info(
            "Iniciando parsing assíncrono | run_id=%s | resultados=%d",
            test_run.run_id,
            len(self.results_data),
        )

        # Preenche campos do run que vieram no payload mas não foram salvos
        # pela view (que só salvou o mínimo para responder rápido)
        run = self.run_data
        test_run.branch = run.get("branch", "")
        test_run.commit_sha = run.get("commit_sha", "")
        test_run.commit_message = run.get("commit_message", "")
        test_run.started_at = self._parse_datetime(run.get("started_at"))
        test_run.completed_at = self._parse_datetime(run.get("finished_at"))
        test_run.duration_seconds = run.get("duration_seconds", 0.0)
        test_run.save(update_fields=[
            "branch", "commit_sha", "commit_message",
            "started_at", "completed_at", "duration_seconds", "updated_at",
        ])

        self._finish_parse(test_run)

    def _finish_parse(self, test_run: TestRun) -> None:
        """
        Parte comum dos dois modos: cria results, calcula métricas e marca COMPLETED.
        """
        self._create_test_results(test_run)

        test_run.calculate_metrics()
        test_run.status = TestRun.STATUS_COMPLETED
        test_run.save(update_fields=[
            "status", "total_tests", "passed_tests", "failed_tests",
            "skipped_tests", "flaky_tests", "duration_seconds", "updated_at",
        ])

        logger.info(
            "Parsing concluído | run_id=%s | total=%d | passed=%d | failed=%d",
            test_run.run_id,
            test_run.total_tests,
            test_run.passed_tests,
            test_run.failed_tests,
        )

    # =========================================================================
    # CRIAÇÃO DO TEST RUN
    # =========================================================================

    def _create_test_run(self) -> TestRun:
        """
        Cria o TestRun diretamente com status COMPLETED.

        O parser não passa pelo lifecycle (PENDING → RUNNING → COMPLETED)
        porque recebe resultados já finalizados.
        """
        run = self.run_data

        # Busca as instâncias pelo UUID (field id) para evitar passar UUID
        # direto no FK que referencia pkid (BigAutoField) — causaria bigint out of range
        project = Project.objects.get(id=run["project_id"])
        environment = Environment.objects.get(id=run["environment_id"])

        # Converte timestamps ISO → datetime aware
        started_at = self._parse_datetime(run.get("started_at"))
        finished_at = self._parse_datetime(run.get("finished_at"))

        test_run = TestRun(
            project=project,
            environment=environment,
            status=TestRun.STATUS_COMPLETED,
            trigger_type=run.get("trigger_type", TestRun.TRIGGER_MANUAL),
            branch=run.get("branch", ""),
            commit_sha=run.get("commit_sha", ""),
            commit_message=run.get("commit_message", ""),
            started_at=started_at,
            completed_at=finished_at,
            duration_seconds=run.get("duration_seconds", 0.0),
            triggered_by=self.user,
            created_by=self.user,
        )

        # Salva para gerar o run_id automático (model.save() gera run-YYYYMMDD-NNN)
        test_run.save()

        return test_run

    # =========================================================================
    # CRIAÇÃO DOS TEST RESULTS
    # =========================================================================

    def _create_test_results(self, test_run: TestRun) -> None:
        """
        Cria todos os TestResults de uma vez com bulk_create.

        Por que bulk_create?
            Sem bulk_create: N testes = N INSERTs separados no banco (lento)
            Com bulk_create: N testes = 1 INSERT com N linhas (muito mais rápido)

        Por que pré-gerar o result_id?
            O bulk_create pula o save() do modelo, que é onde o result_id
            normalmente é gerado. Por isso geramos o ID aqui, em Python,
            antes de inserir.

        Antes:  300 testes → 300 queries ao banco
        Depois: 300 testes → 1 query (ou 2 se > 500 resultados)
        """
        results_to_create = []
        prefix = f"result-{test_run.run_id}-"

        # enumerate(start=1): itera com índice começando em 1
        for index, item in enumerate(self.results_data, start=1):
            result = self._build_test_result(test_run, item)
            # Gera o result_id em Python em vez de deixar para o save() do modelo
            # Formato: result-run-20260314-001-001, result-run-20260314-001-002, ...
            result.result_id = f"{prefix}{index:03d}"
            results_to_create.append(result)

        # batch_size=500: insere de 500 em 500 para não gerar queries SQL muito longas
        # ignore_conflicts=False (padrão): levanta erro se result_id duplicado
        TestResult.objects.bulk_create(results_to_create, batch_size=500)

    def _build_test_result(self, test_run: TestRun, item: dict) -> TestResult:
        """
        Constrói um TestResult a partir de um item do results[].
        Não salva — apenas monta o objeto.
        """
        status = self.STATUS_MAP.get(item.get("status", "FAILED"), TestResult.STATUS_FAILED)

        # Tenta vincular ao TestCase cadastrado via playwright_id
        test_case = self._resolve_test_case(item.get("playwright_id", ""))

        # Metadata: tudo que é específico do Playwright mas útil para debug
        metadata = {
            "profile": item.get("profile", ""),
            "module": item.get("module", ""),
            "file": item.get("file", ""),
            "error_location": item.get("error_location"),
            "worker_index": item.get("metadata", {}).get("worker_index"),
            "parallel_index": item.get("metadata", {}).get("parallel_index"),
            "timeout_ms": item.get("metadata", {}).get("timeout_ms"),
            "stdout": item.get("metadata", {}).get("stdout", []),
        }

        executed_at = self._parse_datetime(item.get("executed_at"))

        return TestResult(
            test_run=test_run,
            test_case=test_case,
            title=item.get("title", ""),
            status=status,
            duration_seconds=item.get("duration_seconds", 0.0),
            error_message=item.get("error_message", ""),
            stack_trace=item.get("stack_trace", ""),
            retry_number=item.get("retry_number", 0),
            executed_at=executed_at or timezone.now(),
            metadata=metadata,
            created_by=self.user,
        )

    # =========================================================================
    # RESOLUÇÃO DO TEST CASE
    # =========================================================================

    def _resolve_test_case(self, playwright_id: str) -> TestCase | None:
        """
        Busca TestCase pelo playwright_id.

        Usa cache interno para evitar uma query por resultado quando
        vários resultados compartilham o mesmo playwright_id.

        Returns:
            TestCase se encontrado, None caso contrário.
            None é válido — TestResult pode existir sem TestCase vinculado.
        """
        if not playwright_id:
            return None

        if playwright_id in self._test_case_cache:
            return self._test_case_cache[playwright_id]

        try:
            test_case = TestCase.objects.get(
                playwright_id=playwright_id,
                is_active=True,
            )
        except TestCase.DoesNotExist:
            test_case = None
            logger.debug(
                "TestCase não encontrado para playwright_id=%s — resultado será vinculado sem caso.",
                playwright_id,
            )

        self._test_case_cache[playwright_id] = test_case
        return test_case

    # =========================================================================
    # UTILITÁRIOS
    # =========================================================================

    @staticmethod
    def _parse_datetime(value) -> datetime | None:
        """
        Converte string ISO 8601 em datetime aware (UTC).
        Também aceita datetime já convertido pelo DRF DateTimeField.
        Retorna None se valor inválido ou ausente.
        """
        if not value:
            return None

        # O DRF DateTimeField já converte a string para datetime durante a validação
        # do serializer. Se chegar aqui como datetime, apenas garante timezone UTC.
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=dt_timezone.utc)
            return value

        try:
            # O Playwright pode gerar timestamps com "Z" (UTC)
            # datetime.fromisoformat não suporta "Z", então substituímos por "+00:00"
            # Exemplo: "2024-05-01T12:34:56.789Z" → "2024-05-01T12:34:56.789+00:00"
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=dt_timezone.utc)
            return dt
        except (ValueError, AttributeError, TypeError):
            logger.warning("Falha ao parsear datetime: %s", value)
            return None
