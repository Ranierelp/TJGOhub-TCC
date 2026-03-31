"""
Tasks Celery para o app de runs.

Executadas em background pelo Celery Worker — não bloqueiam o servidor HTTP.

Para rodar o worker:
    celery -A tjgohub worker --loglevel=info
"""

import logging

from celery import shared_task
from apps.runs.models import TestRun
from apps.users.models import User
from apps.runs.services.report_parser import ReportParserService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def parse_report_task(self, run_id: str, report_data: dict, user_id: int):
    """
    Processa o relatório JSON do Playwright em background.

    Chamada pela UploadReportView após criar o TestRun com status PENDING.
    Ao terminar, o TestRun é atualizado para COMPLETED (ou FAILED em caso de erro).

    Args:
        run_id:      UUID (str) do TestRun já criado no banco
        report_data: dict validado pelo ReportUploadSerializer (run + results)
        user_id:     ID do usuário que fez o upload (para created_by nos results)

    Parâmetros do decorador:
        bind=True:      dá acesso ao `self` (a própria task) — necessário para retry
        max_retries=3:  tenta novamente até 3 vezes antes de desistir
    """
    # Importações locais evitam problemas de importação circular no startup do Django

    logger.info("Task iniciada | run_id=%s | user_id=%s", run_id, user_id)

    try:
        run = TestRun.objects.get(id=run_id)
        user = User.objects.get(id=user_id)

        # Executa o parse: cria TestResults e calcula métricas
        service = ReportParserService(report_data=report_data, user=user)
        service.parse_into(run)

        logger.info(
            "Task concluída | run_id=%s | total=%d | passed=%d | failed=%d",
            run_id,
            run.total_tests,
            run.passed_tests,
            run.failed_tests,
        )

    except Exception as exc:
        logger.error("Erro na task | run_id=%s | erro=%s", run_id, exc)

        # Tenta marcar o run como FAILED para o usuário saber que algo deu errado
        try:
            run = TestRun.objects.get(id=run_id)
            run.fail()
        except Exception:
            pass  # Se o run não existe mais, ignora

        # self.retry re-enfileira a task após `countdown` segundos
        # exc=exc preserva a exceção original para o traceback
        raise self.retry(exc=exc, countdown=30)
