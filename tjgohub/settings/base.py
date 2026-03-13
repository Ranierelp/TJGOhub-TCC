import os
from datetime import timedelta
from pathlib import Path

import environ
from corsheaders.defaults import default_headers
from django.utils.translation import gettext_lazy as _

env = environ.Env()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
APPS_DIR = ROOT_DIR / "apps"

# Take environment variables from .env file
environ.Env.read_env(os.path.join(BASE_DIR, "../.envs/.local/.django"))

SECRET_KEY = env("DJANGO_SECRET_KEY")

DEBUG = env.bool("DJANGO_DEBUG", False)

ALLOWED_HOSTS = ["*"]

BASE_URL = env("BASE_URL")

LOCAL_APPS = [
    "apps.users",
    "apps.commons",
    "apps.honeypot",
    "apps.artifacts",
    "apps.cases",
    "apps.environments",
    "apps.metrics",
    "apps.projects",
    "apps.results",
    "apps.runs",
    "apps.tags",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework.authtoken",
    "drf_spectacular",
    "corsheaders",
    "django_filters",
    "tinymce",
    "health_check",
    # Email
    "django_ses",
    # Admin
    "admin_interface",
    "colorfield",
    "django_admin_inline_paginator",
    # Import/Export
    "import_export",
    # Authentication
    "rest_framework_simplejwt",
    # Others
    "django_extensions",
    "django_crontab",
]

HEALTH_CHECK_APPS = [
    "health_check.db",
    "health_check.cache",
    "health_check.storage",
    "health_check.contrib.migrations",
    "health_check.contrib.psutil",
    "health_check.contrib.redis"
]

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

INSTALLED_APPS = LOCAL_APPS + THIRD_PARTY_APPS + DJANGO_APPS + HEALTH_CHECK_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.locale.LocaleMiddleware",
]

ROOT_URLCONF = "tjgohub.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [str(APPS_DIR / "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "tjgohub.wsgi.application"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
    "TEST_REQUEST_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "EXCEPTION_HANDLER": "apps.commons.api.v1.exceptions.exception_handler",
    "NON_FIELD_ERRORS_KEY": "error",
    "PAGE_SIZE": 10,
    "DATE_INPUT_FORMATS": ("%d/%m/%Y",),
    "COERCE_DECIMAL_TO_STRING": False,
}

VERSION_FILE = ROOT_DIR / "VERSION"

try:
    with open(VERSION_FILE) as f:
        API_VERSION = f.read().strip()
except FileNotFoundError:
    API_VERSION = "1.0.0"

SPECTACULAR_SETTINGS = {
    "TITLE": "TJGOhub API",
    "DESCRIPTION": "API docs and endpoints for TJGOhub API.",
    "VERSION": API_VERSION,
    "DISABLE_WARN_ON_IGNORED_VIEWS": True
}

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["ATOMIC_REQUESTS"] = True
DATABASES["default"]["ENGINE"] = "django.db.backends.postgresql"

# Schema específico para isolamento de dados entre diferentes APIs
DATABASE_SCHEMA = env("POSTGRES_SCHEMA", default="public")  # type: ignore
DATABASES["default"]["OPTIONS"] = {
    "options": f"-c search_path={DATABASE_SCHEMA},public"
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
)

AUTH_USER_MODEL = "users.User"

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Permitir métodos específicos
CORS_ALLOW_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]

CORS_URLS_REGEX = r"^(/api/v1/.*|/media/.*|/api/.*$)$"

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://172.19.0.3",  # Docker
]

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://localhost:\d+$",
    r"^https://\w+\.tjgohub\.com\.br$",
    r"^https://\w+\.tjgohub\.com$",
    r"^https://[a-zA-Z0-9-]+\.tjgohub\.com(:\d+)?$",
    r"^http://172\.\d+\.\d+\.\d+(:\d+)?$",  # Permite qualquer IP do Docker
]

CORS_ALLOW_HEADERS = list(default_headers) + [
    "x-msw-request-id",
    "authorization",
    "content-type",
    "x-requested-with",
]

CORS_EXPOSE_HEADERS = ["Content-Type", "X-CSRFToken"]

CSRF_TRUSTED_ORIGINS = [
    "https://*.ngrok-free.app",
    "https://*.tjgohub.com.br",
    "https://*.tjgohub.com",
    "https://*.tjgohub.com:8000",
]

LANGUAGES = (("pt-br", _("Português")), ("en", _("English")))

LANGUAGE_CODE = "pt-br"

TIME_ZONE = "America/Sao_Paulo"

USE_TZ = True

USE_I18N = True

SITE_ID = 1

ADMIN_URL = "secret/"

# For report CRITICAL errors
ADMINS = (
    ("Raniere", "luiz.raniere@discente.ufg.br"),
)

MANAGERS = ADMINS

LOCALE_PATHS = (os.path.join(BASE_DIR, "locale"),)

# S3 Configs
USE_S3 = env("USE_S3", cast=bool)

if USE_S3:
    # AWS settings
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_CUSTOM_DOMAIN = f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"
    AWS_REGION = env("AWS_REGION")

    # S3 public media settings
    PUBLIC_MEDIA_LOCATION = "media"
    MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/{PUBLIC_MEDIA_LOCATION}/"
    DEFAULT_FILE_STORAGE = "tjgohub.storage_backends.PublicMediaStorage"

    AWS_S3_FILE_OVERWRITE = False
    AWS_DEFAULT_ACL = None
    AWS_S3_OBJECT_PARAMETERS = {
        "CacheControl": "max-age=86400",
    }
else:
    MEDIA_URL = "/mediafiles/"
    MEDIA_ROOT = os.path.join(BASE_DIR, "mediafiles")

FILE_UPLOAD_PERMISSIONS = None

STATIC_URL = "/staticfiles/"
STATIC_ROOT = "/data/tjgohub/staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

PROJECT_TITLE = "TJGOhub API"

SITE_URL = env("SITE_URL")
SITE_NAME = "TJGOhub API"

# Admin
X_FRAME_OPTIONS = "SAMEORIGIN"
SILENCED_SYSTEM_CHECKS = ["security.W019"]

# Email

EMAIL_HOST_USER = env("DEFAULT_FROM_EMAIL", default="mailhog")
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

if DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = env("EMAIL_HOST")
    EMAIL_PORT = env("EMAIL_PORT")
    EMAIL_USE_SSL = True
    EMAIL_USE_TLS = False
    EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", cast=str)
else:
    EMAIL_BACKEND = "django_ses.SESBackend"

"""
Cache setting
Default cache timeout is one minute
"""
API_CACHE_TIMEOUT = env("API_CACHE_TIMEOUT", cast=int, default=3600)  # Tempo de expiração padrão de 1h

EMAIL_SUBJECT_PREFIX = f"[{SITE_NAME}]"

FIXTURE_DIRS = [
    os.path.join(BASE_DIR, "fixtures"),
]

# Authentication
SIMPLE_JWT = {
    "AUTH_HEADER_TYPES": (
        "Bearer",
    ),
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=24),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": False,

    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "VERIFYING_KEY": None,
    "AUDIENCE": None,
    "ISSUER": None,
    "JWK_URL": None,
    "LEEWAY": 0,

    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "USER_AUTHENTICATION_RULE": "rest_framework_simplejwt.authentication.default_user_authentication_rule",

    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "TOKEN_USER_CLASS": "rest_framework_simplejwt.models.TokenUser",

    "JTI_CLAIM": "jti",
}

EMAIL_TMP_DIR = f"{APPS_DIR}/commons/templates/emails/tmp/"

HONEYPOT_URL = "/admin"

CRONJOBS = [
    # ("*/3 * * * *", "apps.app_name.utils.file.function"),
]

DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000
DATA_UPLOAD_MAX_NUMBER_FILES = 1000
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

DEFAULT_TIMEOUT = env("DEFAULT_TIMEOUT", cast=int)

REDIS_URL = env("CACHE_HOST")
