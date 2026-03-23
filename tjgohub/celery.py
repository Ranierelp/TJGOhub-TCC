"""
Configuração do Celery para o TJGOHub.

O Celery é o sistema de filas que permite executar tarefas pesadas
(como parsear relatórios de teste) em background, sem bloquear o servidor HTTP.

Como funciona:
    Django (producer) → Redis (fila/broker) → Celery Worker (consumer)

Para rodar o worker em desenvolvimento:
    celery -A tjgohub worker --loglevel=info
"""

import os

from celery import Celery

# Define qual arquivo de settings usar (mesmo que o manage.py)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tjgohub.settings.local")

# Cria a aplicação Celery com o nome do projeto
app = Celery("tjgohub")

# Lê as configurações do settings.py que começam com "CELERY_"
# Ex: CELERY_BROKER_URL no settings.py → broker_url no Celery
app.config_from_object("django.conf:settings", namespace="CELERY")

# Descobre automaticamente arquivos tasks.py em todos os apps do INSTALLED_APPS
# Ex: apps/runs/tasks.py → registra as tasks lá definidas
app.autodiscover_tasks()
