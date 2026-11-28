from retail_common.settings_base import *  # noqa: F403

INSTALLED_APPS += ["caches", "sales"]  # noqa: F405
EVENT_HANDLER_MODULES = []  # modules with @handles functions
