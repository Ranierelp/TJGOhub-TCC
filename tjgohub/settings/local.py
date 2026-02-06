from .base import *
from .base import env

DEBUG = True

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS += ["debug_toolbar"]

MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware"] + MIDDLEWARE

INTERNAL_IPS = [
    "127.0.0.1",
]

USE_S3 = env.bool("USE_S3", False)

if USE_S3:
    # AWS settings
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
    AWS_DEFAULT_ACL = None
    AWS_S3_CUSTOM_DOMAIN = f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"
    AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}
    AWS_REGION = env("AWS_REGION")

    # S3 public media settings
    PUBLIC_MEDIA_LOCATION = "media"
    MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/{PUBLIC_MEDIA_LOCATION}/"
    DEFAULT_FILE_STORAGE = "tjgohub.storage_backends.PublicMediaStorage"
else:
    MEDIA_URL = "/media/"

MEDIA_ROOT = os.path.join(BASE_DIR, "media")

if env("USE_CACHE", cast=bool):
    """
    Redis Cache
    """

    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": env("CACHE_HOST"),
            "TIMEOUT": 60,
        }
    }

"""
Logging
"""
LOG_ROOT = Path(__file__).resolve().parent.parent / "logs"

LOG_FILE = "/log.log"

LOG_PATH = f'{LOG_ROOT}{LOG_FILE}'

if not os.path.exists(LOG_ROOT):
    os.mkdir(LOG_ROOT)

# Create empty log file
if not os.path.exists(LOG_PATH):
    f = open(LOG_PATH, 'a').close()

LOGGING = {
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_PATH,
            "maxBytes": 1024 * 1024 * 5,  # 5MB
            "backupCount": 5,
            "formatter": "verbose",
        },
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": [
                "file",
            ],
            "level": "INFO",
            "propagate": True,
        },
    },
}

DEFAULT_EXCEPTION_REPORTER_FILTER = "tools.helpers.CustomExceptionFilter"

