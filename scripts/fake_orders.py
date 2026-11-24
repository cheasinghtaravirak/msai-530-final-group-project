"""Publish fake `order.completed` events (design doc §6.3 E5) so Analytics can be built before Order.

Orders use the history generator's catalogue and basket rules, stamped with the current time.
The envelope comes from retail_common.events.build_envelope, with producer "order".
Unlike the services, this script produces to Kafka directly: there is no outbox to relay from.

Needs retail_common installed (`pip install -e libs/retail_common`), or run it in a service image:

    python scripts/fake_orders.py --dry-run --count 2
    python scripts/fake_orders.py --count 20 --interval 0.5            # host, Kafka on localhost:9094
    docker run --rm --network retail_default -v "$PWD:/src" -w /src retail/analytics \\
        python scripts/fake_orders.py --bootstrap kafka:9092 --count 20
"""

import argparse
import json
import random
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

import django
from django.conf import settings

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "seed"))
import generate_history as history  # noqa: E402

EVENT_TYPE = "order.completed"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", type=int, default=10, help="number of orders (default 10)")
    parser.add_argument("--branch", choices=sorted(history.BRANCH_SIZE), help="default: a random branch per order")
    parser.add_argument("--interval", type=float, default=0.0, help="seconds between orders")
    parser.add_argument("--bootstrap", default="localhost:9094", help="Kafka bootstrap servers")
    parser.add_argument("--dry-run", action="store_true", help="print the events, publish nothing")
    args = parser.parse_args()

    settings.configure(
        SERVICE_NAME="order",
        KAFKA_BOOTSTRAP_SERVERS=args.bootstrap,
        TIME_ZONE="Asia/Phnom_Penh",
        USE_TZ=True,
        INSTALLED_APPS=["retail_common"],
    )
    django.setup()
    from retail_common.events import build_envelope
    from retail_common.kafka import producer_config
    from retail_common.topics import topic_for

    topic = topic_for(EVENT_TYPE).name
    producer = None
    failures: list[str] = []
    if not args.dry_run:
        from confluent_kafka import Producer

        producer = Producer(producer_config())

    def delivered(err, msg) -> None:
        if err:
            failures.append(f"{msg.key().decode()}: {err}")
        else:
            print(f"delivered {msg.topic()}[{msg.partition()}]@{msg.offset()} key={msg.key().decode()}")

    rng = random.Random()
    weights, _ = history.popularity(random.Random(history.SEED))
    for i in range(args.count):
        branch_id = args.branch or rng.choice(list(history.BRANCH_SIZE))
        completed_at = datetime.now(history.TZ).replace(microsecond=0)
        order = history.build_order(rng, branch_id, completed_at, weights, uuid.uuid4())
        envelope = build_envelope(EVENT_TYPE, order, correlation_id=f"fake-orders-{uuid.uuid4().hex[:12]}")
        key = envelope["payload"]["order_id"]
        if producer is None:
            print(json.dumps({"topic": topic, "key": key, "value": envelope}, indent=2))
        else:
            producer.produce(
                topic,
                key=key,
                value=json.dumps(envelope).encode(),
                on_delivery=delivered,
            )
            producer.poll(0)
        if args.interval and i < args.count - 1:
            time.sleep(args.interval)

    if producer is not None:
        undelivered = producer.flush(10)
        if failures or undelivered:
            sys.exit(f"Kafka at {args.bootstrap}: {len(failures)} failed, {undelivered} undelivered. {failures}")


if __name__ == "__main__":
    main()
