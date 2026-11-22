from django.conf import settings


def producer_config() -> dict:
    return {
        "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
        "client.id": f"{settings.SERVICE_NAME}-producer",
        "acks": "all",
        "enable.idempotence": True,
        "linger.ms": 5,
    }


def consumer_config(group_id: str | None = None) -> dict:
    return {
        "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
        "client.id": f"{settings.SERVICE_NAME}-consumer",
        "group.id": group_id or settings.SERVICE_NAME,
        # Offsets are committed by hand, only after the DB transaction commits.
        "enable.auto.commit": False,
        # A new consumer group reads from the beginning, so late starters miss nothing.
        "auto.offset.reset": "earliest",
    }
