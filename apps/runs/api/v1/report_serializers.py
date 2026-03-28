"""
Serializers para validação do JSON enviado pelo custom reporter do Playwright.

Valida a estrutura antes de passar para o ReportParserService.
Separa responsabilidades: serializer valida, service processa.
"""

from rest_framework import serializers

from apps.projects.models import Project
from apps.environments.models import Environment


# =============================================================================
# NESTED SERIALIZERS (sub-estruturas do JSON)
# =============================================================================

class ReportAttachmentSerializer(serializers.Serializer):
    name = serializers.CharField()
    content_type = serializers.CharField()
    path = serializers.CharField()


class ReportMetadataSerializer(serializers.Serializer):
    worker_index  = serializers.IntegerField(required=False, default=0)
    parallel_index = serializers.IntegerField(required=False, default=0)
    timeout_ms = serializers.IntegerField(required=False, default=0)
    stdout = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    stderr = serializers.ListField(child=serializers.CharField(), required=False, default=list)


class ReportErrorLocationSerializer(serializers.Serializer):
    file = serializers.CharField()
    line = serializers.IntegerField()
    column = serializers.IntegerField()


class ReportResultSerializer(serializers.Serializer):
    """Valida um item do array results[]."""

    VALID_STATUSES = ["PASSED", "FAILED", "SKIPPED", "FLAKY"]

    title = serializers.CharField()
    playwright_id = serializers.CharField()
    file = serializers.CharField()
    module = serializers.CharField()
    profile = serializers.CharField()

    status = serializers.ChoiceField(choices=VALID_STATUSES)
    retry_number = serializers.IntegerField(min_value=0, default=0)

    duration_seconds = serializers.FloatField(min_value=0)
    executed_at = serializers.DateTimeField()

    error_message = serializers.CharField(allow_blank=True, default="")
    stack_trace = serializers.CharField(allow_blank=True, default="")
    error_location = ReportErrorLocationSerializer(required=False, allow_null=True)

    attachments = ReportAttachmentSerializer(many=True, required=False, default=list)
    metadata = ReportMetadataSerializer(required=False)


class ReportRunSerializer(serializers.Serializer):
    """Valida o bloco run{} do JSON."""

    VALID_TRIGGER_TYPES = ["manual", "api", "scheduled"]

    project_id = serializers.UUIDField()
    environment_id = serializers.UUIDField()

    branch = serializers.CharField(allow_blank=True, default="")
    commit_sha = serializers.CharField(allow_blank=True, default="")
    commit_message = serializers.CharField(allow_blank=True, default="")
    trigger_type = serializers.ChoiceField(
        choices=VALID_TRIGGER_TYPES,
        default="manual"
    )

    playwright_version = serializers.CharField(allow_blank=True, default="")
    started_at = serializers.DateTimeField()
    finished_at = serializers.DateTimeField()
    duration_seconds = serializers.FloatField(min_value=0)


# =============================================================================
# SERIALIZER: DISPARAR PIPELINE GITLAB
# =============================================================================

class TriggerPipelineSerializer(serializers.Serializer):
    """
    Valida o payload para disparar uma pipeline no GitLab CI.

    project_id e environment_id identificam o contexto no TJGOHub.
    branch é o nome do branch a ser executado no GitLab.
    """
    project_id = serializers.UUIDField()
    environment_id = serializers.UUIDField()
    branch = serializers.CharField(default="main")

    def validate(self, attrs):
        project_id = attrs["project_id"]
        environment_id = attrs["environment_id"]

        try:
            project = Project.objects.get(id=project_id, is_active=True)
        except Project.DoesNotExist:
            raise serializers.ValidationError({
                "project_id": f"Projeto '{project_id}' não encontrado."
            })

        try:
            environment = Environment.objects.get(id=environment_id, is_active=True)
        except Environment.DoesNotExist:
            raise serializers.ValidationError({
                "environment_id": f"Ambiente '{environment_id}' não encontrado."
            })

        if environment.project_id != project.pk:
            raise serializers.ValidationError({
                "environment_id": (
                    f"O ambiente '{environment.get_env_type_display()}' não pertence "
                    f"ao projeto '{project.name}'."
                )
            })

        return attrs


# =============================================================================
# SERIALIZER PRINCIPAL
# =============================================================================

class ReportUploadSerializer(serializers.Serializer):
    """
    Serializer raiz para o payload completo do upload.

    Valida:
    - Estrutura do JSON (campos obrigatórios, tipos)
    - Existência do projeto e ambiente no banco
    - Que o ambiente pertence ao projeto
    """

    run = ReportRunSerializer()
    results = ReportResultSerializer(many=True)

    def validate(self, attrs):
        run = attrs["run"]

        project_id = run["project_id"]
        environment_id = run["environment_id"]

        # Valida existência do projeto
        try:
            project = Project.objects.get(id=project_id, is_active=True)
        except Project.DoesNotExist:
            raise serializers.ValidationError({
                "run": {"project_id": f"Projeto '{project_id}' não encontrado."}
            })

        # Valida existência do ambiente
        try:
            environment = Environment.objects.get(id=environment_id, is_active=True)
        except Environment.DoesNotExist:
            raise serializers.ValidationError({
                "run": {"environment_id": f"Ambiente '{environment_id}' não encontrado."}
            })

        # Valida que o ambiente pertence ao projeto
        if environment.project_id != project.pk:
            raise serializers.ValidationError({
                "run": {
                    "environment_id": (
                        f"O ambiente '{environment.get_env_type_display()}' não pertence "
                        f"ao projeto '{project.name}'."
                    )
                }
            })

        return attrs
