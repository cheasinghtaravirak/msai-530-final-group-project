"""Outbox relay: publishes unsent outbox rows to Kafka, oldest first."""

import json
import logging

from django.db import transaction
from django.utils import timezone

from .models import Outbox

log = logging.getLogger(__name__)


class OutboxRelay:
    def __init__(self, producer, batch_size: int = 100, flush_timeout: float = 15.0):
        self.producer = producer
        self.batch_size = batch_size
        self.flush_timeout = flush_timeout

    def run_once(self) -> int:
        """Publish one batch. Returns the number of events published.

        If anything fails, the transaction rolls back and the rows are retried later. Some of
        them may already have reached Kafka; consumers drop those duplicates by event_id.
        """
        errors: list = []

        def on_delivery(err, _msg):
            if err is not None:
                errors.append(err)

        with transaction.atomic():
            rows = list(
                Outbox.objects.select_for_update(skip_locked=True)
                .filter(published_at__isnull=True)
                .order_by("created_at")[: self.batch_size]
            )
            if not rows:
                return 0

            for row in rows:
                self.producer.produce(
                    row.topic,
                    key=row.key.encode(),
                    value=json.dumps(row.envelope).encode(),
                    headers={"event_type": row.event_type, "event_id": str(row.event_id)},
                    on_delivery=on_delivery,
                )
            remaining = self.producer.flush(self.flush_timeout)
            if remaining or errors:
                raise RuntimeError(f"Kafka publish failed: {remaining} undelivered, errors={errors}")

            Outbox.objects.filter(pk__in=[r.pk for r in rows]).update(published_at=timezone.now())

        log.info("Published %d event(s)", len(rows))
        return len(rows)
