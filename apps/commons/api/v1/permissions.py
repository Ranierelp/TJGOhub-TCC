"""
Classes de permissão compartilhadas entre os viewsets do projeto.

ActionPermissions é o coração do sistema de perfis:
- Força view_<model> em GET (o default do DRF deixa GET aberto).
- Mapeia @action customs (start/move/archive/etc.) pra view/add/change/delete
  via uma tabela central — sem isso, todas as actions POST seriam tratadas
  como "add" pelo DRF, mesmo quando semanticamente são "change".
"""

from rest_framework import permissions
from rest_framework.permissions import DjangoModelPermissions


# ─────────────────────────────────────────────────────────────────────────────
# IsAdmin — permission "grossa" pra telas inteiras administrativas
# ─────────────────────────────────────────────────────────────────────────────

class IsAdmin(permissions.BasePermission):
    """
    Libera o request se o usuário é superuser OU pertence ao grupo "Admin".

    Diferença vs ActionPermissions:
    - ActionPermissions pergunta "tem permission X pra esse model?".
      Bom pra CRUD granular (QA edita caso, Visualizador só lê, etc.).
    - IsAdmin pergunta "é admin?". Bom pra recursos administrativos onde
      a granularidade não importa (gerenciar usuários, editar grupos).

    Usado em UserViewSet e nos endpoints que alimentam a tela /dashboard/perfis/.
    """

    message = "Apenas administradores podem acessar este recurso."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return user.groups.filter(name="Admin").exists()


# ─────────────────────────────────────────────────────────────────────────────
# ActionPermissions — usada em todos os viewsets que herdam BaseModelApiViewSet
# ─────────────────────────────────────────────────────────────────────────────

class ActionPermissions(DjangoModelPermissions):
    """
    Estende DjangoModelPermissions com dois ajustes:

    1. perms_map: força view_<model> em GET/HEAD (default do DRF deixa vazio).
    2. action_to_required_perm: lookup por NOME da @action que sobrescreve
       o mapeamento por método HTTP. Ex.: a action `start` é POST mas é
       semanticamente uma edição — então exige change_testrun, não add_testrun.

    Quando criar action nova:
    - Se ela só faz GET e o nome remete a leitura → não precisa cadastrar
      (o perms_map já cobre).
    - Se ela muda estado mas usa POST → adicionar entrada apontando pra "change".
    - Se ela deleta algo → adicionar entrada apontando pra "delete".
    """

    # ── Mapeamento por método HTTP ──────────────────────────────────────────
    # Diferença do default do DRF: GET/HEAD agora exigem view_*.
    perms_map = {
        "GET":     ["%(app_label)s.view_%(model_name)s"],
        "HEAD":    ["%(app_label)s.view_%(model_name)s"],
        "OPTIONS": [],
        "POST":    ["%(app_label)s.add_%(model_name)s"],
        "PUT":     ["%(app_label)s.change_%(model_name)s"],
        "PATCH":   ["%(app_label)s.change_%(model_name)s"],
        "DELETE":  ["%(app_label)s.delete_%(model_name)s"],
    }

    # ── Mapeamento por NOME de @action custom ───────────────────────────────
    # Valor = "view" | "add" | "change" | "delete" — vira o codename apropriado
    # no model do viewset. Esta tabela é o ponto único de manutenção: quando
    # um dev criar @action nova num viewset, registra aqui.
    action_to_required_perm = {
        # ── Cases ───────────────────────────────────────────────────────
        "by_project":         "view",
        "history":            "view",
        "change_status":      "change",
        "activate":           "change",
        "move":               "change",
        "remove_attachment":  "change",   # edita o caso (anexo é sub-objeto)
        "update_attachment":  "change",
        "add_attachment":     "change",
        # ── Projects ────────────────────────────────────────────────────
        "mine":               "view",
        "archive":            "delete",   # archive = soft delete
        "hard_delete":        "delete",   # + check is_superuser no viewset
        # ── Runs ────────────────────────────────────────────────────────
        "start":              "change",
        "complete":           "change",
        "fail":               "change",
        "cancel":             "change",
        "recalculate_metrics": "change",
        "by_environment":     "view",
        "results":            "view",
        # ── Results ─────────────────────────────────────────────────────
        "mark_as_flaky":      "change",
        # ── Kanban ──────────────────────────────────────────────────────
        "reorder":            "change",
        # Obs.: actions que apenas LISTAM (GET) já caem no perms_map e
        # não precisam estar aqui — manter aqui só por clareza/debug.
    }

    def has_permission(self, request, view):
        # Igual ao super(), mas com a lookup do action_to_required_perm na frente.
        if getattr(view, "_ignore_model_permissions", False):
            return True
        if not request.user or (
            not request.user.is_authenticated and self.authenticated_users_only
        ):
            return False

        queryset = self._queryset(view)
        model_cls = queryset.model

        # Se a action atual tem mapeamento explícito, usa ele e ignora o método HTTP.
        action_name = getattr(view, "action", None)
        custom = self.action_to_required_perm.get(action_name)
        if custom:
            perm = f"{model_cls._meta.app_label}.{custom}_{model_cls._meta.model_name}"
            return request.user.has_perm(perm)

        # Caso default — usa perms_map (que já fortalecemos com view em GET).
        perms = self.get_required_permissions(request.method, model_cls)
        return request.user.has_perms(perms)


# ─────────────────────────────────────────────────────────────────────────────
# MineOrReadOnly — mantida intocada por compatibilidade. Não é usada pelos
# viewsets do domínio TJGOhub (é resto de outro projeto), mas alguns testes
# antigos podem referenciar. Será removida em cleanup futuro.
# ─────────────────────────────────────────────────────────────────────────────

class MineOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.user.is_superuser:
            return True

        if request.method in ["POST", "PATCH"]:
            if any(key in request.data and request.data[key] == str(request.user.id) for key in
                   ["created_by"]):
                return True
            try:
                instance = view.get_object()
                attributes = ["created_by"]
                if any(hasattr(instance, attr) and getattr(instance, attr) == request.user for attr in attributes):
                    return True
            except Exception:
                return False

        if request.method in permissions.SAFE_METHODS:
            return True

        return False

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True

        if request.method in permissions.SAFE_METHODS:
            return True

        if not request.user:
            return False

        attributes = ["created_by"]
        if any(hasattr(obj, attr) and getattr(obj, attr) == request.user for attr in attributes):
            return True

        return False