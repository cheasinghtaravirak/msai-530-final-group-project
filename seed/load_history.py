"""Load about 6 months of sales history straight into the databases (implementation plan §9, M4).

Writes the orders from generate_history into order_db (sales_order, order_line, payment) and
analytics_db (fact_sales_line, marking each loaded day dirty), gives every branch and SKU an opening
stock balance in inventory_db (an ADJUST movement plus its stock_level change) and copies it to
analytics stock_current, then runs J2 day_close and J6 month_close through the API.

It publishes no events: history must not replay through Kafka. Every insert skips rows that are
already there, so a second run, or a run after a crash, changes nothing that the first one wrote.
A rerun reuses the window already in order_db, so it never loads a second, shifted history.

Runs on the compose network, where each database takes only its own service's login:

    docker run --rm --network retail_default --env-file .env -v "$PWD:/src" -w /src \\
        retail/analytics python seed/load_history.py
"""

import argparse
import os
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from datetime import time as clock

import psycopg
from generate_history import CATALOGUE, TZ, cashier_id, orders
from seed_reference import PASSWORD, Api

OPENING_DAYS_OF_COVER = 10
RECENT_DAYS = 28
PAYMENT_METHODS = ("CASH",) * 6 + ("CARD",) * 3 + ("QR",)
NAMES = {s.sku: s.name for s in CATALOGUE}


def connect(service: str) -> psycopg.Connection:
    password = os.environ.get(f"{service.upper()}_DB_PASSWORD", service)
    host = os.environ.get("PGHOST", "postgres")
    return psycopg.connect(f"postgresql://{service}_svc:{password}@{host}:5432/{service}_db")


def loaded_window_end(order_db: psycopg.Connection) -> date | None:
    cashiers = [cashier_id(f"BR-0{n}") for n in range(1, 6)]
    return order_db.execute("SELECT max(sale_date) FROM sales_order WHERE cashier_id = ANY(%s)", [cashiers]).fetchone()[
        0
    ]


def copy_rows(cur: psycopg.Cursor, table: str, columns: str, rows) -> None:
    with cur.copy(f"COPY {table} ({columns}) FROM STDIN") as copy:
        for row in rows:
            copy.write_row(row)


def load_sales(order_db: psycopg.Connection, analytics_db: psycopg.Connection, end: date) -> dict:
    """One pass over the history, streamed into both databases. Returns recent units per branch and SKU.

    A connection runs one COPY at a time, so Order gets one wide row per line and SQL splits it into
    orders, lines and payments.
    """
    recent_units: dict[tuple[str, str], int] = defaultdict(int)
    recent_from = end - timedelta(days=RECENT_DAYS - 1)
    with order_db.cursor() as o, analytics_db.cursor() as a:
        o.execute(
            """
            CREATE TEMP TABLE h_line (
                order_id uuid, branch_id text, cashier_id uuid, total numeric, completed_at timestamptz,
                sale_date date, method text, line_no int, sku text, name text, unit_price numeric, qty int,
                line_total numeric
            ) ON COMMIT DROP
            """
        )
        a.execute("CREATE TEMP TABLE h_fact (LIKE fact_sales_line) ON COMMIT DROP")
        with (
            o.copy("COPY h_line FROM STDIN") as order_copy,
            a.copy(
                "COPY h_fact (order_id, line_no, entry_type, branch_id, sku, channel, sale_date, qty, net_amount) "
                "FROM STDIN"
            ) as fact_copy,
        ):
            for order in orders(end):
                oid, branch, day = order["order_id"], order["branch_id"], order["sale_date"]
                head = (oid, branch, order["cashier_id"], order["total_amount"], order["completed_at"], day)
                method = PAYMENT_METHODS[oid.int % len(PAYMENT_METHODS)]
                for line in order["lines"]:
                    sku, qty, total = line["sku"], line["qty"], line["line_total"]
                    order_copy.write_row(
                        (*head, method, line["line_no"], sku, NAMES[sku], line["unit_price"], qty, total)
                    )
                    fact_copy.write_row((oid, line["line_no"], "SALE", branch, sku, "POS", day, qty, total))
                    if day >= recent_from:
                        recent_units[branch, sku] += qty
        orders_added = o.execute(
            """
            INSERT INTO sales_order
                (order_id, branch_id, cashier_id, channel, status, total_amount, completed_at, sale_date)
            SELECT DISTINCT ON (order_id) order_id, branch_id, cashier_id, 'POS', 'COMPLETED', total, completed_at,
                   sale_date
            FROM h_line
            ON CONFLICT DO NOTHING
            """
        ).rowcount
        o.execute(
            """
            INSERT INTO order_line (order_id, line_no, sku, product_name_snapshot, unit_price_snapshot, qty, line_total)
            SELECT order_id, line_no, sku, name, unit_price, qty, line_total FROM h_line
            ON CONFLICT DO NOTHING
            """
        )
        o.execute(
            """
            INSERT INTO payment (payment_id, order_id, method, amount, reference)
            SELECT DISTINCT ON (order_id) md5('payment:' || order_id)::uuid, order_id, method, total, '' FROM h_line
            ON CONFLICT DO NOTHING
            """
        )
        facts_added = a.execute(
            """
            WITH added AS (
                INSERT INTO fact_sales_line SELECT * FROM h_fact ON CONFLICT DO NOTHING RETURNING branch_id, sale_date
            )
            INSERT INTO dirty_day (branch_id, sale_date, marked_at)
            SELECT DISTINCT branch_id, sale_date, now() FROM added
            ON CONFLICT (branch_id, sale_date) DO UPDATE SET marked_at = EXCLUDED.marked_at
            """
        ).rowcount
    order_db.commit()
    analytics_db.commit()
    print(f"order_db      {orders_added:,} orders added")
    print(f"analytics_db  {facts_added:,} branch-days marked dirty")
    return recent_units


def open_stock(
    inventory_db: psycopg.Connection, analytics_db: psycopg.Connection, end: date, recent_units: dict
) -> None:
    """The opening balance is one ADJUST movement per branch and SKU, so the ledger explains every unit on hand."""
    at = datetime.combine(end, clock(21), TZ)
    branches = sorted({branch for branch, _ in recent_units} | {f"BR-0{n}" for n in range(1, 6)})
    openings = [
        (branch, s.sku, round(recent_units.get((branch, s.sku), 0) / RECENT_DAYS * OPENING_DAYS_OF_COVER))
        for branch in branches
        for s in CATALOGUE
    ]
    with inventory_db.cursor() as cur:
        cur.execute("CREATE TEMP TABLE h_opening (branch_id text, sku text, qty int) ON COMMIT DROP")
        copy_rows(cur, "h_opening", "branch_id, sku, qty", (row for row in openings if row[2] != 0))
        added = cur.execute(
            """
            WITH movement AS (
                INSERT INTO stock_movement
                    (movement_id, branch_id, sku, qty_delta, reason, source_ref, source_line, note, occurred_at)
                SELECT gen_random_uuid(), branch_id, sku, qty, 'ADJUST', 'opening:' || sku, 1,
                       'Opening balance from the history load', %s
                FROM h_opening
                ON CONFLICT (source_ref, source_line, branch_id, reason) DO NOTHING
                RETURNING branch_id, sku, qty_delta
            )
            INSERT INTO stock_level (branch_id, sku, on_hand, on_order, version, updated_at)
            SELECT branch_id, sku, qty_delta, 0, 1, now() FROM movement
            ON CONFLICT (branch_id, sku) DO UPDATE
                SET on_hand = stock_level.on_hand + EXCLUDED.on_hand, version = stock_level.version + 1,
                    updated_at = now()
            """,
            [at],
        ).rowcount
        levels = cur.execute("SELECT branch_id, sku, on_hand, on_order, version FROM stock_level").fetchall()
    inventory_db.commit()
    with analytics_db.cursor() as cur:
        cur.execute("CREATE TEMP TABLE h_stock (LIKE stock_current) ON COMMIT DROP")
        copy_rows(cur, "h_stock", "branch_id, sku, on_hand, on_order, version", levels)
        cur.execute(
            """
            INSERT INTO stock_current SELECT * FROM h_stock
            ON CONFLICT (branch_id, sku) DO UPDATE
                SET on_hand = EXCLUDED.on_hand, on_order = EXCLUDED.on_order, version = EXCLUDED.version
                WHERE stock_current.version < EXCLUDED.version
            """
        )
    analytics_db.commit()
    print(f"inventory_db  {added:,} opening balances added, {len(levels):,} stock rows copied to analytics")


def run_job(api: Api, job: str) -> None:
    run = api("POST", f"/analytics/jobs/{job}/run")
    started = time.monotonic()
    while run["status"] in ("QUEUED", "RUNNING"):
        time.sleep(1)
        run = api("GET", f"/analytics/jobs/runs/{run['run_id']}")
    if run["status"] != "DONE":
        raise SystemExit(f"{job} {run['status']}: {run['message']}")
    print(f"{job:13} {run['message']} ({time.monotonic() - started:.0f} s)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--end", type=date.fromisoformat, help="last day of a first load (default: yesterday)")
    parser.add_argument("--base-url", default=os.environ.get("API_BASE_URL", "http://gateway/api"))
    parser.add_argument("--email", default=os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "hq@demo.local"))
    parser.add_argument("--password", default=os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", PASSWORD))
    args = parser.parse_args()

    with connect("order") as order_db, connect("analytics") as analytics_db, connect("inventory") as inventory_db:
        end = loaded_window_end(order_db)
        if end and args.end and args.end != end:
            print(f"History already loaded up to {end}; reloading that window, not {args.end}.")
        end = end or args.end or datetime.now(TZ).date() - timedelta(days=1)
        print(f"history ends  {end}")
        recent_units = load_sales(order_db, analytics_db, end)
        open_stock(inventory_db, analytics_db, end, recent_units)

    api = Api(args.base_url)
    api.token = api("POST", "/admin/auth/login", {"email": args.email, "password": args.password})["access_token"]
    run_job(api, "day_close")
    run_job(api, "month_close")


if __name__ == "__main__":
    main()
