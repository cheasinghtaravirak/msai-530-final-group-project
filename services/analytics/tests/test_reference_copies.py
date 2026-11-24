import uuid
from datetime import date

import pytest
import replenishment.handlers  # noqa: F401 - registers the event handlers
import reporting.handlers  # noqa: F401
from replenishment.models import SupplierTerms
from reporting.models import Calendar, DimProduct

from retail_common.consumer import apply_event
from retail_common.events import build_envelope

pytestmark = pytest.mark.django_db

SKU = "TEST-COLA"
OLD, NEW = uuid.UUID(int=1), uuid.UUID(int=2)


def terms_event(supplier_id, is_preferred, lead_time_days=3):
    payload = {
        "sku": SKU,
        "supplier_id": str(supplier_id),
        "is_preferred": is_preferred,
        "lead_time_days": lead_time_days,
        "pack_size": 24,
        "min_order_qty": 24,
        "unit_cost": "0.49",
    }
    return build_envelope("supplier_terms.changed", payload)


def preferred_supplier():
    return list(SupplierTerms.objects.filter(sku=SKU).values_list("supplier_id", flat=True))


def test_product_upserted_fills_dim_product():
    payload = {
        "sku": SKU,
        "product_id": str(uuid.uuid4()),
        "barcode": None,
        "name": "Test cola 330 ml",
        "brand": "Testco",
        "category_id": str(uuid.UUID(int=3)),
        "category_name": "Beverages",
        "pack_size": 24,
        "status": "ACTIVE",
    }
    apply_event(build_envelope("product.upserted", payload))

    row = DimProduct.objects.get(sku=SKU)
    assert (row.name, row.category_name, row.brand) == ("Test cola 330 ml", "Beverages", "Testco")


def test_non_preferred_terms_are_not_stored():
    apply_event(terms_event(OLD, is_preferred=False))
    assert preferred_supplier() == []


# Events of one supplier share a partition and keep their order, so OLD's two events never swap.
@pytest.mark.parametrize("order", [(0, 1, 2), (0, 2, 1), (2, 0, 1)])
def test_a_preferred_supplier_swap_converges_in_any_arrival_order(order):
    # OLD is preferred, then NEW is promoted, which demotes OLD in the same Catalog transaction.
    published = [terms_event(OLD, True), terms_event(OLD, False), terms_event(NEW, True, lead_time_days=5)]

    for i in order:
        apply_event(published[i])

    assert preferred_supplier() == [NEW]
    assert SupplierTerms.objects.get(sku=SKU).lead_time_days == 5


def test_calendar_covers_2025_to_2027():
    assert Calendar.objects.filter(calendar_date__range=(date(2025, 1, 1), date(2027, 12, 31))).count() == 1095
    assert Calendar.objects.get(calendar_date=date(2026, 11, 26)).weekday == 4
