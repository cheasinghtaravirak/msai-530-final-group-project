import logging

from django.db import close_old_connections, transaction
from django.utils import timezone

from .models import JobRun
from .registry import JOBS

log = logging.getLogger(__name__)


def execute(run: JobRun) -> JobRun:
    """Run a job and record the outcome on its JobRun row."""
    run.status = JobRun.Status.RUNNING
    run.started_at = timezone.now()
    run.save(update_fields=["status", "started_at"])
    log.info("Job %s started (%s, run %s)", run.job, run.trigger, run.run_id)
    try:
        run.message = JOBS[run.job]() or ""
        run.status = JobRun.Status.DONE
    except Exception as exc:  # noqa: BLE001 - record any failure on the run
        log.exception("Job %s failed", run.job)
        run.message = f"{exc.__class__.__name__}: {exc}"
        run.status = JobRun.Status.FAILED
    run.finished_at = timezone.now()
    run.save(update_fields=["status", "message", "finished_at"])
    log.info("Job %s finished: %s", run.job, run.status)
    return run


def run_scheduled(job: str) -> None:
    close_old_connections()
    execute(JobRun.objects.create(job=job, trigger=JobRun.Trigger.SCHEDULE))


def run_queued() -> None:
    """Pick up manual runs queued through the API, oldest first."""
    close_old_connections()
    while True:
        with transaction.atomic():
            run = (
                JobRun.objects.select_for_update(skip_locked=True)
                .filter(status=JobRun.Status.QUEUED)
                .order_by("created_at")
                .first()
            )
            if run is None:
                return
            run.status = JobRun.Status.RUNNING
            run.save(update_fields=["status"])
        execute(run)
