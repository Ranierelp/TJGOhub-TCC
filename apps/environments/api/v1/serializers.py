from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from apps.commons.api.v1.serializers import BaseSerializer
from apps.environments.models import Environment
from apps.projects.api.v1.serializers import ProjectSerializer

class EnvironmentListSerializer(BaseSerializer):
    """
    Serializer compacto para listagens e uso nested em outros serializers
    (ex: TestRunSerializer).
    """

    env_type_display = serializers.CharField(
        source='get_env_type_display',
        read_only=True
    )

    class Meta(BaseSerializer.Meta):
        model = Environment
        fields = [
            'id',
            'base_url',
            'env_type',
            'env_type_display',
            'is_active',
        ]

class EnvironmentSerializer(BaseSerializer):
    """
    Serializer completo para criação, edição e detalhe de ambiente.

    Campos de escrita:
        project  → UUID do projeto pai
        base_url → URL base validada pelo URLField do model
        env_type → development | staging | production

    Campos somente leitura:
        project_name, test_runs_count e todos os de rastreabilidade
        (gerenciados pelo BaseSerializer.__init__)
    """

    project_name = serializers.CharField(
        source='project.name',
        read_only=True
    )

    env_type_display = serializers.CharField(
        source='get_env_type_display',
        read_only=True
    )

    test_runs_count = serializers.SerializerMethodField(
        help_text="Quantidade de execuções neste ambiente"
    )

    class Meta(BaseSerializer.Meta):
        model = Environment
        fields = [
            "id",
            "project",
            "project_name",
            "base_url",
            "env_type",
            "env_type_display",
            "is_active",
            "test_runs_count",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
        ]

    @extend_schema_field(serializers.IntegerField())
    def get_test_runs_count(self, obj) -> int:
        if hasattr(obj, "_test_runs_count"):
            return obj._test_runs_count
        return obj.test_runs.count()

    def validate(self, attrs):
        """
        Valida unicidade de env_type por projeto.
        Funciona tanto em criação (POST) quanto em atualização (PATCH/PUT).
        """
        project = attrs.get("project", getattr(self.instance, "project", None))
        env_type = attrs.get("env_type", getattr(self.instance, "env_type", None))

        if project and env_type:
            qs = Environment.objects.filter(
                project=project,
                env_type=env_type,
                is_active=True,
            )
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"env_type": "Já existe um ambiente deste tipo neste projeto."}
                )

        return attrs
