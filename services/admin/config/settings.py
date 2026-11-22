import base64
import os

from retail_common.settings_base import *  # noqa: F403

INSTALLED_APPS += ["accounts"]  # noqa: F405
EVENT_HANDLER_MODULES = []  # Admin publishes only

# Only the admin service holds the private key.
JWT_PRIVATE_KEY = base64.b64decode(os.environ.get("JWT_PRIVATE_KEY_B64", "")).decode()
JWT_TTL_SECONDS = 8 * 60 * 60

BOOTSTRAP_ADMIN_EMAIL = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "hq@demo.local")
BOOTSTRAP_ADMIN_PASSWORD = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "demo1234")
