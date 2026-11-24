"""Synthetic sales history: about 6 months x 5 branches x 200 SKUs (design doc §12).

Each order has the shape of the `order.completed` payload (design doc §6.3, E5), with Python
types (UUID, datetime, date, Decimal), so `load_history.py` can bulk-insert it into
`sales_order`, `order_line` and `fact_sales_line`, and `scripts/fake_orders.py` can publish it.

The output is deterministic: the same `end` date always gives the same orders.

    python seed/generate_history.py                    # summary of the history ending yesterday
    python seed/generate_history.py --end 2026-11-30
"""

import argparse
import hashlib
import random
import uuid
from collections import Counter, defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

SEED = 530
TZ = ZoneInfo("Asia/Phnom_Penh")
ID_NAMESPACE = uuid.UUID("6d1c7a3e-4f0b-4c55-9f43-5e0b8c3f9a10")

BRANCH_SIZE = {"BR-01": 1.3, "BR-02": 1.0, "BR-03": 0.9, "BR-04": 1.1, "BR-05": 0.7}
WEEKDAY_FACTOR = (0.85, 0.85, 0.9, 0.95, 1.1, 1.3, 1.2)
ORDERS_PER_DAY = 85
TREND = 0.10
OPEN_HOURS = (7, 21)
LINES_PER_ORDER = {1: 30, 2: 25, 3: 20, 4: 12, 5: 8, 6: 5}
QTY_PER_LINE = {1: 70, 2: 20, 3: 7, 4: 3}
SLOW_SKUS = 20
SLOW_FACTOR = 0.25
STOCKOUT_GAPS = 8

CATEGORIES = [
    (
        "Beverages",
        [
            ("COKE", "Coca-Cola", "0.70"),
            ("SPRITE", "Sprite", "0.70"),
            ("FANTA", "Fanta Orange", "0.70"),
            ("PEPSI", "Pepsi", "0.65"),
            ("WATER", "Mineral Water", "0.30"),
            ("REDBULL", "Red Bull", "0.90"),
            ("ICETEA", "Iced Lemon Tea", "0.80"),
            ("SOYMILK", "Soy Milk", "0.60"),
            ("COFFEE", "Iced Coffee", "1.00"),
            ("OJ", "Orange Juice", "1.20"),
        ],
        [("330", "330 ml", "1"), ("1500", "1.5 L", "2.2")],
    ),
    (
        "Snacks",
        [
            ("LAYS", "Lay's Classic", "0.90"),
            ("PRINGLES", "Pringles Original", "1.80"),
            ("OREO", "Oreo", "0.80"),
            ("KITKAT", "KitKat", "0.75"),
            ("SNICKERS", "Snickers", "0.85"),
            ("PEANUT", "Roasted Peanuts", "0.60"),
            ("RICECRK", "Rice Crackers", "0.70"),
            ("CASSAVA", "Cassava Chips", "0.65"),
            ("POPCORN", "Popcorn", "0.95"),
            ("WAFER", "Chocolate Wafer", "0.55"),
        ],
        [("S", "small", "1"), ("L", "family pack", "2.4")],
    ),
    (
        "Dairy",
        [
            ("MILK", "Fresh Milk", "1.10"),
            ("CHOCMILK", "Chocolate Milk", "0.90"),
            ("YOGURT", "Plain Yogurt", "0.70"),
            ("FRUITYOG", "Strawberry Yogurt", "0.80"),
            ("CHEESE", "Cheddar Slices", "2.50"),
            ("BUTTER", "Butter", "2.20"),
            ("CONDMILK", "Condensed Milk", "1.20"),
            ("EVAPMILK", "Evaporated Milk", "1.00"),
            ("CREAM", "Whipping Cream", "2.80"),
            ("EGGS", "Eggs", "1.50"),
        ],
        [("S", "small", "1"), ("L", "large", "1.8")],
    ),
    (
        "Bakery",
        [
            ("BREAD-WHT", "White Bread", "1.20"),
            ("BREAD-WW", "Wholewheat Bread", "1.50"),
            ("BAGUETTE", "Baguette", "0.50"),
            ("CROISSANT", "Croissant", "0.90"),
            ("MUFFIN", "Blueberry Muffin", "1.10"),
            ("DONUT", "Glazed Donut", "0.70"),
            ("BUN", "Sweet Bun", "0.40"),
            ("SPONGE", "Sponge Cake", "1.60"),
            ("COOKIE", "Butter Cookies", "1.30"),
            ("TOAST", "Garlic Toast", "1.00"),
        ],
        [("1", "single", "1"), ("6", "pack of 6", "5")],
    ),
    (
        "Produce",
        [
            ("BANANA", "Bananas", "0.80"),
            ("APPLE", "Apples", "1.60"),
            ("MANGO", "Mangoes", "1.40"),
            ("ORANGE", "Oranges", "1.30"),
            ("TOMATO", "Tomatoes", "0.90"),
            ("ONION", "Red Onions", "0.70"),
            ("GARLIC", "Garlic", "1.10"),
            ("CARROT", "Carrots", "0.60"),
            ("CABBAGE", "Cabbage", "0.50"),
            ("LIME", "Limes", "0.80"),
        ],
        [("500G", "500 g", "1"), ("1KG", "1 kg", "1.8")],
    ),
    (
        "Frozen",
        [
            ("ICECREAM", "Vanilla Ice Cream", "2.20"),
            ("POPSICLE", "Mango Popsicle", "0.50"),
            ("DUMPLING", "Pork Dumplings", "2.80"),
            ("NUGGETS", "Chicken Nuggets", "3.20"),
            ("FRIES", "French Fries", "2.00"),
            ("SHRIMP", "Frozen Shrimp", "4.50"),
            ("FISHBALL", "Fish Balls", "1.80"),
            ("SPRROLL", "Spring Rolls", "2.40"),
            ("PIZZA", "Frozen Pizza", "3.80"),
            ("PEAS", "Green Peas", "1.20"),
        ],
        [("S", "small", "1"), ("L", "large", "1.9")],
    ),
    (
        "Household",
        [
            ("DETERG", "Laundry Detergent", "3.50"),
            ("DISHSOAP", "Dish Soap", "1.40"),
            ("TISSUE", "Facial Tissue", "1.10"),
            ("TOILETPPR", "Toilet Paper", "2.60"),
            ("BLEACH", "Bleach", "1.50"),
            ("SCRUB", "Scrub Sponges", "0.90"),
            ("TRASHBAG", "Trash Bags", "1.70"),
            ("FOIL", "Aluminium Foil", "2.10"),
            ("MATCHES", "Matches", "0.30"),
            ("BATTERY", "AA Batteries", "2.40"),
        ],
        [("S", "regular", "1"), ("L", "value pack", "2.6")],
    ),
    (
        "Personal Care",
        [
            ("SHAMPOO", "Shampoo", "3.20"),
            ("CONDITNR", "Conditioner", "3.40"),
            ("SOAP", "Bar Soap", "0.80"),
            ("BODYWASH", "Body Wash", "3.00"),
            ("TOOTHPST", "Toothpaste", "1.60"),
            ("TOOTHBR", "Toothbrush", "1.20"),
            ("DEODOR", "Deodorant", "2.80"),
            ("LOTION", "Body Lotion", "3.60"),
            ("RAZOR", "Disposable Razors", "2.20"),
            ("COTTON", "Cotton Buds", "0.90"),
        ],
        [("S", "regular", "1"), ("L", "large", "1.7")],
    ),
    (
        "Pantry",
        [
            ("SARDINE", "Sardines in Tomato", "1.10"),
            ("TUNA", "Tuna Chunks", "1.80"),
            ("CORNEDBF", "Corned Beef", "2.40"),
            ("BEANS", "Baked Beans", "1.20"),
            ("SWCORN", "Sweet Corn", "1.00"),
            ("COCOMILK", "Coconut Milk", "1.30"),
            ("FISHSAUCE", "Fish Sauce", "1.50"),
            ("SOYSAUCE", "Soy Sauce", "1.20"),
            ("OIL", "Vegetable Oil", "2.90"),
            ("SUGAR", "White Sugar", "1.10"),
        ],
        [("S", "small", "1"), ("L", "large", "1.8")],
    ),
    (
        "Rice and Noodles",
        [
            ("JASMINE", "Jasmine Rice", "2.50"),
            ("RICE-BRN", "Brown Rice", "2.90"),
            ("STICKY", "Sticky Rice", "2.30"),
            ("NOODLE", "Instant Noodles", "0.35"),
            ("CUPNOOD", "Cup Noodles", "0.70"),
            ("RICENOOD", "Rice Noodles", "1.10"),
            ("EGGNOOD", "Egg Noodles", "1.30"),
            ("VERMIC", "Rice Vermicelli", "1.00"),
            ("FLOUR", "Wheat Flour", "1.40"),
            ("OATS", "Rolled Oats", "2.60"),
        ],
        [("S", "small", "1"), ("L", "large", "3.2")],
    ),
]


@dataclass(frozen=True)
class Sku:
    sku: str
    name: str
    category_id: uuid.UUID
    category_name: str
    unit_price: Decimal


def _catalogue() -> list[Sku]:
    skus = []
    for category, products, variants in CATEGORIES:
        category_id = uuid.uuid5(ID_NAMESPACE, f"category:{category}")
        for code, name, price in products:
            for suffix, label, mult in variants:
                unit_price = (Decimal(price) * Decimal(mult)).quantize(Decimal("0.01"))
                skus.append(Sku(f"{code}-{suffix}", f"{name} {label}", category_id, category, unit_price))
    return skus


CATALOGUE = _catalogue()


def popularity(rng: random.Random) -> tuple[list[float], set[str]]:
    ranked = CATALOGUE[:]
    rng.shuffle(ranked)
    slow = {s.sku for s in ranked[-SLOW_SKUS:]}
    rank = {s.sku: i + 1 for i, s in enumerate(ranked)}
    weights = [rank[s.sku] ** -0.6 * (SLOW_FACTOR if s.sku in slow else 1) for s in CATALOGUE]
    return weights, slow


def cashier_id(branch_id: str) -> uuid.UUID:
    return uuid.uuid5(ID_NAMESPACE, f"cashier:{branch_id}")


def build_order(
    rng: random.Random, branch_id: str, completed_at: datetime, weights: list[float], order_id: uuid.UUID
) -> dict:
    """One order in the order.completed payload shape. SKUs with weight 0 are never picked."""
    n_lines = rng.choices(list(LINES_PER_ORDER), list(LINES_PER_ORDER.values()))[0]
    picked: list[Sku] = []
    while len(picked) < n_lines:
        sku = rng.choices(CATALOGUE, weights)[0]
        if sku not in picked:
            picked.append(sku)
    lines = []
    for line_no, sku in enumerate(picked, start=1):
        qty = rng.choices(list(QTY_PER_LINE), list(QTY_PER_LINE.values()))[0]
        lines.append(
            {
                "line_no": line_no,
                "sku": sku.sku,
                "qty": qty,
                "unit_price": sku.unit_price,
                "line_total": sku.unit_price * qty,
            }
        )
    return {
        "order_id": order_id,
        "branch_id": branch_id,
        "channel": "POS",
        "cashier_id": cashier_id(branch_id),
        "completed_at": completed_at,
        "sale_date": completed_at.date(),
        "total_amount": sum((line["line_total"] for line in lines), Decimal("0.00")),
        "lines": lines,
    }


def window(end: date) -> tuple[date, date]:
    month = end.month - 6
    year = end.year + (month - 1) // 12
    return date(year, (month - 1) % 12 + 1, 1), end


@dataclass(frozen=True)
class Stockout:
    branch_id: str
    sku: str
    first_day: date
    last_day: date


def stockouts(end: date) -> list[Stockout]:
    start, _ = window(end)
    rng = random.Random(f"{SEED}:stockouts")
    weights, _ = popularity(random.Random(SEED))
    popular = [s.sku for _, s in sorted(zip(weights, CATALOGUE, strict=True), key=lambda p: -p[0])[:40]]
    days = (end - start).days
    gaps = []
    for _ in range(STOCKOUT_GAPS):
        first = start + timedelta(days=rng.randrange(14, days - 14))
        gaps.append(
            Stockout(rng.choice(list(BRANCH_SIZE)), rng.choice(popular), first, first + timedelta(rng.randint(3, 7)))
        )
    return gaps


def orders(end: date) -> Iterator[dict]:
    start, _ = window(end)
    rng = random.Random(SEED)
    weights, _ = popularity(rng)
    gaps = stockouts(end)
    days = (end - start).days
    for offset in range(days + 1):
        day = start + timedelta(days=offset)
        trend = 1 + TREND * offset / days
        for branch_id, size in BRANCH_SIZE.items():
            out = {g.sku for g in gaps if g.branch_id == branch_id and g.first_day <= day <= g.last_day}
            day_weights = [0 if s.sku in out else w for s, w in zip(CATALOGUE, weights, strict=True)]
            mean = ORDERS_PER_DAY * size * WEEKDAY_FACTOR[day.weekday()] * trend
            opening = datetime.combine(day, time(OPEN_HOURS[0]), TZ)
            seconds = (OPEN_HOURS[1] - OPEN_HOURS[0]) * 3600
            count = max(0, round(rng.gauss(mean, mean**0.5)))
            for t in sorted(rng.randrange(seconds) for _ in range(count)):
                order_id = uuid.UUID(int=rng.getrandbits(128), version=4)
                yield build_order(rng, branch_id, opening + timedelta(seconds=t), day_weights, order_id)


def _summary(end: date) -> None:
    start, _ = window(end)
    gaps = stockouts(end)
    _, slow = popularity(random.Random(SEED))
    n_orders = n_lines = units = 0
    revenue = Decimal("0.00")
    digest = hashlib.sha256()
    skus_sold: set[str] = set()
    branches: set[str] = set()
    per_day: dict[tuple[str, date], int] = Counter()
    revenue_per_day: dict[tuple[str, date], Decimal] = defaultdict(Decimal)
    sku_units: Counter[str] = Counter()
    gap_units = 0
    first = last = None
    for o in orders(end):
        assert o["total_amount"] == sum(line["line_total"] for line in o["lines"]), "total equals the sum of lines"
        assert len({line["sku"] for line in o["lines"]}) == len(o["lines"]), "one line per SKU in an order"
        assert o["sale_date"] == o["completed_at"].astimezone(TZ).date(), "sale_date is the local date"
        n_orders += 1
        n_lines += len(o["lines"])
        revenue += o["total_amount"]
        branches.add(o["branch_id"])
        per_day[o["branch_id"], o["sale_date"]] += 1
        revenue_per_day[o["branch_id"], o["sale_date"]] += o["total_amount"]
        first = first or o["sale_date"]
        last = o["sale_date"]
        digest.update(o["order_id"].bytes)
        for line in o["lines"]:
            units += line["qty"]
            skus_sold.add(line["sku"])
            sku_units[line["sku"]] += line["qty"]
            gap_units += any(
                g.branch_id == o["branch_id"] and g.sku == line["sku"] and g.first_day <= o["sale_date"] <= g.last_day
                for g in gaps
            )
    assert gap_units == 0, "no sales inside a stockout gap"

    branch_days = len(per_day)
    print(f"window        {start} .. {end}  ({(end - start).days + 1} days)")
    print(f"sales dates   {first} .. {last}")
    print(f"branches      {len(branches)}  {sorted(branches)}")
    print(f"SKUs          {len(CATALOGUE)} in catalogue, {len(skus_sold)} sold, {len(slow)} slow sellers")
    print(f"orders        {n_orders:,}  ({n_orders / branch_days:.1f} per branch-day)")
    print(f"order lines   {n_lines:,}  ({n_lines / n_orders:.2f} per order)")
    print(f"units         {units:,}")
    print(f"revenue       {revenue:,}")
    print(f"digest        {digest.hexdigest()[:16]}  (same --end, same digest)")

    print("\nweekday     avg orders/branch-day   avg revenue/branch-day")
    by_weekday: dict[int, list[tuple[str, date]]] = defaultdict(list)
    for key in per_day:
        by_weekday[key[1].weekday()].append(key)
    for wd, name in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
        keys = by_weekday[wd]
        avg_orders = sum(per_day[k] for k in keys) / len(keys)
        avg_revenue = sum(revenue_per_day[k] for k in keys) / len(keys)
        print(f"{name}         {avg_orders:8.1f}               {avg_revenue:10.2f}")

    print("\nmonth     orders/branch-day   revenue")
    month_orders: Counter[str] = Counter()
    month_branch_days: Counter[str] = Counter()
    month_revenue: dict[str, Decimal] = defaultdict(Decimal)
    for (branch, day), n in per_day.items():
        month = day.strftime("%Y-%m")
        month_orders[month] += n
        month_branch_days[month] += 1
        month_revenue[month] += revenue_per_day[branch, day]
    for month in sorted(month_orders):
        print(f"{month}   {month_orders[month] / month_branch_days[month]:8.1f}          {month_revenue[month]:11,.2f}")

    slowest = sorted(slow, key=lambda s: sku_units[s])[:3]
    print("\nslow sellers  " + ", ".join(f"{s}: {sku_units[s]} units" for s in slowest) + " ...")
    print("stockout gaps")
    for g in gaps:
        print(f"  {g.branch_id} {g.sku:14} {g.first_day} .. {g.last_day}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    yesterday = datetime.now(TZ).date() - timedelta(days=1)
    parser.add_argument("--end", type=date.fromisoformat, default=yesterday, help="last day (default: yesterday)")
    _summary(parser.parse_args().end)
