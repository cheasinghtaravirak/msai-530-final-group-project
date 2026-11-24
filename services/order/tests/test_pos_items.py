from datetime import date, timedelta

import caches.handlers  # noqa: F401 - registers the event handlers
import pytest
from caches.models import ProductCache
from caches.pricing import current_prices
from django.utils import timezone
from rest_framework.test import APIClient

from retail_common.auth import CASHIER, TokenUser
from retail_common.consumer import apply_event
from retail_common.events import build_envelope

pytestmark = pytest.mark.django_db

SKU = "TEST-COLA"
BARCODE = "0000000000017"


def product_event(name="Test cola 330 ml", status="ACTIVE"):
    return build_envelope(
        "product.upserted",
        {
            "sku": SKU,
            "product_id": "5b0d7f4e-0000-4000-8000-000000000001",
            "barcode": BARCODE,
            "name": name,
            "brand": "",
            "category_id": "5b0d7f4e-0000-4000-8000-000000000002",
            "category_name": "Test",
            "pack_size": 24,
            "status": status,
        },
    )


def price_event(scope, valid_from, amount):
    payload = {"sku": SKU, "branch_scope": scope, "amount": amount, "currency": "USD", "valid_from": valid_from}
    return build_envelope("price.changed", payload)


def lookup(branch_id="BR-01", **params):
    client = APIClient()
    client.force_authenticate(TokenUser(id="cashier", roles=[{"role": CASHIER, "branch_id": "BR-01"}]))
    return client.get("/pos/items", {"branch_id": branch_id, **params})


def test_price_rule_matches_catalog():
    apply_event(product_event())
    apply_event(price_event("ALL", "2025-01-01", "1.00"))
    apply_event(price_event("ALL", "2026-03-01", "1.20"))
    apply_event(price_event("BR-01", "2025-06-01", "0.90"))

    def amount(branch_id, on_date):
        return str(current_prices([SKU], branch_id, on_date)[SKU].amount)

    assert amount("BR-01", date(2026, 4, 1)) == "0.90"
    assert amount("BR-02", date(2026, 2, 28)) == "1.00"
    assert amount("BR-02", date(2026, 3, 1)) == "1.20"


def test_lookup_by_barcode_and_search_returns_todays_branch_price():
    today = timezone.localdate()
    apply_event(product_event())
    apply_event(price_event("ALL", (today - timedelta(days=30)).isoformat(), "1.00"))
    apply_event(price_event("BR-01", today.isoformat(), "0.85"))
    apply_event(price_event("BR-01", (today + timedelta(days=1)).isoformat(), "0.10"))

    by_barcode = lookup(barcode=BARCODE)
    assert by_barcode.status_code == 200
    assert by_barcode.json() == {"sku": SKU, "name": "Test cola 330 ml", "unit_price": "0.85"}

    by_text = lookup(q="test cola")
    assert by_text.status_code == 200
    assert by_text.json()["results"] == [{"sku": SKU, "name": "Test cola 330 ml", "unit_price": "0.85"}]


def test_lookup_refuses_a_branch_outside_the_token():
    assert lookup(branch_id="BR-02", q="test cola").status_code == 403


def test_redelivered_and_republished_product_leaves_one_cache_row():
    first = product_event()
    apply_event(first)
    apply_event(first)
    apply_event(product_event(name="Test cola can"))

    assert list(ProductCache.objects.filter(sku=SKU).values_list("name", flat=True)) == ["Test cola can"]


def test_price_before_product_yields_a_priced_item_once_the_product_arrives():
    apply_event(price_event("ALL", "2025-01-01", "1.00"))
    assert lookup(barcode=BARCODE).status_code == 404

    apply_event(product_event())

    assert lookup(barcode=BARCODE).json()["unit_price"] == "1.00"


def test_discontinued_item_is_not_sold():
    apply_event(product_event())
    apply_event(price_event("ALL", "2025-01-01", "1.00"))
    apply_event(product_event(status="DISCONTINUED"))

    assert lookup(barcode=BARCODE).status_code == 404
