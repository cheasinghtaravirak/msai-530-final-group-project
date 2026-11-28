from datetime import date
from decimal import Decimal

import pytest
from django.conf import settings
from django.utils import timezone
from products.models import Category, Price, Product, Sku
from products.pricing import current_prices
from rest_framework.test import APIClient

from retail_common.auth import HQ_ADMIN, TokenUser
from retail_common.models import Outbox

pytestmark = pytest.mark.django_db


@pytest.fixture
def sku():
    category = Category.objects.create(name="Test category")
    product = Product.objects.create(category=category, name="Test cola")
    return Sku.objects.create(sku="TEST-COLA", product=product, name="Test cola 330 ml", barcode="0000000000017")


def price(sku, scope, valid_from, amount):
    Price.objects.create(sku=sku, branch_scope=scope, valid_from=valid_from, amount=Decimal(amount))


def amount_on(sku, branch_id, on_date):
    row = current_prices([sku.sku], branch_id, on_date).get(sku.sku)
    return row and str(row.amount)


def test_branch_price_beats_a_newer_all_price(sku):
    price(sku, "ALL", date(2026, 1, 1), "1.00")
    price(sku, "BR-01", date(2025, 6, 1), "0.90")

    assert amount_on(sku, "BR-01", date(2026, 2, 1)) == "0.90"
    assert amount_on(sku, "BR-02", date(2026, 2, 1)) == "1.00"


def test_latest_valid_from_on_or_before_the_date_wins(sku):
    price(sku, "ALL", date(2025, 1, 1), "1.00")
    price(sku, "ALL", date(2026, 3, 1), "1.20")
    price(sku, "BR-01", date(2027, 1, 1), "0.50")

    assert amount_on(sku, "BR-01", date(2026, 2, 28)) == "1.00"
    assert amount_on(sku, "BR-01", date(2026, 3, 1)) == "1.20"
    assert amount_on(sku, "BR-01", date(2027, 1, 1)) == "0.50"


def test_no_price_before_the_first_valid_from(sku):
    price(sku, "ALL", date(2026, 3, 1), "1.20")

    assert amount_on(sku, "BR-01", date(2026, 2, 28)) is None


def test_price_edit_publishes_price_changed_and_s6_serves_it(sku):
    hq = APIClient()
    hq.force_authenticate(TokenUser(id="hq", roles=[{"role": HQ_ADMIN, "branch_id": None}]))
    today = timezone.localdate().isoformat()

    response = hq.put(
        "/prices/TEST-COLA", {"branch_scope": "BR-01", "amount": "1.5", "valid_from": today}, format="json"
    )

    assert response.status_code == 200
    event = Outbox.objects.get(event_type="price.changed", key=f"TEST-COLA:BR-01:{today}")
    assert event.envelope["payload"] == {
        "sku": "TEST-COLA",
        "branch_scope": "BR-01",
        "amount": "1.50",
        "currency": "USD",
        "valid_from": today,
    }

    s6 = APIClient().get("/prices/TEST-COLA?branch_id=BR-01", HTTP_X_SERVICE_TOKEN=settings.SERVICE_TOKEN)
    assert s6.status_code == 200
    assert s6.json() == {
        "sku": "TEST-COLA",
        "name": "Test cola 330 ml",
        "barcode": "0000000000017",
        "amount": "1.50",
        "valid_from": today,
    }
