from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from apps.commons.api.v1.serializers import BaseSerializer
from apps.results.models import TestResult


class TestResultListSerializer(BaseSerializer):
    """
    Serializer compacto para listagens e para o action runs/{id}/results/.
    Omite stack_trace e metadata para reduzir payload.
    """

    result_id = serializers.CharField(read_only=True)
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    duration_formatted = serializers.CharField(read_only=True)
    error_summary = serializers.CharField(
        source="get_error_summary", read_only=True
    )
    test_case_title = serializers.SerializerMethodField()
    artifacts_count = serializers.SerializerMethodField()

    class Meta(BaseSerializer.Meta):
        model = TestResult
        fields = [
            "id",
            "result_id",
            "test_run",
            "test_case",
            "test_case_title",
            "title",
            "status",
            "status_display",
            "duration_seconds",
            "duration_formatted",
            "retry_number",
            "error_summary",
            "artifacts_count",
            "executed_at",
        ]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_test_case_title(self, obj) -> str | None:
        if obj.test_case:
            return obj.test_case.title
        return None

    @extend_schema_field(serializers.IntegerField())
    def get_artifacts_count(self, obj) -> int:
        if hasattr(obj, "_artifacts_count"):
            return obj._artifacts_count
        return obj.artifacts.count() if hasattr(obj, "artifacts") else 0


class TestResultSerializer(BaseSerializer):
    """
    Serializer completo para detalhe de resultado.
    Inclui error_message, stack_trace e metadata completos.

    Todos os campos são read-only — resultados são criados pelo parser XML,
    nunca pelo usuário diretamente via API.
    A única operação de escrita permitida é mark-as-flaky (action dedicada).
    """

    result_id = serializers.CharField(read_only=True)
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    duration_formatted = serializers.CharField(read_only=True)
    error_summary = serializers.CharField(
        source="get_error_summary", read_only=True
    )
    test_name = serializers.CharField(read_only=True)

    # Nested compacto do test_case
    test_case_title = serializers.SerializerMethodField()
    test_case_case_id = serializers.SerializerMethodField()

    # Run de referência
    run_id = serializers.CharField(source="test_run.run_id", read_only=True)

    artifacts_count = serializers.SerializerMethodField()

    class Meta(BaseSerializer.Meta):
        model = TestResult
        fields = [
            "id",
            "result_id",
            # Relacionamentos
            "test_run",
            "run_id",
            "test_case",
            "test_case_title",
            "test_case_case_id",
            "test_name",
            # Status
            "status",
            "status_display",
            # Métricas
            "duration_seconds",
            "duration_formatted",
            "retry_number",
            # Erro
            "error_message",
            "error_summary",
            "stack_trace",
            # Extras
            "metadata",
            "artifacts_count",
            # Timestamps
            "executed_at",
            "created_at",
        ]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_test_case_title(self, obj) -> str | None:
        return obj.test_case.title if obj.test_case else None

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_test_case_case_id(self, obj) -> str | None:
        return obj.test_case.case_id if obj.test_case else None

    @extend_schema_field(serializers.IntegerField())
    def get_artifacts_count(self, obj) -> int:
        if hasattr(obj, "_artifacts_count"):
            return obj._artifacts_count
        return obj.artifacts.count() if hasattr(obj, "artifacts") else 0
