import json
import uuid
from types import SimpleNamespace

import pytest
from django.db import transaction

from retail_common import consumer
from retail_common.consumer import HANDLERS, EventConsumer, apply_event
from retail_common.context import JsonFormatter, reset_request_id, set_request_id
from retail_common.events import build_envelope, publish_event
from retail_common.models import Outbox, ProcessedEvent

pytestmark = pytest.mark.django_db

EVENT = "branch.upserted"
KEY = "BR-9903"


class Boom(Exception):
    pass


def fake_message(envelope):
    answers = {
        "value": json.dumps(envelope).encode(),
        "key": KEY.encode(),
        "topic": EVENT,
        "partition": 0,
        "offset": 7,
        "headers": [],
        "error": None,
    }
    return SimpleNamespace(**{name: (lambda answer=answer: answer) for name, answer in answers.items()})


class FakeKafka:
    def __init__(self, message=None):
        self.message = message
        self.produced = []
        self.committed = []

    def poll(self, timeout):
        return self.message

    def commit(self, message, asynchronous):
        self.committed.append(message)

    def produce(self, topic, key, value, headers):
        self.produced.append((topic, key, value, dict(headers)))

    def flush(self, timeout):
        return 0


def test_outbox_row_shares_the_fate_of_the_business_transaction():
    with pytest.raises(Boom), transaction.atomic():
        publish_event(EVENT, {"branch_id": KEY}, key=KEY)
        raise Boom
    assert not Outbox.objects.filter(key=KEY).exists()

    with transaction.atomic():
        publish_event(EVENT, {"branch_id": KEY}, key=KEY)
    assert Outbox.objects.get(key=KEY).envelope["payload"] == {"branch_id": KEY}


def test_publishing_outside_a_transaction_is_refused(monkeypatch):
    monkeypatch.setattr(transaction.get_connection(), "in_atomic_block", False)
    with pytest.raises(RuntimeError):
        publish_event(EVENT, {"branch_id": KEY}, key=KEY)


def test_consumer_applies_an_event_id_once(monkeypatch):
    seen = []
    monkeypatch.setitem(HANDLERS, EVENT, seen.append)
    envelope = build_envelope(EVENT, {"branch_id": KEY})

    assert apply_event(envelope) is True
    assert apply_event(envelope) is False
    assert len(seen) == 1


def test_failing_handler_goes_to_the_dlq_after_three_attempts(monkeypatch):
    attempts = []

    def handler(envelope):
        attempts.append(envelope["event_id"])
        raise Boom("bad event")

    monkeypatch.setitem(HANDLERS, EVENT, handler)
    monkeypatch.setattr(consumer.time, "sleep", lambda seconds: None)
    # The real one would drop the connection that holds this test's transaction.
    monkeypatch.setattr(consumer, "close_old_connections", lambda: None)
    envelope = build_envelope(EVENT, {"branch_id": KEY})
    message = fake_message(envelope)
    source, dlq = FakeKafka(message), FakeKafka()

    assert EventConsumer(source, dlq_producer=dlq).poll_once() is True

    assert len(attempts) == 3
    [(topic, key, value, headers)] = dlq.produced
    assert (topic, key, value) == (f"{EVENT}.dlq", KEY.encode(), message.value())
    assert headers["dlq_source_offset"] == b"7"
    assert b"bad event" in headers["dlq_error"]
    assert source.committed == [message], "the partition moves on past the poison message"
    assert not ProcessedEvent.objects.filter(event_id=envelope["event_id"]).exists()


def test_a_failing_handler_is_logged_under_the_request_id_of_its_event(monkeypatch, caplog):
    def handler(envelope):
        raise Boom("bad event")

    monkeypatch.setitem(HANDLERS, EVENT, handler)
    monkeypatch.setattr(consumer.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(consumer, "close_old_connections", lambda: None)
    token = set_request_id("req-from-gateway")
    try:
        envelope = build_envelope(EVENT, {"branch_id": KEY})
    finally:
        reset_request_id(token)
    caplog.handler.setFormatter(JsonFormatter())

    EventConsumer(FakeKafka(fake_message(envelope)), dlq_producer=FakeKafka()).poll_once()

    failures = [json.loads(line) for line in caplog.text.splitlines() if "Handler failed" in line]
    assert len(failures) == 3
    assert {entry["request_id"] for entry in failures} == {"req-from-gateway"}


def test_handler_publishes_with_the_correlation_id_of_the_event_it_handles(monkeypatch):
    monkeypatch.setitem(HANDLERS, EVENT, lambda envelope: publish_event(EVENT, {"branch_id": KEY}, key=KEY))
    token = set_request_id("req-from-gateway")
    try:
        incoming = build_envelope(EVENT, {"branch_id": KEY})
    finally:
        reset_request_id(token)
    assert incoming["correlation_id"] == "req-from-gateway"

    apply_event(incoming | {"event_id": str(uuid.uuid4())})

    assert Outbox.objects.get(key=KEY).envelope["correlation_id"] == "req-from-gateway"
