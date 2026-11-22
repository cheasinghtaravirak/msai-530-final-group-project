"""Create every Kafka topic from the catalogue. Run once at startup by the kafka-init container.

    python -m retail_common.create_topics

Safe to run again: existing topics are left alone.
"""

import os
import sys
import time

from confluent_kafka import KafkaException
from confluent_kafka.admin import AdminClient, NewTopic

from .topics import DLQ_RETENTION_MS, TOPICS, dlq_name


def wanted_topics() -> list[NewTopic]:
    result = []
    for t in TOPICS.values():
        if t.compact:
            config = {"cleanup.policy": "compact"}
        else:
            config = {"cleanup.policy": "delete", "retention.ms": str(t.retention_ms)}
        result.append(NewTopic(t.name, num_partitions=t.partitions, replication_factor=1, config=config))
        result.append(
            NewTopic(
                dlq_name(t.name),
                num_partitions=1,
                replication_factor=1,
                config={"cleanup.policy": "delete", "retention.ms": str(DLQ_RETENTION_MS)},
            )
        )
    return result


def main() -> int:
    bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    admin = AdminClient({"bootstrap.servers": bootstrap})

    for attempt in range(1, 31):
        try:
            existing = set(admin.list_topics(timeout=5).topics)
            break
        except KafkaException as exc:
            print(f"Waiting for Kafka at {bootstrap} (attempt {attempt}): {exc}", flush=True)
            time.sleep(2)
    else:
        print("Kafka did not become available.", flush=True)
        return 1

    missing = [t for t in wanted_topics() if t.topic not in existing]
    failed = False
    if missing:
        for name, future in admin.create_topics(missing).items():
            try:
                future.result()
                print(f"Created {name}", flush=True)
            except KafkaException as exc:
                if "TOPIC_ALREADY_EXISTS" in str(exc):
                    continue
                print(f"Failed to create {name}: {exc}", flush=True)
                failed = True

    print(f"Topics ready ({len(TOPICS)} event topics + DLQs).", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
