import os

from retail_common.settings_base import *  # noqa: F403

INSTALLED_APPS += ["reporting", "forecasting", "replenishment", "insights", "jobs"]  # noqa: F405
EVENT_HANDLER_MODULES = ["reporting.handlers"]

# Local LLM (design doc §9.4)
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "ollama")  # "ollama" or "fake"
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:12b")
