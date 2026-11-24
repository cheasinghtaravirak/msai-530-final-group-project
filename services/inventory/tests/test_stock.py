import uuid

import pytest
import stock.handlers  # noqa: F401
from django.conf import settings
from refs.models import SkuRef
from rest_framework.test import APIClient
from stock.ledger import Cause, move_stock
from stock.models import StockLevel, StockMovement

from retail_common.auth import BRANCH_MANAGER, CASHIER, TokenUser
from retail_common.consumer import apply_event
from retail_common.events import build_envelope
from retail_common.models import Outbox

pytestmark = pytest.mark.django_db

BRANCH, OTHER_BRANCH = "BR-9901", "BR-9902"
COLA, BREAD = "TEST-COLA", "TEST-BREAD"
MANAGER_ID = "5b0d7f4e-0000-4000-8000-0000000000a1"
CATEGORY = "5b0d7f4e-0000-4000-8000-000000000002"


@pytest.fixture(autouse=True)
def known_skus():
    SkuRef.objects.create(sku=COLA, name="Test cola", category_id=CATEGORY)
    SkuRef.objects.create(sku=BREAD, name="Test bread", category_id=CATEGORY)


def adjustment(**fields):
    return {
        "adjustment_id": str(uuid.uuid4()),
        "branch_id": BRANCH,
        "sku": COLA,
        "qty_delta": 1,
        "note": "Count",
    } | fields


def receipt_body(**fields):
    return {"receipt_id": str(uuid.uuid4()), "branch_id": BRANCH, "lines": [{"sku": COLA, "qty": 1}]} | fields


def client_for(role, branch_id=BRANCH):
    client = APIClient()
    client.force_authenticate(TokenUser(id=MANAGER_ID, roles=[{"role": role, "branch_id": branch_id}]))
    return client


@pytest.fixture
def manager():
    return client_for(BRANCH_MANAGER)


def completed(order_id, lines=((COLA, 2), (BREAD, 1))):
    return build_envelope(
        "order.completed",
        {
            "order_id": order_id,
            "branch_id": BRANCH,
            "completed_at": "2026-11-26T14:03:22+07:00",
            "lines": [{"line_no": n, "sku": sku, "qty": qty} for n, (sku, qty) in enumerate(lines, start=1)],
        },
    )


def refunded(order_id, lines=((COLA, 2), (BREAD, 1))):
    return build_envelope(
        "order.refunded",
        {
            "order_id": order_id,
            "branch_id": BRANCH,
            "refunded_at": "2026-11-26T15:00:00+07:00",
            "lines": [{"line_no": n, "sku": sku, "qty": qty} for n, (sku, qty) in enumerate(lines, start=1)],
        },
    )


def on_hand(sku):
    return StockLevel.objects.get(branch_id=BRANCH, sku=sku).on_hand


def stock_events(sku):
    return [row.envelope["payload"] for row in Outbox.objects.filter(key=f"{BRANCH}:{sku}").order_by("created_at")]


def test_a_sale_writes_one_sale_movement_per_line_and_can_go_negative():
    order_id = str(uuid.uuid4())

    apply_event(completed(order_id))

    movements = StockMovement.objects.filter(source_ref=order_id).order_by("source_line")
    assert [(m.sku, m.qty_delta, m.reason, m.source_line) for m in movements] == [
        (COLA, -2, "SALE", 1),
        (BREAD, -1, "SALE", 2),
    ]
    assert (on_hand(COLA), on_hand(BREAD)) == (-2, -1)
    [event] = stock_events(COLA)
    assert event | {"occurred_at": None} == {
        "branch_id": BRANCH,
        "sku": COLA,
        "qty_delta": -2,
        "reason": "SALE",
        "on_hand": -2,
        "on_order": 0,
        "version": 1,
        "occurred_at": None,
    }


def test_the_same_sale_redelivered_under_a_new_event_id_deducts_once():
    order_id = str(uuid.uuid4())

    assert apply_event(completed(order_id)) is True
    assert apply_event(completed(order_id)) is True, "a new event_id gets past processed_event"

    assert StockMovement.objects.filter(source_ref=order_id).count() == 2
    assert on_hand(COLA) == -2
    assert len(stock_events(COLA)) == 1


def test_a_cause_already_applied_changes_nothing():
    cause = Cause("ADJUST", str(uuid.uuid4()), 1)

    assert move_stock(BRANCH, COLA, 5, cause, "2026-11-26T09:00:00+07:00").on_hand == 5
    assert move_stock(BRANCH, COLA, 5, cause, "2026-11-26T09:00:00+07:00") is None
    assert on_hand(COLA) == 5


def test_a_refund_puts_the_stock_back_and_bumps_the_version():
    order_id = str(uuid.uuid4())
    apply_event(completed(order_id))

    apply_event(refunded(order_id))
    apply_event(refunded(order_id))

    assert (on_hand(COLA), on_hand(BREAD)) == (0, 0)
    assert StockMovement.objects.filter(source_ref=order_id, reason="REFUND").count() == 2
    assert [e["version"] for e in stock_events(COLA)] == [1, 2]


def test_stock_list_filters_low_and_negative(manager):
    move_stock(BRANCH, COLA, settings.LOW_STOCK_THRESHOLD + 1, Cause("ADJUST", str(uuid.uuid4()), 1), "2026-11-26")
    move_stock(BRANCH, BREAD, -1, Cause("ADJUST", str(uuid.uuid4()), 1), "2026-11-26")

    def skus(**params):
        return [row["sku"] for row in manager.get("/stock", {"branch_id": BRANCH, **params}).json()["results"]]

    assert skus() == [BREAD, COLA]
    assert skus(low_only="true") == [BREAD]
    assert skus(negative_only="true") == [BREAD]
    assert skus(q="cola") == [COLA]
    assert manager.get("/stock", {"branch_id": BRANCH, "sku": COLA}).json()["results"] == [
        {"sku": COLA, "name": "Test cola", "on_hand": 6, "on_order": 0, "low": False}
    ]


def test_adjustment_writes_an_adjust_movement_with_its_author(manager):
    response = manager.post("/adjustments", adjustment(qty_delta=-3, note="Breakage"), format="json")

    assert response.status_code == 201
    assert response.json() == {"sku": COLA, "name": "Test cola", "on_hand": -3, "on_order": 0, "low": True}
    [movement] = manager.get(f"/stock/{BRANCH}/{COLA}/movements").json()["results"]
    assert movement | {"movement_id": None, "source_ref": None, "occurred_at": None} == {
        "movement_id": None,
        "qty_delta": -3,
        "reason": "ADJUST",
        "source_ref": None,
        "source_line": 1,
        "note": "Breakage",
        "created_by": MANAGER_ID,
        "occurred_at": None,
    }
    assert movement["occurred_at"].endswith("+07:00")


def test_adjustment_refuses_zero_and_unknown_skus(manager):
    zero = manager.post("/adjustments", adjustment(qty_delta=0), format="json")
    unknown = manager.post("/adjustments", adjustment(sku="TEST-NOPE"), format="json")

    assert zero.status_code == 400
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "UNKNOWN_SKU"


def test_ad_hoc_receipt_writes_one_receipt_movement_per_line(manager):
    body = receipt_body(lines=[{"sku": COLA, "qty": 48}, {"sku": BREAD, "qty": 6}])

    response = manager.post("/receipts", body, format="json")

    assert response.status_code == 201
    receipt = response.json()
    assert receipt["po_id"] is None
    assert receipt["received_by"] == MANAGER_ID
    movements = StockMovement.objects.filter(source_ref=receipt["receipt_id"]).order_by("source_line")
    assert [(m.sku, m.qty_delta, m.reason, m.source_line) for m in movements] == [
        (COLA, 48, "RECEIPT", 1),
        (BREAD, 6, "RECEIPT", 2),
    ]
    assert (on_hand(COLA), on_hand(BREAD)) == (48, 6)


def test_receipt_refuses_a_po_and_repeated_skus(manager):
    po = receipt_body(po_id=str(uuid.uuid4()))
    twice = receipt_body(lines=[{"sku": COLA, "qty": 1}, {"sku": COLA, "qty": 2}])

    assert manager.post("/receipts", po, format="json").json()["error"]["code"] == "VALIDATION_ERROR"
    assert manager.post("/receipts", twice, format="json").status_code == 400
    assert not StockMovement.objects.filter(branch_id=BRANCH).exists()


def test_every_endpoint_is_scoped_to_the_managers_branches():
    elsewhere = client_for(BRANCH_MANAGER, OTHER_BRANCH)
    cashier = client_for(CASHIER)

    for client in (elsewhere, cashier):
        assert client.get("/stock", {"branch_id": BRANCH}).status_code == 403
        assert client.get(f"/stock/{BRANCH}/{COLA}/movements").status_code == 403
        adjust = {"branch_id": BRANCH, "sku": COLA, "qty_delta": 1}
        assert client.post("/adjustments", adjust, format="json").status_code == 403
        receive = {"branch_id": BRANCH, "lines": [{"sku": COLA, "qty": 1}]}
        assert client.post("/receipts", receive, format="json").status_code == 403


def test_a_sku_longer_than_40_characters_is_refused(manager):
    long_sku = "TEST-" + "X" * 36

    adjusted = manager.post("/adjustments", adjustment(sku=long_sku), format="json")
    received = manager.post("/receipts", receipt_body(lines=[{"sku": long_sku, "qty": 1}]), format="json")
    stock = manager.get("/stock", {"branch_id": BRANCH, "sku": long_sku})

    assert (adjusted.status_code, received.status_code, stock.status_code) == (400, 400, 400)


def test_an_adjustment_sent_twice_moves_stock_once(manager):
    body = adjustment(qty_delta=-2)

    first = manager.post("/adjustments", body, format="json")
    again = manager.post("/adjustments", body | {"qty_delta": 5}, format="json")
    elsewhere = client_for(BRANCH_MANAGER, OTHER_BRANCH).post(
        "/adjustments", body | {"branch_id": OTHER_BRANCH}, format="json"
    )

    assert (first.status_code, again.status_code, elsewhere.status_code) == (201, 200, 409)
    assert again.json() == first.json()
    assert StockMovement.objects.filter(source_ref=body["adjustment_id"]).count() == 1
    assert on_hand(COLA) == -2


def test_a_receipt_sent_twice_receives_once(manager):
    body = receipt_body(lines=[{"sku": COLA, "qty": 48}])

    first = manager.post("/receipts", body, format="json")
    again = manager.post("/receipts", body, format="json")

    assert (first.status_code, again.status_code) == (201, 200)
    assert again.json() == first.json()
    assert StockMovement.objects.filter(source_ref=body["receipt_id"]).count() == 1
    assert on_hand(COLA) == 48
