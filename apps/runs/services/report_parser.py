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
        Executa o parsing completo dentro de uma transaction.

        Em caso de erro, tudo é revertido (nenhum TestRun parcial fica no banco).

        Returns:
            TestRun criado e salvo com métricas calculadas.
        """
        logger.info(
            "Iniciando parsing de relatório | projeto=%s | resultados=%d",
            self.run_data.get("project_id"),
            len(self.results_data),
        )

        test_run = self._create_test_run()
        self._create_test_results(test_run)

        # Recalcula métricas agregadas a partir dos TestResults criados
        test_run.calculate_metrics()
        test_run.save(update_fields=[
            "total_tests", "passed_tests", "failed_tests",
            "skipped_tests", "flaky_tests", "duration_seconds",
            "updated_at",
        ])

        logger.info(
            "Parsing concluído | run_id=%s | total=%d | passed=%d | failed=%d",
            test_run.run_id,
            test_run.total_tests,
            test_run.passed_tests,
            test_run.failed_tests,
        )

        return test_run

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
        Itera sobre results[] e cria um TestResult por item.
        Usa bulk_create para performance.
        """
        results_to_create = []

        for item in self.results_data:
            test_result = self._build_test_result(test_run, item)
            results_to_create.append(test_result)

        # bulk_create ignora o override de save() do modelo (que gera result_id)
        # Por isso usamos save() individual — aceitável para volumes < 10k
        for result in results_to_create:
            result.save()

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
