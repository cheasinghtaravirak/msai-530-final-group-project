import uuid

from django.db import models


class JobRun(models.Model):
    """One execution of a scheduled job (design doc §8.2).

    Manual runs ("Run now") are inserted as QUEUED by the API and picked up by the
    scheduler process within a few seconds, so only one process ever executes jobs.
    """

    class Status(models.TextChoices):
        QUEUED = "QUEUED"
        RUNNING = "RUNNING"
        DONE = "DONE"
        FAILED = "FAILED"

    class Trigger(models.TextChoices):
        SCHEDULE = "SCHEDULE"
        MANUAL = "MANUAL"

    run_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.CharField(max_length=50)
    trigger = models.CharField(max_length=10, choices=Trigger.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.QUEUED)
    requested_by = models.CharField(max_length=64, blank=True, default="")  # user_id for manual runs
    message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "job_run"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"], name="job_run_status_idx")]
