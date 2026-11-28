import uuid
from datetime import date, timedelta

import pytest
import reporting.handlers  # noqa: F401
from reporting import rollups, views
from reporting.models import AggSalesDaily, AggSalesMonthly, DirtyDay, FactSalesLine, FactStockDaily, StockCurrent
from rest_framework.test import APIClient

from retail_common.auth import BRANCH_MANAGER, CASHIER, TokenUser
from retail_common.consumer import apply_event
from retail_common.events import build_envelope

pytestmark = pytest.mark.django_db

BRANCH, OTHER_BRANCH = "BR-9901", "BR-9902"
COLA, BREAD = "TEST-COLA", "TEST-BREAD"
TODAY = date(2026, 3, 10)
LATE_DAY = date(2026, 2, 20)


def completed(day, lines=((COLA, 2, "3.40"), (BREAD, 1, "1.50")), order_id=None):
    payload = {
        "order_id": order_id or str(uuid.uuid4()),
        "branch_id": BRANCH,
        "channel": "POS",
        "sale_date": day.isoformat(),
        "lines": [{"line_no": n, "sku": s, "qty": q, "line_total": t} for n, (s, q, t) in enumerate(lines, 1)],
    }
    return build_envelope("order.completed", payload)


def refunded(sale, day):
    p = sale["payload"]
    return build_envelope("order.refunded", p | {"refund_date": day.isoformat()})


def stock_adjusted(version, on_hand):
    payload = {"branch_id": BRANCH, "sku": COLA, "qty_delta": -1, "reason": "SALE", "on_hand": on_hand}
    return build_envelope("stock.adjusted", payload | {"on_order": 0, "version": version, "occurred_at": "x"})


def daily(day):
    return {
        row["sku"]: (row["units"], str(row["revenue"]), row["order_count"], row["status"])
        for row in AggSalesDaily.objects.filter(branch_id=BRANCH, sale_date=day).values()
    }


def test_fact_insert_is_idempotent_even_for_a_reread_event():
    sale = completed(LATE_DAY)

    apply_event(sale)
    apply_event(sale | {"event_id": str(uuid.uuid4())})

    rows = FactSalesLine.objects.filter(order_id=sale["payload"]["order_id"])
    assert sorted((r.line_no, r.entry_type, r.qty, str(r.net_amount)) for r in rows) == [
        (1, "SALE", 2, "3.40"),
        (2, "SALE", 1, "1.50"),
    ]


def test_a_late_event_marks_its_day_dirty_and_day_close_recomputes_it():
    apply_event(completed(LATE_DAY))
    rollups.day_close(TODAY)
    assert daily(LATE_DAY) == {COLA: (2, "3.40", 1, "FINAL"), BREAD: (1, "1.50", 1, "FINAL")}

    late = completed(LATE_DAY, lines=((COLA, 1, "1.70"),))
    apply_event(late)
    assert DirtyDay.objects.filter(branch_id=BRANCH, sale_date=LATE_DAY).exists()

    rollups.day_close(TODAY)

    assert daily(LATE_DAY) == {COLA: (3, "5.10", 2, "FINAL"), BREAD: (1, "1.50", 1, "FINAL")}
    assert not DirtyDay.objects.filter(branch_id=BRANCH, sale_date=LATE_DAY).exists()
    month = AggSalesMonthly.objects.get(branch_id=BRANCH, month="2026-02")
    assert (str(month.revenue), month.units, month.orders, str(month.avg_basket), month.status) == (
        "6.60",
        4,
        2,
        "3.30",
        "FINAL",
    )


def test_a_refund_counts_on_its_own_day_and_keeps_the_order_count():
    sale_day, refund_day = TODAY - timedelta(days=2), TODAY - timedelta(days=1)
    sale = completed(sale_day)
    apply_event(sale)
    apply_event(refunded(sale, refund_day))

    rollups.day_close(TODAY)

    assert daily(sale_day) == {COLA: (2, "3.40", 1, "PROVISIONAL"), BREAD: (1, "1.50", 1, "PROVISIONAL")}
    assert daily(refund_day) == {COLA: (-2, "-3.40", 0, "PROVISIONAL"), BREAD: (-1, "-1.50", 0, "PROVISIONAL")}
    assert AggSalesMonthly.objects.get(branch_id=BRANCH, month="2026-03").orders == 1


def test_stock_current_keeps_only_the_newest_version_and_day_close_snapshots_it():
    apply_event(stock_adjusted(version=3, on_hand=7))
    apply_event(stock_adjusted(version=2, on_hand=9))

    assert StockCurrent.objects.get(branch_id=BRANCH, sku=COLA).on_hand == 7
    apply_event(stock_adjusted(version=4, on_hand=0))
    rollups.day_close(TODAY)

    snapshot = FactStockDaily.objects.get(branch_id=BRANCH, sku=COLA, stock_date=TODAY - timedelta(days=1))
    assert (snapshot.closing_on_hand, snapshot.stockout_flag) == (0, True)


def test_month_orders_count_only_the_closed_days_its_revenue_covers():
    apply_event(completed(TODAY - timedelta(days=1)))
    apply_event(completed(TODAY))
    rollups.day_close(TODAY)

    rollups.recompute_month(BRANCH, "2026-03", TODAY)

    month = AggSalesMonthly.objects.get(branch_id=BRANCH, month="2026-03")
    assert (month.orders, str(month.revenue), str(month.avg_basket)) == (1, "4.90", "4.90")


def test_month_close_marks_a_month_final_only_when_all_its_days_are():
    apply_event(completed(LATE_DAY))
    rollups.day_close(TODAY)
    AggSalesDaily.objects.filter(branch_id=BRANCH, sale_date=LATE_DAY).update(status="PROVISIONAL")

    rollups.month_close(TODAY)

    assert AggSalesMonthly.objects.get(branch_id=BRANCH, month="2026-02").status == "PROVISIONAL"


def client_for(role, branch_id=BRANCH):
    client = APIClient()
    client.force_authenticate(TokenUser(id=str(uuid.uuid4()), roles=[{"role": role, "branch_id": branch_id}]))
    return client


def test_daily_report_reads_today_live_and_past_days_from_the_rollup(monkeypatch):
    monkeypatch.setattr(views.timezone, "localdate", lambda: TODAY)
    yesterday = TODAY - timedelta(days=1)
    apply_event(completed(yesterday))
    rollups.day_close(TODAY)
    kept, returned = completed(TODAY), completed(TODAY, lines=((COLA, 1, "1.70"),))
    for event in (kept, returned, refunded(returned, TODAY)):
        apply_event(event)

    response = client_for(BRANCH_MANAGER).get(
        "/reports/sales", {"branch_id": BRANCH, "grain": "day", "from": yesterday, "to": TODAY}
    )

    assert response.status_code == 200
    assert response.json() == {
        "results": [
            {
                "period": TODAY.isoformat(),
                "branch_id": BRANCH,
                "revenue": "4.90",
                "units": 3,
                "orders": 2,
                "avg_basket": "2.45",
                "status": "PROVISIONAL",
            },
            {
                "period": yesterday.isoformat(),
                "branch_id": BRANCH,
                "revenue": "4.90",
                "units": 3,
                "orders": 1,
                "avg_basket": "4.90",
                "status": "PROVISIONAL",
            },
        ],
        "count": 2,
    }


def test_today_has_a_row_of_zeros_before_the_first_sale():
    rows = client_for(BRANCH_MANAGER).get("/reports/sales", {"branch_id": BRANCH, "grain": "day"}).json()["results"]

    assert [(r["revenue"], r["units"], r["orders"], r["avg_basket"]) for r in rows] == [("0.00", 0, 0, "0.00")]


def test_daily_report_is_branch_scoped_and_phase_3_only():
    manager = client_for(BRANCH_MANAGER)

    assert manager.get("/reports/sales", {"branch_id": OTHER_BRANCH, "grain": "day"}).status_code == 403
    assert client_for(CASHIER).get("/reports/sales", {"branch_id": BRANCH, "grain": "day"}).status_code == 403
    month = manager.get("/reports/sales", {"branch_id": BRANCH, "grain": "month"})
    assert (month.status_code, month.json()["error"]["code"]) == (400, "VALIDATION_ERROR")
    too_long = manager.get("/reports/sales", {"branch_id": BRANCH, "grain": "day", "from": "2025-01-01"})
    assert too_long.status_code == 400
