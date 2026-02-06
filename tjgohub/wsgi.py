import os

import environ
from django.core.wsgi import get_wsgi_application

env = environ.Env()

if env("DJANGO_DEBUG", cast=bool):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tjgohub.settings.local")
else:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tjgohub.settings.production")

os.environ.setdefault("SERVER_GATEWAY_INTERFACE", "WSGI")

application = get_wsgi_application()

