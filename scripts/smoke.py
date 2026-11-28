"""The selling path end to end through the gateway (implementation plan §13), in about 30 seconds.

A cashier looks up an item and sells one; the manager watches stock drop and "today so far" grow,
then refunds the sale and watches stock come back. Every sale it makes stays in the Kafka history,
so run it before a merge, not in a loop.

    python scripts/smoke.py                                   # gateway on http://localhost:8080
    python scripts/smoke.py --base-url http://localhost:8090/api --branch BR-02
"""

import argparse
import os
import sys
import time
import uuid
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "seed"))
from seed_reference import PASSWORD, Api  # noqa: E402

TIMEOUT_SECONDS = 15


def login(base_url: str, email: str) -> Api:
    api = Api(base_url)
    api.token = api("POST", "/admin/auth/login", {"email": email, "password": PASSWORD})["access_token"]
    return api


def wait_for(what: str, read, done) -> float:
    started = time.monotonic()
    while not done(value := read()):
        if time.monotonic() - started > TIMEOUT_SECONDS:
            raise SystemExit(f"FAIL {what}: still {value!r} after {TIMEOUT_SECONDS} s")
        time.sleep(0.2)
    elapsed = time.monotonic() - started
    print(f"ok   {what} ({elapsed:.1f} s)")
    return elapsed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    port = os.environ.get("GATEWAY_PORT", "8080")
    parser.add_argument("--base-url", default=os.environ.get("API_BASE_URL", f"http://localhost:{port}/api"))
    parser.add_argument("--branch", default="BR-01")
    parser.add_argument("--query", default="water", help="item search text")
    args = parser.parse_args()
    started = time.monotonic()
    branch = args.branch
    number = branch.removeprefix("BR-")
    cashier = login(args.base_url, f"cashier.br{number}@demo.local")
    manager = login(args.base_url, f"manager.br{number}@demo.local")

    items = cashier("GET", f"/order/pos/items?branch_id={branch}&q={args.query}")["results"]
    item = next(i for i in items if i["unit_price"] is not None)
    sku = item["sku"]
    print(f"ok   looked up {sku} at {item['unit_price']}")

    def on_hand() -> int:
        rows = manager("GET", f"/inventory/stock?branch_id={branch}&sku={sku}")["results"]
        return rows[0]["on_hand"] if rows else 0

    def today() -> tuple[Decimal, int]:
        row = manager("GET", f"/analytics/reports/sales?branch_id={branch}&grain=day")["results"][0]
        return Decimal(row["revenue"]), row["orders"]

    stock_before, (revenue_before, orders_before) = on_hand(), today()
    sale = {
        "order_id": str(uuid.uuid4()),
        "branch_id": branch,
        "lines": [{"sku": sku, "qty": 1}],
        "payments": [{"method": "CASH", "amount": item["unit_price"]}],
    }
    order = cashier("POST", "/order/orders", sale)
    assert order["status"] == "COMPLETED", order
    assert cashier("POST", "/order/orders", sale) == order, "a retry returns the same order"
    print(f"ok   sold order {order['order_id']} for {order['total_amount']}, and a retry returned it")

    price = Decimal(order["total_amount"])
    wait_for("stock dropped by 1", on_hand, lambda n: n == stock_before - 1)
    wait_for(
        "today so far includes the sale",
        today,
        lambda t: t == (revenue_before + price, orders_before + 1),
    )

    refunded = manager("POST", f"/order/orders/{order['order_id']}/refund")
    assert refunded["status"] == "REFUNDED", refunded
    print("ok   refunded")
    wait_for("stock came back", on_hand, lambda n: n == stock_before)
    wait_for("today's revenue dropped back", today, lambda t: t == (revenue_before, orders_before + 1))
    print(f"PASS in {time.monotonic() - started:.1f} s")


if __name__ == "__main__":
    main()
