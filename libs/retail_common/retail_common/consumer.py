"""Idempotent Kafka consumer (design doc §5, §6.4, §11.3).

Register handlers with @handles("event.type"). The worker subscribes to every topic that
has a handler. For each message:

1. one DB transaction: insert into processed_event (skip if already there) + run the handler
2. commit the Kafka offset only after that transaction commits
3. if the handler keeps failing (3 attempts), send the message to <topic>.dlq and move on

Database outages are not the event's fault: those are retried until the DB is back, and
never sent to the DLQ.
"""

import json
import logging
import time
from collections.abc import Callable
from typing import Any

from django.conf import settings
from django.db import InterfaceError, OperationalError, close_old_connections, transaction

from .models import ProcessedEvent
from .topics import dlq_name, topic_for

log = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any]], None]
HANDLERS: dict[str, Handler] = {}


def handles(*event_types: str) -> Callable[[Handler], Handler]:
    """Register a function as the handler for one or more event types.

    The handler receives the whole envelope; business fields are in envelope["payload"].
    It runs inside a transaction, so it must not call external services.
    """

    def decorator(fn: Handler) -> Handler:
        for event_type in event_types:
            topic_for(event_type)  # fail fast on typos
            if event_type in HANDLERS and HANDLERS[event_type] is not fn:
                raise ValueError(f"Two handlers registered for {event_type}")
            HANDLERS[event_type] = fn
        return fn

    return decorator


def apply_event(envelope: dict[str, Any]) -> bool:
    """Apply one event exactly once. Returns False if skipped (duplicate or no handler)."""
    handler = HANDLERS.get(envelope.get("event_type"))
    if handler is None:
        return False
    with transaction.atomic():
        _, created = ProcessedEvent.objects.get_or_create(
            event_id=envelope["event_id"],
            defaults={"event_type": envelope["event_type"]},
        )
        if not created:
            log.info("Skipping duplicate %s %s", envelope["event_type"], envelope["event_id"])
            return False
        handler(envelope)
    return True


def subscribed_topics() -> list[str]:
    return sorted({topic_for(event_type).name for event_type in HANDLERS})


class EventConsumer:
    def __init__(self, consumer, dlq_producer, max_attempts: int = 3):
        self.consumer = consumer
        self.dlq_producer = dlq_producer
        self.max_attempts = max_attempts

    def subscribe(self) -> list[str]:
        topics = subscribed_topics()
        self.consumer.subscribe(topics)
        return topics

    def poll_once(self, timeout: float = 1.0) -> bool:
        msg = self.consumer.poll(timeout)
        if msg is None:
            return False
        if msg.error():
            log.warning("Kafka error: %s", msg.error())
            return False
        self._handle(msg)
        self.consumer.commit(message=msg, asynchronous=False)
        return True

    def _handle(self, msg) -> None:
        if msg.value() is None:
            # Tombstone: how a compacted topic deletes a key. Nothing to apply.
            log.info("Skipping tombstone on %s key=%s", msg.topic(), msg.key())
            return
        try:
            envelope = json.loads(msg.value())
            envelope["event_id"], envelope["event_type"]  # noqa: B018 - required fields
        except (ValueError, TypeError, KeyError) as exc:
            self._to_dlq(msg, f"Invalid envelope: {exc!r}")
            return

        attempt = 0
        while True:
            attempt += 1
            try:
                close_old_connections()
                applied = apply_event(envelope)
                if applied:
                    log.info("Applied %s %s", envelope["event_type"], envelope["event_id"])
                return
            except (OperationalError, InterfaceError) as exc:
                # Database unavailable: wait and retry the same event, never DLQ it.
                log.warning("Database unavailable, retrying %s: %s", envelope["event_id"], exc)
                close_old_connections()
                attempt = 0
                time.sleep(5)
            except Exception as exc:
                log.exception("Handler failed for %s (attempt %d)", envelope.get("event_id"), attempt)
                if attempt >= self.max_attempts:
                    self._to_dlq(msg, repr(exc))
                    return
                time.sleep(attempt)

    def _to_dlq(self, msg, error: str) -> None:
        headers = list(msg.headers() or []) + [
            ("dlq_error", error[:2000].encode()),
            ("dlq_source_topic", msg.topic().encode()),
            ("dlq_source_partition", str(msg.partition()).encode()),
            ("dlq_source_offset", str(msg.offset()).encode()),
            ("dlq_consumer_group", settings.SERVICE_NAME.encode()),
        ]
        self.dlq_producer.produce(dlq_name(msg.topic()), key=msg.key(), value=msg.value(), headers=headers)
        if self.dlq_producer.flush(10):
            raise RuntimeError("Could not write to the DLQ")
        log.error("Sent message to %s: %s", dlq_name(msg.topic()), error)
