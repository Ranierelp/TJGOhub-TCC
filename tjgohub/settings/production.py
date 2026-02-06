from .base import *
from .base import env

DEBUG = False

ALLOWED_HOSTS = ["*"]

INTERNAL_IPS = [
    "127.0.0.1",
]

USE_X_FORWARDED_HOST = True

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

USE_S3 = env.bool("USE_S3", False)

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

LOG_FILE = "/production.log"

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

