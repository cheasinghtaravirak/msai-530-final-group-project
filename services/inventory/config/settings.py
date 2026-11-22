from retail_common.settings_base import *  # noqa: F403

INSTALLED_APPS += ["refs"]  # noqa: F405
EVENT_HANDLER_MODULES = ["refs.handlers"]
