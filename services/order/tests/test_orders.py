import uuid
from datetime import date, timedelta
from decimal import Decimal

import httpx
import pytest
from caches.models import BranchRef, PriceCache, ProductCache
from django.conf import settings
from django.utils import timezone
from rest_framework.test import APIClient
from sales import orders
from sales.models import SalesOrder

from retail_common.auth import BRANCH_MANAGER, CASHIER, TokenUser
from retail_common.models import Outbox

pytestmark = pytest.mark.django_db

BRANCH = "BR-9901"
OTHER_BRANCH = "BR-9902"
COLA, BREAD, UNCACHED = "TEST-COLA", "TEST-BREAD", "TEST-NEW"
CASHIER_ID = "5b0d7f4e-0000-4000-8000-0000000000c1"
MANAGER_ID = "5b0d7f4e-0000-4000-8000-0000000000a1"


def client_for(user_id, role, branch_id=BRANCH):
    client = APIClient()
    client.force_authenticate(TokenUser(id=user_id, roles=[{"role": role, "branch_id": branch_id}]))
    return client


@pytest.fixture
def cashier():
    return client_for(CASHIER_ID, CASHIER)


@pytest.fixture
def manager():
    return client_for(MANAGER_ID, BRANCH_MANAGER)


@pytest.fixture(autouse=True)
def priced_items():
    ProductCache.objects.create(sku=COLA, name="Test cola", barcode="0000000000017")
    ProductCache.objects.create(sku=BREAD, name="Test bread", barcode="0000000000024")
    PriceCache.objects.create(sku=COLA, branch_scope="ALL", valid_from=date(2025, 1, 1), amount="1.70")
    PriceCache.objects.create(sku=BREAD, branch_scope="ALL", valid_from=date(2025, 1, 1), amount="1.50")


@pytest.fixture(autouse=True)
def catalog_down(monkeypatch):
    def refuse(*args, **kwargs):
        raise httpx.ConnectError("catalog is down")

    monkeypatch.setattr(orders.httpx, "get", refuse)


def sale(lines=None, paid="4.90", order_id=None, branch_id=BRANCH):
    return {
        "order_id": order_id or str(uuid.uuid4()),
        "branch_id": branch_id,
        "lines": lines or [{"sku": COLA, "qty": 2}, {"sku": BREAD, "qty": 1}],
        "payments": [{"method": "CASH", "amount": paid}],
    }


def events(event_type, order_id):
    return [row.envelope["payload"] for row in Outbox.objects.filter(event_type=event_type, key=order_id)]


def test_sale_is_stored_completed_with_its_event(cashier):
    body = sale()

    response = cashier.post("/orders", body, format="json")

    assert response.status_code == 201
    order = response.json()
    assert order["status"] == "COMPLETED"
    assert order["total_amount"] == "4.90"
    assert order["cashier_id"] == CASHIER_ID
    assert order["sale_date"] == timezone.localdate().isoformat()
    assert order["lines"] == [
        {"line_no": 1, "sku": COLA, "name": "Test cola", "unit_price": "1.70", "qty": 2, "line_total": "3.40"},
        {"line_no": 2, "sku": BREAD, "name": "Test bread", "unit_price": "1.50", "qty": 1, "line_total": "1.50"},
    ]
    assert order["payments"] == [{"method": "CASH", "amount": "4.90"}]
    [event] = events("order.completed", body["order_id"])
    assert event["total_amount"] == "4.90"
    assert event["sale_date"] == order["sale_date"]
    assert event["completed_at"].endswith("+07:00")
    assert event["lines"] == [
        {"line_no": 1, "sku": COLA, "qty": 2, "unit_price": "1.70", "line_total": "3.40"},
        {"line_no": 2, "sku": BREAD, "qty": 1, "unit_price": "1.50", "line_total": "1.50"},
    ]


def test_same_order_id_twice_gives_one_order_and_one_event(cashier):
    body = sale()

    first = cashier.post("/orders", body, format="json")
    retry = cashier.post("/orders", body, format="json")

    assert (first.status_code, retry.status_code) == (201, 200)
    assert retry.json() == first.json()
    assert SalesOrder.objects.filter(pk=body["order_id"]).count() == 1
    assert len(events("order.completed", body["order_id"])) == 1


def test_an_order_id_from_another_branch_is_not_handed_out(cashier):
    body = sale()
    cashier.post("/orders", body, format="json")
    elsewhere = client_for(CASHIER_ID, CASHIER, OTHER_BRANCH)

    response = elsewhere.post("/orders", body | {"branch_id": OTHER_BRANCH}, format="json")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ORDER_ID_CONFLICT"


def test_server_ignores_client_prices(cashier):
    body = sale(lines=[{"sku": COLA, "qty": 2, "unit_price": "0.01", "line_total": "0.02"}], paid="3.40")
    body["total_amount"] = "0.02"

    order = cashier.post("/orders", body, format="json").json()

    assert order["total_amount"] == "3.40"
    assert order["lines"][0]["unit_price"] == "1.70"


def test_payment_that_differs_from_the_total_is_refused(cashier):
    body = sale(paid="4.00")

    response = cashier.post("/orders", body, format="json")

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "PAYMENT_MISMATCH"
    assert error["details"]["total_amount"] == "4.90"
    assert {"sku": COLA, "unit_price": "1.70"} in error["details"]["lines"]
    assert not SalesOrder.objects.filter(pk=body["order_id"]).exists()
    assert events("order.completed", body["order_id"]) == []


def test_uncached_sku_is_priced_by_catalog(cashier, monkeypatch):
    calls = []

    def catalog(url, *, params, headers, timeout):
        calls.append((url, params, headers["X-Service-Token"], timeout))
        return httpx.Response(
            200, json={"sku": UNCACHED, "name": "Test new item", "amount": "2.25"}, request=httpx.Request("GET", url)
        )

    monkeypatch.setattr(orders.httpx, "get", catalog)

    response = cashier.post("/orders", sale(lines=[{"sku": UNCACHED, "qty": 2}], paid="4.50"), format="json")

    assert response.status_code == 201
    assert response.json()["lines"][0] | {"line_no": 1} == {
        "line_no": 1,
        "sku": UNCACHED,
        "name": "Test new item",
        "unit_price": "2.25",
        "qty": 2,
        "line_total": "4.50",
    }
    assert calls == [(f"{settings.CATALOG_URL}/prices/{UNCACHED}", {"branch_id": BRANCH}, settings.SERVICE_TOKEN, 0.3)]


def test_uncached_sku_is_refused_when_catalog_times_out(cashier, monkeypatch):
    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("300 ms passed")

    monkeypatch.setattr(orders.httpx, "get", timeout)
    body = sale(lines=[{"sku": UNCACHED, "qty": 1}], paid="1.00")

    response = cashier.post("/orders", body, format="json")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PRICE_UNAVAILABLE"
    assert response.json()["error"]["details"] == {"sku": UNCACHED}
    assert not SalesOrder.objects.filter(pk=body["order_id"]).exists()


def test_cached_sku_sells_while_catalog_is_down(cashier):
    assert cashier.post("/orders", sale(), format="json").status_code == 201


def test_discontinued_sku_is_refused(cashier):
    ProductCache.objects.filter(sku=COLA).update(active=False)

    response = cashier.post("/orders", sale(), format="json")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "ITEM_NOT_FOUND"


def test_branch_outside_the_token_is_refused(cashier):
    response = cashier.post("/orders", sale(branch_id=OTHER_BRANCH), format="json")
    assert response.status_code == 403
    assert cashier.get("/orders", {"branch_id": OTHER_BRANCH}).status_code == 403


def test_closed_branch_cannot_sell(cashier):
    BranchRef.objects.create(branch_id=BRANCH, status="CLOSED", timezone="Asia/Phnom_Penh")

    response = cashier.post("/orders", sale(), format="json")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "BRANCH_CLOSED"


def test_sale_date_is_the_branch_local_date(cashier):
    BranchRef.objects.create(branch_id=BRANCH, status="OPEN", timezone="Pacific/Kiritimati")
    far_east = timezone.now().astimezone(tz=__import__("zoneinfo").ZoneInfo("Pacific/Kiritimati")).date()

    order = cashier.post("/orders", sale(), format="json").json()

    assert order["sale_date"] == far_east.isoformat()


def test_refund_moves_the_order_to_refunded_once(cashier, manager):
    body = sale()
    cashier.post("/orders", body, format="json")

    first = manager.post(f"/orders/{body['order_id']}/refund")
    again = manager.post(f"/orders/{body['order_id']}/refund")

    assert (first.status_code, again.status_code) == (200, 200)
    assert first.json()["status"] == "REFUNDED"
    assert first.json()["refund_date"] == timezone.localdate().isoformat()
    assert again.json() == first.json()
    assert SalesOrder.objects.get(pk=body["order_id"]).refunded_by == uuid.UUID(MANAGER_ID)
    [event] = events("order.refunded", body["order_id"])
    assert event["refund_date"] == first.json()["refund_date"]
    assert event["lines"] == [
        {"line_no": 1, "sku": COLA, "qty": 2, "line_total": "3.40"},
        {"line_no": 2, "sku": BREAD, "qty": 1, "line_total": "1.50"},
    ]


def test_only_this_branchs_manager_refunds(cashier):
    body = sale()
    cashier.post("/orders", body, format="json")
    path = f"/orders/{body['order_id']}/refund"

    assert cashier.post(path).status_code == 403
    assert client_for(MANAGER_ID, BRANCH_MANAGER, OTHER_BRANCH).post(path).status_code == 403
    assert SalesOrder.objects.get(pk=body["order_id"]).status == "COMPLETED"


def test_orders_are_listed_by_branch_and_date_and_read_by_id(cashier):
    body = sale()
    cashier.post("/orders", body, format="json")

    listed = cashier.get("/orders", {"branch_id": BRANCH}).json()
    yesterday = cashier.get("/orders", {"branch_id": BRANCH, "date": timezone.localdate() - timedelta(days=1)}).json()
    one = cashier.get(f"/orders/{body['order_id']}")

    assert [o["order_id"] for o in listed["results"]] == [body["order_id"]]
    assert listed["count"] == 1
    assert yesterday["count"] == 0
    assert one.json() == listed["results"][0]
    assert client_for(CASHIER_ID, CASHIER, OTHER_BRANCH).get(f"/orders/{body['order_id']}").status_code == 403
    assert cashier.get(f"/orders/{uuid.uuid4()}").status_code == 404


def test_sales_summary_needs_the_service_token_and_nets_refunds(cashier, manager):
    kept, returned = sale(), sale(lines=[{"sku": COLA, "qty": 1}], paid="1.70")
    cashier.post("/orders", kept, format="json")
    cashier.post("/orders", returned, format="json")
    manager.post(f"/orders/{returned['order_id']}/refund")
    today = timezone.localdate().isoformat()

    assert APIClient().get("/internal/sales-summary", {"date": today}).status_code in (401, 403)
    assert cashier.get("/internal/sales-summary", {"date": today}).status_code == 403
    response = APIClient().get(
        "/internal/sales-summary", {"date": today}, headers={"X-Service-Token": settings.SERVICE_TOKEN}
    )

    ours = [row for row in response.json() if row["branch_id"] == BRANCH]
    assert ours == [{"branch_id": BRANCH, "order_count": 2, "total_amount": str(Decimal("4.90"))}]
