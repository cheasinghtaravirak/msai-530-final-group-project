"""Kafka topic catalogue (design doc §6.4). The single source of truth for topic settings.

The topic name is the event type. `python -m retail_common.create_topics` creates all of
them, plus a `<topic>.dlq` for each, before any service starts.
"""

from dataclasses import dataclass

DAY_MS = 24 * 60 * 60 * 1000


@dataclass(frozen=True)
class Topic:
    name: str
    key_field: str  # documents what the message key is; producers pass the key explicitly
    compact: bool = False
    retention_ms: int = -1  # -1 = keep forever (only for non-compacted topics)
    partitions: int = 3


TOPICS: dict[str, Topic] = {
    t.name: t
    for t in [
        # Reference data: compacted, so a consumer can rebuild its local copy from the start.
        Topic("branch.upserted", key_field="branch_id", compact=True),
        Topic("product.upserted", key_field="sku", compact=True),
        Topic("price.changed", key_field="sku:branch_scope:valid_from", compact=True),
        Topic("supplier_terms.changed", key_field="supplier_id:sku", compact=True),
        # Facts: kept, so Analytics can re-read any past day (J1) or rebuild.
        Topic("order.completed", key_field="order_id"),
        Topic("order.refunded", key_field="order_id"),
        Topic("stock.adjusted", key_field="branch_id:sku", retention_ms=30 * DAY_MS),
        Topic("replenishment.approved", key_field="recommendation_id"),
    ]
}

DLQ_RETENTION_MS = 30 * DAY_MS


def dlq_name(topic: str) -> str:
    return f"{topic}.dlq"


def topic_for(event_type: str) -> Topic:
    try:
        return TOPICS[event_type]
    except KeyError:
        raise ValueError(f"Unknown event type {event_type!r}. Add it to retail_common/topics.py.") from None
