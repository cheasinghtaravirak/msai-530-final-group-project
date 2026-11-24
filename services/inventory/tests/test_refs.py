import pytest
import refs.handlers  # noqa: F401 - registers the event handlers
from refs.models import SkuRef

from retail_common.consumer import apply_event
from retail_common.events import build_envelope

pytestmark = pytest.mark.django_db


def product_event(**changes):
    payload = {
        "sku": "TEST-COLA",
        "product_id": "5b0d7f4e-0000-4000-8000-000000000001",
        "barcode": "0000000000017",
        "name": "Test cola 330 ml",
        "brand": "",
        "category_id": "5b0d7f4e-0000-4000-8000-000000000002",
        "category_name": "Test",
        "pack_size": 24,
        "status": "ACTIVE",
    }
    return build_envelope("product.upserted", payload | changes)


def test_product_upserted_keeps_one_sku_ref_with_the_latest_values():
    first = product_event()
    apply_event(first)
    apply_event(first)
    apply_event(product_event(pack_size=12, status="DISCONTINUED"))

    rows = list(SkuRef.objects.filter(sku="TEST-COLA").values("name", "pack_size", "active"))
    assert rows == [{"name": "Test cola 330 ml", "pack_size": 12, "active": False}]
