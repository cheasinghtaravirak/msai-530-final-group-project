"""The jobs Analytics runs (design doc §8.2). Each job returns a short message for job_run.

The real implementations arrive in Phases 3-4. Until then each job is a placeholder, so the
scheduler, the queue and the "Run now" buttons can be built and tested now.
"""

import logging
from collections.abc import Callable

log = logging.getLogger(__name__)


def reconcile() -> str:  # J1, 00:15
    return "placeholder: reconcile not implemented yet"


def day_close() -> str:  # J2
    return "placeholder: day_close not implemented yet"


def month_close() -> str:  # J6, 4th of the month
    return "placeholder: month_close not implemented yet"


def forecast() -> str:  # J3
    return "placeholder: forecast not implemented yet"


def replenishment() -> str:  # J5
    return "placeholder: replenishment not implemented yet"


def briefing() -> str:  # J7, LLM
    return "placeholder: briefing not implemented yet"


NIGHTLY_STEPS: list[tuple[str, Callable[[], str]]] = [
    ("day_close", day_close),
    ("forecast", forecast),
    ("replenishment", replenishment),
    ("briefing", briefing),  # last, so an LLM problem never blocks the others
]


def nightly() -> str:
    """J2 -> J3 -> J5 -> J7, stopping at the first failure (J4 anomalies are deferred)."""
    messages = []
    for name, fn in NIGHTLY_STEPS:
        log.info("Nightly step %s", name)
        messages.append(f"{name}: {fn()}")
    return "\n".join(messages)


JOBS: dict[str, Callable[[], str]] = {
    "reconcile": reconcile,
    "day_close": day_close,
    "month_close": month_close,
    "forecast": forecast,
    "replenishment": replenishment,
    "briefing": briefing,
    "nightly": nightly,
}
