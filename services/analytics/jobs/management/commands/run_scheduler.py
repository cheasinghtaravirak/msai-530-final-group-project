"""The analytics-scheduler process (APScheduler). Run exactly one of these.

    python manage.py run_scheduler
"""

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from django.conf import settings
from django.core.management.base import BaseCommand

from jobs.runner import run_queued, run_scheduled

log = logging.getLogger("jobs.scheduler")


class Command(BaseCommand):
    help = "Run the nightly analytics schedule and execute manually queued jobs"

    def handle(self, *args, **options):
        tz = settings.TIME_ZONE
        scheduler = BlockingScheduler(timezone=tz, job_defaults={"coalesce": True, "max_instances": 1})

        scheduler.add_job(run_scheduled, CronTrigger(hour=0, minute=15, timezone=tz), args=["reconcile"], id="J1")
        scheduler.add_job(run_scheduled, CronTrigger(hour=0, minute=30, timezone=tz), args=["nightly"], id="nightly")
        scheduler.add_job(
            run_scheduled, CronTrigger(day=4, hour=2, minute=0, timezone=tz), args=["month_close"], id="J6"
        )
        # "Run now" requests from the API.
        scheduler.add_job(run_queued, "interval", seconds=3, id="queued")

        log.info("Scheduler started (%s): J1 00:15, nightly 00:30, J6 4th 02:00, queue every 3 s", tz)
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            log.info("Scheduler stopped")
