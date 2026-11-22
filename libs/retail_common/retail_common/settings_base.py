"""Base Django settings shared by every service. In a service's config/settings.py:

    from retail_common.settings_base import *  # noqa: F403
    INSTALLED_APPS += ["myapp"]
    EVENT_HANDLER_MODULES = ["myapp.handlers"]
"""

import base64
import os

import dj_database_url


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(int(default))).lower() in ("1", "true", "yes", "on")


SERVICE_NAME = os.environ.get("SERVICE_NAME", "unknown")
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-key")
DEBUG = env_bool("DEBUG", False)
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "retail_common",
]

MIDDLEWARE = [
    "retail_common.context.RequestIdMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
APPEND_SLASH = False  # API paths have no trailing slash: /branches, /orders/{id}

DATABASES = {
    "default": dj_database_url.parse(
        os.environ.get("DATABASE_URL", "postgres://localhost/unset"),
        conn_max_age=60,
        conn_health_checks=True,
    )
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Phnom_Penh"
USE_I18N = False
USE_TZ = True

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["retail_common.auth.JWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PAGINATION_CLASS": "retail_common.api.Pagination",
    "EXCEPTION_HANDLER": "retail_common.api.exception_handler",
    "UNAUTHENTICATED_USER": None,
    "COERCE_DECIMAL_TO_STRING": True,
}

# Messaging
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
EVENT_HANDLER_MODULES: list[str] = []  # modules that register @handles functions

# Auth
JWT_PUBLIC_KEY = base64.b64decode(os.environ.get("JWT_PUBLIC_KEY_B64", "")).decode()
SERVICE_TOKEN = os.environ.get("SERVICE_TOKEN", "")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"request_id": {"()": "retail_common.context.RequestIdFilter"}},
    "formatters": {
        "standard": {
            "format": f"%(asctime)s %(levelname)s {SERVICE_NAME} [%(name)s] rid=%(request_id)s %(message)s",
        }
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "filters": ["request_id"], "formatter": "standard"}
    },
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
    "loggers": {"django.db.backends": {"level": "WARNING"}},
}
