from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from apps.tags.models import Tag


class TagSerializer(serializers.ModelSerializer):
    """
    Serializer único para Tag — usado tanto em lista quanto em detalhe.

    Tag não herda de BaseModel (sem soft delete, sem rastreabilidade completa),
    por isso usamos ModelSerializer diretamente em vez do BaseSerializer do projeto.

    Campos:
        id          → UUID, somente leitura
        name        → obrigatório, único (validado no serializer)
        color       → hex #RRGGBB, padrão #007bff
        description → opcional
        created_at  → somente leitura
        usage_count → calculado via annotation ou count()
    """

    usage_count = serializers.SerializerMethodField(
        help_text="Quantidade de casos de teste que usam esta tag"
    )

    class Meta:
        model = Tag
        fields = [
            "id",
            "name",
            "color",
            "description",
            "usage_count",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    @extend_schema_field(serializers.IntegerField())
    def get_usage_count(self, obj) -> int:
        # Aproveita annotation injetada pelo viewset quando disponível
        if hasattr(obj, "_usage_count"):
            return obj._usage_count
        return obj.test_cases.count()

    def validate_name(self, value):
        """Unicidade de nome case-insensitive."""
        qs = Tag.objects.filter(name__iexact=value.strip())
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "Já existe uma tag com este nome."
            )
        return value.strip()

    def validate_color(self, value):
        """Garante formato hex válido (#RRGGBB)."""
        import re
        if not re.match(r'^#[0-9A-Fa-f]{6}$', value):
            raise serializers.ValidationError(
                "Cor deve estar no formato hexadecimal (#RRGGBB). Ex: #007bff"
            )
        return value.lower()
