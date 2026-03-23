# Garante que o app Celery é carregado quando o Django inicializa.
# Sem isso, as tasks não são registradas corretamente ao subir o servidor.
from .celery import app as celery_app

__all__ = ("celery_app",)
