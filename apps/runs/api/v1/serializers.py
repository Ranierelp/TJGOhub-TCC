from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from apps.commons.api.v1.serializers import BaseSerializer
from apps.runs.models import TestRun
from apps.tags.api.v1.serializers import TagSerializer
from apps.environments.api.v1.serializers import EnvironmentListSerializer
from apps.projects.api.v1.serializers import ProjectListSerializer


class TestRunListSerializer(BaseSerializer):
    """
    Serializer compacto para listagens.
    Foco nas métricas e identificação — evita carregar resultados completos.
    """

    run_id = serializers.CharField(read_only=True)
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    trigger_type_display = serializers.CharField(
        source="get_trigger_type_display", read_only=True
    )
    success_rate = serializers.FloatField(
        source="get_success_rate", read_only=True
    )
    duration_formatted = serializers.CharField(read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    environment_name = serializers.CharField(source="environment.name", read_only=True)
    tags = TagSerializer(many=True, read_only=True)

    class Meta(BaseSerializer.Meta):
        model = TestRun
        fields = [
            "id",
            "run_id",
            "project",
            "project_name",
            "environment",
            "environment_name",
            "status",
            "status_display",
            "trigger_type",
            "trigger_type_display",
            "branch",
            "total_tests",
            "passed_tests",
            "failed_tests",
            "skipped_tests",
            "flaky_tests",
            "success_rate",
            "duration_seconds",
            "duration_formatted",
            "tags",
            "started_at",
            "completed_at",
        ]


class TestRunSerializer(BaseSerializer):
    """
    Serializer completo para criação, edição e detalhe de execução.

    Campos write:
        project, environment, trigger_type, branch, commit_sha,
        commit_message, tag_ids

    Campos read-only:
        run_id (gerado pelo model), métricas (preenchidas pelo parser),
        status (gerenciado pelos métodos do model: start/complete/fail/cancel)
    """

    # Declarados explicitamente — não sobrescritos pelo BaseSerializer.__init__
    run_id = serializers.CharField(read_only=True)

    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    trigger_type_display = serializers.CharField(
        source="get_trigger_type_display", read_only=True
    )

    project_name = serializers.CharField(source="project.name", read_only=True)
    environment_name = serializers.CharField(source="environment.name", read_only=True)
    triggered_by_name = serializers.SerializerMethodField()

    # Métricas calculadas — nunca enviadas pelo cliente
    success_rate = serializers.FloatField(
        source="get_success_rate", read_only=True
    )
    duration_formatted = serializers.CharField(read_only=True)
    results_count = serializers.SerializerMethodField()

    # Tags — leitura objeto completo, escrita lista de UUIDs
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        help_text="Lista de UUIDs das tags para associar à execução",
    )

    class Meta(BaseSerializer.Meta):
        model = TestRun
        fields = [
            "id",
            "run_id",
            # Relacionamentos
            "project",
            "project_name",
            "environment",
            "environment_name",
            "triggered_by",
            "triggered_by_name",
            # Status
            "status",
            "status_display",
            "trigger_type",
            "trigger_type_display",
            # Git
            "branch",
            "commit_sha",
            "commit_message",
            # Métricas (read-only)
            "total_tests",
            "passed_tests",
            "failed_tests",
            "skipped_tests",
            "flaky_tests",
            "duration_seconds",
            "duration_formatted",
            "success_rate",
            "results_count",
            # Tags
            "tags",
            "tag_ids",
            # Timestamps
            "started_at",
            "completed_at",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
        ]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_triggered_by_name(self, obj) -> str | None:
        if obj.triggered_by:
            return obj.triggered_by.get_full_name() or obj.triggered_by.email
        return None

    @extend_schema_field(serializers.IntegerField())
    def get_results_count(self, obj) -> int:
        if hasattr(obj, "_results_count"):
            return obj._results_count
        return obj.test_results.count()

    def validate(self, attrs):
        """Valida que environment pertence ao project enviado."""
        project = attrs.get("project", getattr(self.instance, "project", None))
        environment = attrs.get("environment", getattr(self.instance, "environment", None))

        if project and environment:
            if environment.project_id != project.pk:
                raise serializers.ValidationError(
                    {"environment": "Este ambiente não pertence ao projeto selecionado."}
                )
        return attrs

    def create(self, validated_data):
        tag_ids = validated_data.pop("tag_ids", [])
        # triggered_by preenchido pelo viewset
        instance = super().create(validated_data)
        if tag_ids:
            from apps.tags.models import Tag
            instance.tags.set(Tag.objects.filter(id__in=tag_ids))
        return instance

    def update(self, instance, validated_data):
        tag_ids = validated_data.pop("tag_ids", None)
        instance = super().update(instance, validated_data)
        if tag_ids is not None:
            from apps.tags.models import Tag
            instance.tags.set(Tag.objects.filter(id__in=tag_ids))
        return instance
