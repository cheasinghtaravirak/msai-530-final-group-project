import os

from retail_common.settings_base import *  # noqa: F403

INSTALLED_APPS += ["caches", "sales"]  # noqa: F405
EVENT_HANDLER_MODULES = ["caches.handlers"]

CATALOG_URL = os.environ.get("CATALOG_URL", "http://catalog:8000")
