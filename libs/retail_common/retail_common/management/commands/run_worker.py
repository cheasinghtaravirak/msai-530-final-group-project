"""Background worker: outbox relay + Kafka consumer in one loop.

    python manage.py run_worker              # relay, plus consumer if the service has handlers
    python manage.py run_worker --no-relay   # consumer only
"""

import importlib
import logging
import signal
import time

from confluent_kafka import Consumer, Producer
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import InterfaceError, OperationalError, close_old_connections

from retail_common.consumer import HANDLERS, EventConsumer
from retail_common.kafka import consumer_config, producer_config
from retail_common.relay import OutboxRelay

log = logging.getLogger("retail_common.worker")


class Command(BaseCommand):
    help = "Run the outbox relay and the Kafka event consumer"

    def add_arguments(self, parser):
        parser.add_argument("--no-relay", action="store_true", help="Do not publish the outbox")
        parser.add_argument("--no-consume", action="store_true", help="Do not consume events")

    def handle(self, *args, **options):
        for module in settings.EVENT_HANDLER_MODULES:
            importlib.import_module(module)

        stopping = False

        def stop(*_):
            nonlocal stopping
            stopping = True

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)

        producer = Producer(producer_config())
        relay = None if options["no_relay"] else OutboxRelay(producer)

        events = None
        if HANDLERS and not options["no_consume"]:
            events = EventConsumer(Consumer(consumer_config()), dlq_producer=producer)
            topics = events.subscribe()
            log.info("Consumer group %r subscribed to %s", settings.SERVICE_NAME, topics)
        log.info("Worker started (relay=%s, consumer=%s)", relay is not None, events is not None)

        try:
            while not stopping:
                close_old_connections()
                published = 0
                if relay is not None:
                    try:
                        published = relay.run_once()
                    except (OperationalError, InterfaceError) as exc:
                        log.warning("Database unavailable for relay: %s", exc)
                        time.sleep(2)
                    except Exception:  # noqa: BLE001 - keep the worker alive, retry next loop
                        log.exception("Relay failed; will retry")
                        time.sleep(2)

                if events is not None:
                    events.poll_once(timeout=0.2 if published else 1.0)
                elif not published:
                    time.sleep(0.5)
        finally:
            log.info("Worker stopping")
            if events is not None:
                events.consumer.close()
            producer.flush(5)
