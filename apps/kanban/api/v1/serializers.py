import re

from rest_framework import serializers

from apps.commons.api.v1.serializers import BaseSerializer, PkToIdMixin
from apps.kanban.models import KanbanColumn
from apps.tags.api.v1.serializers import TagSerializer


class KanbanColumnSerializer(BaseSerializer):
    """
    Serializer para KanbanColumn.

    Herda de BaseSerializer pra converter automaticamente o FK `project`:
    aceita UUID na entrada e devolve UUID na saída (compatível com o que
    o frontend envia/espera). Sem isso, o campo usaria o pkid (int interno).
    """

    class Meta(BaseSerializer.Meta):
        model = KanbanColumn
        fields = [
            'id',
            'name',
            'color',
            'order',
            'project',
            'is_active',
            'created_at',
            'updated_at',
        ]

    def validate_color(self, value):
        """Garante que a cor está no formato #RRGGBB."""
        if not re.match(r'^#[0-9A-Fa-f]{6}$', value):
            raise serializers.ValidationError(
                "Cor deve estar no formato hexadecimal (#RRGGBB). Ex: #6366f1"
            )
        return value.lower()

    def validate_name(self, value):
        """Remove espaços extras do nome."""
        return value.strip()


class KanbanBoardCaseSerializer(PkToIdMixin, serializers.ModelSerializer):
    """
    Representação compacta de um TestCase dentro do board.
    Inclui apenas o necessário para renderizar o card no frontend.

    PkToIdMixin converte o FK `project` de pkid (int) para id (UUID) na saída,
    pra bater com o que o front espera (consistente com KanbanBoardColumnSerializer).
    """
    tags = TagSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    priority_display = serializers.CharField(source="get_priority_display", read_only=True)
    assigned_to_id = serializers.SerializerMethodField()
    assigned_to_name = serializers.SerializerMethodField()
    assigned_to_initials = serializers.SerializerMethodField()

    class Meta:
        from apps.cases.models import TestCase
        model = TestCase
        fields = [
            "id",
            "case_id",
            "title",
            "status",
            "status_display",
            "project",
            "project_name",
            "tags",
            "board_position",
            "priority",
            "priority_display",
            "assigned_to_id",
            "assigned_to_name",
            "assigned_to_initials",
        ]

    def get_assigned_to_id(self, obj) -> str | None:
        return str(obj.assigned_to.id) if obj.assigned_to_id else None

    def get_assigned_to_name(self, obj) -> str | None:
        if not obj.assigned_to_id:
            return None
        return obj.assigned_to.get_full_name() or obj.assigned_to.email

    def get_assigned_to_initials(self, obj) -> str | None:
        if not obj.assigned_to_id:
            return None
        u = obj.assigned_to
        first = (u.first_name or "")[:1].upper()
        last = (u.last_name or "")[:1].upper()
        return (first + last) or u.email[:2].upper()


class KanbanBoardColumnSerializer(PkToIdMixin, serializers.ModelSerializer):
    """
    Coluna do board com seus casos aninhados, já ordenados por board_position.
    Usado exclusivamente no endpoint GET /kanban/board/.

    PkToIdMixin converte o output do FK `project` de pkid (int) para id (UUID),
    pra bater com o que o frontend espera (string | null).
    """
    cases = serializers.SerializerMethodField()
    cases_count = serializers.SerializerMethodField()

    class Meta:
        model = KanbanColumn
        fields = ["id", "name", "color", "order", "project", "cases", "cases_count"]

    def get_cases(self, column):
        """Retorna os casos ativos desta coluna ordenados por posição."""
        project_id = self.context.get("project_id")
        from apps.cases.models import TestCase
        qs = (
            TestCase.objects.filter(kanban_column=column)
            .select_related("project", "assigned_to")
            .prefetch_related("tags")
            .order_by("board_position")
        )
        if project_id:
            qs = qs.filter(project__id=project_id)
        return KanbanBoardCaseSerializer(qs, many=True).data

    def get_cases_count(self, column):
        cases = self.get_cases(column)
        return len(cases)


class KanbanColumnReorderSerializer(serializers.Serializer):
    """
    Serializer para o endpoint de reordenação bulk.

    Recebe uma lista de objetos: [{"id": "<uuid>", "order": <int>}, ...]
    """

    class ColumnOrderItem(serializers.Serializer):
        id = serializers.UUIDField()
        order = serializers.IntegerField(min_value=0)

    columns = ColumnOrderItem(many=True)
