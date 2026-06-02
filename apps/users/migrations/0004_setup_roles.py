"""
Data migration: cria os 3 grupos de perfil (Admin, QA, Visualizador) e
atribui as permissões nativas do Django apropriadas a cada um.

Por que data migration e não código de runtime?
- Idempotente (rodar 2x não duplica nada — get_or_create + set()).
- Versionado junto do schema — se você clonar o repo e rodar `migrate`,
  os grupos vêm prontos.
- Reversível (`reverse_code` apaga os grupos sem afetar usuários).

Observações:
1. Usamos `apps.get_model("auth", "Group")` em vez de import direto, porque
   dentro da migration o ORM precisa da versão histórica do model (o atual
   pode estar diferente).
2. `create_permissions` é chamado manualmente: numa DB nova as permissions
   só seriam criadas no signal post_migrate (após TODAS as migrations),
   então sem essa chamada o filter abaixo voltaria vazio.
"""

from django.db import migrations


# ─────────────────────────────────────────────────────────────────────────────
# Mapas declarativos — fica fácil ler e ajustar depois.
# Chave = app_label do Django; valor = lista de model_name em lowercase
# (que é como o Django nomeia os codenames das permissions: view_<modelname>).
# ─────────────────────────────────────────────────────────────────────────────

APP_MODELS = {
    "cases":        ["testcase", "testcaseattachment"],
    "projects":     ["project"],
    "runs":         ["testrun"],
    "results":      ["testresult"],
    "environments": ["environment"],
    "kanban":       ["kanbancolumn"],
    "tags":         ["tag"],
}

# QA: edita o domínio de testes inteiro, MAS não deleta projeto (regra do plano).
QA_PERMS = {
    "cases":        ["view", "add", "change", "delete"],
    "projects":     ["view", "add", "change"],          # sem delete
    "runs":         ["view", "add", "change", "delete"],
    "results":      ["view", "add", "change"],
    "environments": ["view", "add", "change", "delete"],
    "kanban":       ["view", "add", "change", "delete"],
    "tags":         ["view", "add", "change", "delete"],
}

# Visualizador: read-only puro em tudo.
VIEWER_PERMS = {app: ["view"] for app in APP_MODELS}


def _codenames(perms_map):
    """Expande {app: [actions]} → lista de codenames ('action_modelname')."""
    out = []
    for app_label, actions in perms_map.items():
        for model_name in APP_MODELS[app_label]:
            for action in actions:
                out.append(f"{action}_{model_name}")
    return out


def setup_roles(apps, schema_editor):
    # ── Força criação das Permission antes de atribuir ──────────────────────
    # Numa DB recém-criada o signal post_migrate ainda não rodou, então
    # as Permissions não existem. Disparamos create_permissions manualmente
    # pra cada app, garantindo que o filter abaixo encontre o que precisa.
    from django.apps import apps as django_apps
    from django.contrib.auth.management import create_permissions

    for app_config in django_apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    # ── Admin: todas as permissões dos apps do projeto (inclui users) ───────
    admin_group, _ = Group.objects.get_or_create(name="Admin")
    all_app_labels = list(APP_MODELS.keys()) + ["users"]
    admin_perms = Permission.objects.filter(content_type__app_label__in=all_app_labels)
    admin_group.permissions.set(admin_perms)

    # ── QA: permissões mapeadas (sem delete em projects, sem nada em users)
    qa_group, _ = Group.objects.get_or_create(name="QA")
    qa_perms = Permission.objects.filter(codename__in=_codenames(QA_PERMS))
    qa_group.permissions.set(qa_perms)

    # ── Visualizador: só view_* ─────────────────────────────────────────────
    viewer_group, _ = Group.objects.get_or_create(name="Visualizador")
    viewer_perms = Permission.objects.filter(codename__in=_codenames(VIEWER_PERMS))
    viewer_group.permissions.set(viewer_perms)


def remove_roles(apps, schema_editor):
    """Reverso: apaga os 3 grupos. Não toca em usuários."""
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=["Admin", "QA", "Visualizador"]).delete()


class Migration(migrations.Migration):
    # Dependemos das migrations mais recentes dos apps cujas permissions
    # vamos atribuir — sem isso o ContentType pode não existir ainda.
    dependencies = [
        ("users",        "0003_alter_user_is_active"),
        ("cases",        "0005_historicaltestcase_historicaltestcase_tags_and_more"),
        ("projects",     "0002_alter_project_slug"),
        ("runs",         "0001_initial"),
        ("results",      "0003_testresult_title"),
        ("environments", "0002_alter_environment_options_and_more"),
        ("kanban",       "0001_initial"),
        ("tags",         "0001_initial"),
    ]

    operations = [
        migrations.RunPython(setup_roles, remove_roles),
    ]