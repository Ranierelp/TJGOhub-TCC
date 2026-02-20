from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from apps.commons.api.v1.serializers import BaseSerializer
from apps.projects.models import Project


class ProjectListSerializer(BaseSerializer):
    """
    Serializer compacto para listagens.

    Utilizado no action `list` e como nested read-only em outros serializers
    (ex: EnvironmentSerializer, TestRunSerializer).

    Inclui contadores via annotation do viewset para evitar N+1 queries.
    """

    slug = serializers.SlugField(read_only=True)

    environments_count = serializers.SerializerMethodField(
        help_text="Quantidade de ambientes ativos do projeto"
    )
    test_cases_count = serializers.SerializerMethodField(
        help_text="Quantidade de casos de teste ativos do projeto"
    )

    class Meta(BaseSerializer.Meta):
        model = Project
        fields = [
            "id",
            "name",
            "slug",
            "is_active",
            "environments_count",
            "test_cases_count",
            "created_at",
        ]

    @extend_schema_field(serializers.IntegerField())
    def get_environments_count(self, obj) -> int:
        # Aproveita annotation injetada pelo viewset (zero queries extras)
        if hasattr(obj, "_environments_count"):
            return obj._environments_count
        return obj.environments.count()

    @extend_schema_field(serializers.IntegerField())
    def get_test_cases_count(self, obj) -> int:
        if hasattr(obj, "_test_cases_count"):
            return obj._test_cases_count
        return obj.test_cases.count()


class ProjectSerializer(BaseSerializer):
    """
    Serializer completo para criação, edição e detalhe de projeto.

    Campos read-only automáticos via BaseSerializer:
        created_at, updated_at, created_by, updated_by, is_active

    O slug é gerado automaticamente pelo model.save() — nunca deve ser
    enviado pelo cliente.
    """
    slug = serializers.SlugField(read_only=True)

    environments_count = serializers.SerializerMethodField(
        help_text="Quantidade de ambientes ativos"
    )
    test_cases_count = serializers.SerializerMethodField(
        help_text="Quantidade de casos de teste ativos"
    )
    test_runs_count = serializers.SerializerMethodField(
        help_text="Quantidade total de execuções"
    )
    # Exibe o nome do criador diretamente, sem nested object
    created_by_name = serializers.SerializerMethodField(
        help_text="Nome do usuário que criou o projeto"
    )

    class Meta(BaseSerializer.Meta):
        model = Project
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "is_active",
            "environments_count",
            "test_cases_count",
            "test_runs_count",
            "created_at",
            "created_by",
            "created_by_name",
            "updated_at",
            "updated_by",
        ]
        # Campos que nunca devem ser enviados pelo cliente
        read_only_fields = [
            "id",
            "slug",
            "is_active",
            "environments_count",
            "test_cases_count",
            "test_runs_count",
            "created_at",
            "created_by",
            "created_by_name",
            "updated_at",
            "updated_by",
        ]

    @extend_schema_field(serializers.IntegerField())
    def get_environments_count(self, obj) -> int:
        if hasattr(obj, "_environments_count"):
            return obj._environments_count
        return obj.environments.count()

    @extend_schema_field(serializers.IntegerField())
    def get_test_cases_count(self, obj) -> int:
        if hasattr(obj, "_test_cases_count"):
            return obj._test_cases_count
        return obj.test_cases.count()

    @extend_schema_field(serializers.IntegerField())
    def get_test_runs_count(self, obj) -> int:
        if hasattr(obj, "_test_runs_count"):
            return obj._test_runs_count
        return obj.test_runs.count()

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_created_by_name(self, obj) -> str | None:
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return None

    def validate_name(self, value):
        """
        Valida unicidade de nome (case-insensitive) entre projetos ativos.
        Exclui o próprio objeto em caso de atualização (PATCH/PUT).
        """
        qs = Project.objects.filter(name__iexact=value, is_active=True)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "Já existe um projeto ativo com este nome."
            )
        return value
