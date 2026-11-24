"""Reference data through the REST APIs (implementation plan §5 item 5): branches BR-01..BR-05,
demo users, the catalogue from generate_history.CATALOGUE, base prices and suppliers.

Safe to re-run. Missing rows are created and existing ones are patched to the values below, and
every write publishes its event again, so the event-fed copies in the other services fill even
for rows that were created before the outbox existed.

    python seed/seed_reference.py                          # gateway on http://localhost:8080
    python seed/seed_reference.py --base-url http://localhost:8090/api
"""

import argparse
import itertools
import json
import os
import time
import urllib.error
import urllib.request
from datetime import date
from decimal import Decimal

from generate_history import CATALOGUE, CATEGORIES

PASSWORD = "demo1234"
BASE_PRICES_FROM = date(2025, 1, 1)
BARCODE_PREFIX = "884"  # GS1 prefix for Cambodia
SUPPLIER_COST_SHARE = Decimal("0.70")
RETRIES = 5

BRANCHES = [
    {"branch_id": "BR-01", "name": "Riverside", "region": "PHNOM_PENH", "address": "Sisowath Quay"},
    {"branch_id": "BR-02", "name": "Toul Kork", "region": "PHNOM_PENH", "address": "Street 289"},
    {"branch_id": "BR-03", "name": "Old Market", "region": "SIEM_REAP", "address": "Pub Street"},
    {"branch_id": "BR-04", "name": "Battambang Centre", "region": "BATTAMBANG", "address": "Street 3"},
    {"branch_id": "BR-05", "name": "Ochheuteal", "region": "SIHANOUKVILLE", "address": "Serendipity Road"},
]

PRODUCT_NAMES = {code: name for _, products, _ in CATEGORIES for code, name, _ in products}

CASE_SIZE = {"Beverages": 24, "Snacks": 12, "Dairy": 12, "Bakery": 6, "Produce": 1, "Frozen": 12}
DEFAULT_CASE_SIZE = 12
LEAD_TIME_DAYS = {"Produce": 1, "Bakery": 1, "Dairy": 2, "Frozen": 3}
DEFAULT_LEAD_TIME_DAYS = 4


class Api:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.token: str | None = None
        self.calls = 0

    def __call__(self, method: str, path: str, body: dict | None = None):
        request = urllib.request.Request(
            self.base_url + path,
            method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Content-Type": "application/json"}
            | ({"Authorization": f"Bearer {self.token}"} if self.token else {}),
        )
        self.calls += 1
        for attempt in range(1, RETRIES + 1):
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    return json.loads(response.read() or "null")
            except urllib.error.HTTPError as exc:
                if exc.code == 503 and attempt < RETRIES:  # the gateway's rate limit
                    time.sleep(attempt)
                    continue
                raise SystemExit(f"{method} {path} -> {exc.code}: {exc.read().decode()[:500]}") from None

    def all(self, path: str) -> list[dict]:
        return self("GET", f"{path}?page_size=500")["results"]


def barcode(index: int) -> str:
    digits = f"{BARCODE_PREFIX}{index:09d}"
    check = (10 - sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(digits)) % 10) % 10
    return digits + str(check)


def seed_branches(api: Api) -> set[str]:
    existing = {b["branch_id"]: b["status"] for b in api.all("/admin/branches")}
    for branch in BRANCHES:
        if branch["branch_id"] in existing:
            fields = {k: v for k, v in branch.items() if k != "branch_id"}
            api("PATCH", f"/admin/branches/{branch['branch_id']}", fields)
        else:
            api("POST", "/admin/branches", branch)
    return {branch_id for branch_id, status in existing.items() if status == "CLOSED"}


def seed_users(api: Api, closed: set[str]) -> None:
    users = {u["email"]: u for u in api("GET", "/admin/users")["results"]}
    for branch in BRANCHES:
        number = branch["branch_id"].removeprefix("BR-")
        for role, title in (("BRANCH_MANAGER", "Manager"), ("CASHIER", "Cashier")):
            email = f"{title.lower()}.br{number}@demo.local"
            user = users.get(email) or api(
                "POST", "/admin/users", {"email": email, "full_name": f"{title} {branch['name']}", "password": PASSWORD}
            )
            if branch["branch_id"] not in closed:
                api("POST", f"/admin/users/{user['user_id']}/roles", {"role_code": role, "branch_id": branch["branch_id"]})


def seed_categories(api: Api) -> dict[str, str]:
    categories = {c["name"]: c["category_id"] for c in api.all("/catalog/categories")}
    for name, _, _ in CATEGORIES:
        if name not in categories:
            categories[name] = api("POST", "/catalog/categories", {"name": name})["category_id"]
    return categories


def seed_products(api: Api, categories: dict[str, str]) -> None:
    product_of_sku = {s["sku"]: p["product_id"] for p in api.all("/catalog/products") for s in p["skus"]}
    index = {s.sku: i for i, s in enumerate(CATALOGUE, start=1)}
    for code, skus in itertools.groupby(CATALOGUE, key=lambda s: s.sku.rsplit("-", 1)[0]):
        skus = list(skus)
        category = skus[0].category_name
        body = {
            "category_id": categories[category],
            "name": PRODUCT_NAMES[code],
            "status": "ACTIVE",
            "skus": [
                {
                    "sku": s.sku,
                    "name": s.name,
                    "barcode": barcode(index[s.sku]),
                    "unit": "EA",
                    "pack_size": CASE_SIZE.get(category, DEFAULT_CASE_SIZE),
                }
                for s in skus
            ],
        }
        product_id = next((product_of_sku[s.sku] for s in skus if s.sku in product_of_sku), None)
        if product_id:
            api("PATCH", f"/catalog/products/{product_id}", body)
        else:
            api("POST", "/catalog/products", body)


def seed_prices(api: Api) -> None:
    for s in CATALOGUE:
        api(
            "PUT",
            f"/catalog/prices/{s.sku}",
            {"branch_scope": "ALL", "amount": str(s.unit_price), "valid_from": BASE_PRICES_FROM.isoformat()},
        )


def seed_suppliers(api: Api) -> None:
    suppliers = {s["name"]: s for s in api.all("/catalog/suppliers")}
    for category, _, _ in CATEGORIES:
        name = f"{category} Supply Co."
        fields = {
            "name": name,
            "contact_email": f"orders@{category.lower().replace(' ', '-')}-supply.example",
            "lead_time_days": LEAD_TIME_DAYS.get(category, DEFAULT_LEAD_TIME_DAYS),
        }
        supplier = suppliers.get(name)
        if supplier:
            api("PATCH", f"/catalog/suppliers/{supplier['supplier_id']}", fields)
        else:
            supplier = api("POST", "/catalog/suppliers", fields)
        for s in (s for s in CATALOGUE if s.category_name == category):
            terms = {
                "unit_cost": str((s.unit_price * SUPPLIER_COST_SHARE).quantize(Decimal("0.01"))),
                "min_order_qty": CASE_SIZE.get(category, DEFAULT_CASE_SIZE),
                "is_preferred": True,
            }
            api("PUT", f"/catalog/suppliers/{supplier['supplier_id']}/skus/{s.sku}", terms)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    port = os.environ.get("GATEWAY_PORT", "8080")
    parser.add_argument("--base-url", default=os.environ.get("API_BASE_URL", f"http://localhost:{port}/api"))
    parser.add_argument("--email", default=os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "hq@demo.local"))
    parser.add_argument("--password", default=os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", PASSWORD))
    args = parser.parse_args()

    api = Api(args.base_url)
    api.token = api("POST", "/admin/auth/login", {"email": args.email, "password": args.password})["access_token"]

    closed = seed_branches(api)
    seed_users(api, closed)
    categories = seed_categories(api)
    seed_products(api, categories)
    seed_prices(api)
    seed_suppliers(api)
    print(
        f"Seeded {len(BRANCHES)} branches, {len(BRANCHES) * 2} users, {len(categories)} categories, "
        f"{len(CATALOGUE)} SKUs with prices, {len(CATEGORIES)} suppliers in {api.calls} API calls"
    )


if __name__ == "__main__":
    main()
