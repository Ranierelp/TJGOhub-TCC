# apps/cases/api/v1/serializers.py

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from apps.commons.api.v1.serializers import BaseSerializer
from apps.cases.models import TestCase, TestCaseAttachment
from apps.tags.api.v1.serializers import TagSerializer


class TestCaseAttachmentSerializer(BaseSerializer):
    """
    Serializer para anexos de casos de teste.
    Usado como nested read-only no TestCaseSerializer.
    """

    class Meta(BaseSerializer.Meta):
        model = TestCaseAttachment
        fields = [
            "id",
            "title",
            "description",
            "attachment_type",
            "file",
            "order",
            "created_at",
        ]


class TestCaseListSerializer(BaseSerializer):
    """
    Serializer compacto para listagens.
    Inclui apenas os campos essenciais para identificação e triagem.
    """

    slug = serializers.SlugField(read_only=True)
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )
    tags = TagSerializer(many=True, read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta(BaseSerializer.Meta):
        model = TestCase
        fields = [
            "id",
            "project",
            "project_name",
            "case_id",
            "title",
            "slug",
            "status",
            "status_display",
            "module",
            "tags",
            "is_active",
            "created_at",
        ]


class TestCaseSerializer(BaseSerializer):
    """
    Serializer completo para criação, edição e detalhe de caso de teste.

    Campos write:
        project, case_id, title, status, module, objective, preconditions,
        postconditions, expected_result, observations, test_title,
        playwright_id, tags (lista de UUIDs)

    Campos read-only:
        slug (gerado pelo model), last_modified_by (preenchido pelo viewset),
        attachments (nested), status_display, project_name
        + todos os de rastreabilidade (BaseSerializer.__init__)
    """

    # Declarados explicitamente — não sobrescritos pelo BaseSerializer.__init__
    slug = serializers.SlugField(read_only=True)

    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )
    project_name = serializers.CharField(source="project.name", read_only=True)

    # Tags: leitura mostra objeto completo, escrita aceita lista de UUIDs
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        help_text="Lista de UUIDs das tags para associar ao caso de teste",
    )

    # last_modified_by é preenchido pelo viewset, nunca pelo cliente
    last_modified_by_name = serializers.SerializerMethodField()

    attachments = TestCaseAttachmentSerializer(many=True, read_only=True)
    attachments_count = serializers.SerializerMethodField()

    class Meta(BaseSerializer.Meta):
        model = TestCase
        fields = [
            "id",
            "project",
            "project_name",
            "case_id",
            "title",
            "slug",
            "status",
            "status_display",
            "module",
            # Documentação
            "objective",
            "preconditions",
            "postconditions",
            "expected_result",
            "observations",
            # Playwright
            "test_title",
            "playwright_id",
            # Tags
            "tags",
            "tag_ids",
            # Anexos
            "attachments",
            "attachments_count",
            # Rastreabilidade
            "is_active",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "last_modified_by",
            "last_modified_by_name",
        ]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_last_modified_by_name(self, obj) -> str | None:
        if obj.last_modified_by:
            return obj.last_modified_by.get_full_name() or obj.last_modified_by.email
        return None

    @extend_schema_field(serializers.IntegerField())
    def get_attachments_count(self, obj) -> int:
        if hasattr(obj, "_attachments_count"):
            return obj._attachments_count
        return obj.attachments.count()

    def validate_case_id(self, value):
        """Unicidade de case_id por projeto (case-insensitive)."""
        # Pega o projeto do body (criação) ou da instância (atualização)
        project = (
            self.initial_data.get("project")
            or getattr(self.instance, "project_id", None)
        )
        if project:
            from apps.cases.models import TestCase as TC
            qs = TC.objects.filter(
                project=project,
                case_id__iexact=value,
                is_active=True,
            )
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    "Já existe um caso de teste ativo com este ID neste projeto."
                )
        return value.upper()  # Normaliza para maiúsculas (TC-001)

    def create(self, validated_data):
        tag_ids = validated_data.pop("tag_ids", [])
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
