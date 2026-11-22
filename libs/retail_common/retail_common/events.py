"""Event envelope and publishing through the transactional outbox (design doc §5, §6.3)."""

import json
import uuid
from typing import Any

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone

from .context import get_request_id
from .models import Outbox
from .topics import topic_for


def build_envelope(
    event_type: str,
    payload: dict[str, Any],
    *,
    event_version: int = 1,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    # Round-trip through JSON so Decimals become strings and datetimes ISO strings,
    # exactly as consumers will see them.
    clean_payload = json.loads(json.dumps(payload, cls=DjangoJSONEncoder))
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "event_version": event_version,
        "occurred_at": timezone.localtime().isoformat(),
        "producer": settings.SERVICE_NAME,
        "correlation_id": correlation_id or get_request_id(),
        "payload": clean_payload,
    }


def publish_event(event_type: str, payload: dict[str, Any], *, key: str, event_version: int = 1) -> Outbox:
    """Queue an event for publishing.

    Call this inside the same `transaction.atomic()` block as the business change, so the
    event is saved if and only if the change commits. The relay sends it to Kafka afterwards.
    """
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("publish_event() must be called inside transaction.atomic()")

    topic = topic_for(event_type)
    envelope = build_envelope(event_type, payload, event_version=event_version)
    return Outbox.objects.create(
        event_id=envelope["event_id"],
        event_type=event_type,
        topic=topic.name,
        key=str(key),
        envelope=envelope,
    )
