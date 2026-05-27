"""
Monta a timeline de edições de um TestCase a partir das shadow tables criadas
pelo django-simple-history (no TestCase e no TestCaseAttachment).

Saída: lista de "entries" cronológicas (mais recente primeiro), prontas pra
serialização. Cada entry tem um `kind` ("edit", "create", "attachment_added",
"attachment_removed", "attachment_updated") e os dados específicos pra UI.
"""

from typing import Iterable

from apps.cases.models import TestCase, TestCaseAttachment


# ─────────────────────────────────────────────────────────────────────────────
# Labels PT-BR — quando adicionar campo novo ao TestCase que precise aparecer
# na timeline, lembrar de adicionar aqui também. Sem entrada o campo é
# ignorado (fica fora da timeline mesmo que mude).
# ─────────────────────────────────────────────────────────────────────────────

FIELD_LABELS = {
    "title":            "Título",
    "case_id":          "ID do caso",
    "status":           "Status",
    "priority":         "Prioridade",
    "module":           "Módulo",
    "assigned_to":      "Responsável",
    # "tags" é tratado SEPARADAMENTE em _tags_changes (M2M tem shape diff:
    # added/removed em vez de from/to). Não pode estar aqui senão geramos
    # duas entries com field="tags" e o front quebra ao ler `added` undefined.
    "objective":        "Objetivo",
    "preconditions":    "Pré-condições",
    "postconditions":   "Pós-condições",
    "expected_result":  "Resultado esperado",
    "observations":     "Observações",
    "playwright_id":    "Playwright ID",
    "test_title":       "Título no Playwright",
    "project":          "Projeto",
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de display — converte valores brutos pra texto humano
# ─────────────────────────────────────────────────────────────────────────────

STATUS_DISPLAY = {
    "DRAFT":      "Rascunho",
    "ACTIVE":     "Ativo",
    "DEPRECATED": "Depreciado",
}

PRIORITY_DISPLAY = {
    "CRITICAL": "Crítica",
    "HIGH":     "Alta",
    "MEDIUM":   "Média",
    "LOW":      "Baixa",
}


def _display_value(field_name: str, value):
    """Traduz valor bruto para o que o usuário vê na UI."""
    if value is None or value == "":
        return None
    if field_name == "status":
        return STATUS_DISPLAY.get(value, value)
    if field_name == "priority":
        return PRIORITY_DISPLAY.get(value, value)
    # FK: o simple-history devolve o pkid; precisamos buscar o nome.
    if field_name == "assigned_to":
        from apps.users.models import User
        user = User.objects.filter(pkid=value).first()
        return user.get_full_name() if user else None
    if field_name == "project":
        from apps.projects.models import Project
        proj = Project.objects.filter(pkid=value).first()
        return proj.name if proj else None
    return value


def _user_payload(history_user):
    """Monta o objeto do autor (id UUID, nome, iniciais) ou None."""
    if not history_user:
        return None
    full = history_user.get_full_name() or history_user.email
    first = (history_user.first_name or "")[:1].upper()
    last = (history_user.last_name or "")[:1].upper()
    initials = (first + last) or full[:2].upper()
    return {
        "id":       str(history_user.id),
        "name":     full,
        "initials": initials,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Construção da timeline
# ─────────────────────────────────────────────────────────────────────────────

def _diff_changes(current, previous) -> list[dict]:
    """
    Compara dois snapshots usando diff_against do simple-history.
    Retorna só os campos que estão em FIELD_LABELS (ignora ruído).
    """
    diff = current.diff_against(previous)
    changes = []
    for change in diff.changes:
        label = FIELD_LABELS.get(change.field)
        if label is None:
            continue  # campo fora do escopo — ignora
        changes.append({
            "field": change.field,
            "label": label,
            "from":  _display_value(change.field, change.old),
            "to":    _display_value(change.field, change.new),
        })
    return changes


def _tags_changes(current, previous) -> list[dict]:
    """
    M2M de tags vem como lista de IDs em `current.tags.all()`. Calcula
    adições/remoções comparando os dois snapshots e devolve uma única entry
    "tags" no formato { added: [...], removed: [...] }.
    """
    cur_ids = set(t.tag_id for t in current.tags.all())
    prev_ids = set(t.tag_id for t in previous.tags.all()) if previous else set()
    added_ids = cur_ids - prev_ids
    removed_ids = prev_ids - cur_ids

    if not added_ids and not removed_ids:
        return []

    from apps.tags.models import Tag
    tags_map = {
        t.pk: t.name
        for t in Tag.objects.filter(pk__in=added_ids | removed_ids)
    }
    return [{
        "field":   "tags",
        "label":   "Tags",
        "added":   [tags_map.get(i, "?") for i in added_ids],
        "removed": [tags_map.get(i, "?") for i in removed_ids],
    }]


def _testcase_entries(case: TestCase) -> Iterable[dict]:
    """Itera snapshots do TestCase e devolve entries 'edit' / 'create'."""
    snapshots = list(case.history.all().order_by("history_date"))
    if not snapshots:
        return

    # Primeiro snapshot é sempre o create.
    first = snapshots[0]
    yield {
        "kind":       "create",
        "edited_at":  first.history_date,
        "edited_by":  _user_payload(first.history_user),
        "changes":    [],
    }

    for i in range(1, len(snapshots)):
        current  = snapshots[i]
        previous = snapshots[i - 1]
        changes  = _diff_changes(current, previous) + _tags_changes(current, previous)
        if not changes:
            continue  # save sem mudança em campos auditados (ex.: só updated_at)
        yield {
            "kind":      "edit",
            "edited_at": current.history_date,
            "edited_by": _user_payload(current.history_user),
            "changes":   changes,
        }


def _attachment_entries(attachment: TestCaseAttachment) -> Iterable[dict]:
    """
    Snapshots de um attachment: o 1º vira 'attachment_added', os seguintes
    'attachment_updated', e se o último for tipo "-" (delete) vira 'removed'.
    """
    snapshots = list(attachment.history.all().order_by("history_date"))
    if not snapshots:
        return

    first = snapshots[0]
    yield {
        "kind":       "attachment_added",
        "edited_at":  first.history_date,
        "edited_by":  _user_payload(first.history_user),
        "attachment": {
            "id":    str(attachment.id),
            "title": first.title or f"Passo {first.order + 1}",
            "order": first.order,
        },
    }

    for i in range(1, len(snapshots)):
        snap = snapshots[i]
        # history_type: '+' (created), '~' (updated), '-' (deleted)
        if snap.history_type == "-":
            kind = "attachment_removed"
        else:
            kind = "attachment_updated"
        yield {
            "kind":       kind,
            "edited_at":  snap.history_date,
            "edited_by":  _user_payload(snap.history_user),
            "attachment": {
                "id":    str(attachment.id),
                "title": snap.title or f"Passo {snap.order + 1}",
                "order": snap.order,
            },
        }


def build_history_timeline(case: TestCase) -> list[dict]:
    """
    Monta a timeline completa de um TestCase mesclando snapshots do caso e
    dos anexos. Ordenada do mais recente pro mais antigo.
    """
    entries = list(_testcase_entries(case))

    # Anexos: incluímos também os já deletados (all_objects), pois mesmo
    # arquivado o histórico precisa contar "passo X foi adicionado".
    attachments = TestCaseAttachment.all_objects.filter(test_case=case)
    for att in attachments:
        entries.extend(_attachment_entries(att))

    entries.sort(key=lambda e: e["edited_at"], reverse=True)
    return entries