import calendar
from datetime import date, timedelta
from decimal import Decimal

from django.db import connection, transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth

from .models import (
    AggSalesDaily,
    AggSalesMonthly,
    DimBranch,
    DirtyDay,
    FactSalesLine,
    FactStockDaily,
    Status,
    StockCurrent,
)

FINAL_AFTER_DAYS = 3
SALE_ORDERS = Count("order_id", distinct=True, filter=Q(entry_type=FactSalesLine.EntryType.SALE))


def day_status(day: date, today: date) -> str:
    return Status.FINAL if day < today - timedelta(days=FINAL_AFTER_DAYS) else Status.PROVISIONAL


def month_bounds(month: str) -> tuple[date, date]:
    year, number = map(int, month.split("-"))
    return date(year, number, 1), date(year, number, calendar.monthrange(year, number)[1])


def lock_until_commit(*key) -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", [":".join(map(str, key))])


@transaction.atomic
def recompute_day(branch_id: str, day: date, today: date) -> None:
    lock_until_commit("agg_sales_daily", branch_id, day)
    AggSalesDaily.objects.filter(branch_id=branch_id, sale_date=day).delete()
    per_sku = (
        FactSalesLine.objects.filter(branch_id=branch_id, sale_date=day)
        .values("sku")
        .annotate(units=Sum("qty"), revenue=Sum("net_amount"), order_count=SALE_ORDERS)
    )
    status = day_status(day, today)
    AggSalesDaily.objects.bulk_create(
        AggSalesDaily(branch_id=branch_id, sale_date=day, status=status, **row) for row in per_sku
    )


@transaction.atomic
def recompute_month(branch_id: str, month: str, today: date) -> None:
    lock_until_commit("agg_sales_monthly", branch_id, month)
    first, last = month_bounds(month)
    daily = AggSalesDaily.objects.filter(branch_id=branch_id, sale_date__range=(first, last)).aggregate(
        revenue=Sum("revenue"),
        units=Sum("units"),
        provisional=Count("sale_date", filter=Q(status=Status.PROVISIONAL)),
    )
    if daily["revenue"] is None:
        AggSalesMonthly.objects.filter(branch_id=branch_id, month=month).delete()
        return
    closed_days = AggSalesDaily.objects.filter(branch_id=branch_id, sale_date__range=(first, last)).values("sale_date")
    orders = FactSalesLine.objects.filter(branch_id=branch_id, sale_date__in=closed_days).aggregate(n=SALE_ORDERS)["n"]
    final = last < today and daily["provisional"] == 0
    AggSalesMonthly.objects.update_or_create(
        branch_id=branch_id,
        month=month,
        defaults={
            "revenue": daily["revenue"],
            "units": daily["units"],
            "orders": orders,
            "avg_basket": basket(daily["revenue"], orders),
            "status": Status.FINAL if final else Status.PROVISIONAL,
        },
    )


def clear_dirty_if_unchanged(branch_id: str, day: date, marked_at) -> None:
    DirtyDay.objects.filter(branch_id=branch_id, sale_date=day, marked_at=marked_at).delete()


def day_close(today: date) -> str:
    yesterday = today - timedelta(days=1)
    days = {
        (b, d): m
        for b, d, m in DirtyDay.objects.filter(sale_date__lt=today).values_list("branch_id", "sale_date", "marked_at")
    }
    for branch_id in DimBranch.objects.values_list("branch_id", flat=True):
        days.setdefault((branch_id, yesterday), None)
    for (branch_id, day), marked_at in sorted(days.items()):
        with transaction.atomic():
            recompute_day(branch_id, day, today)
            clear_dirty_if_unchanged(branch_id, day, marked_at)
    finalised = AggSalesDaily.objects.filter(
        sale_date__lt=today - timedelta(days=FINAL_AFTER_DAYS), status=Status.PROVISIONAL
    ).update(status=Status.FINAL)
    FactStockDaily.objects.bulk_create(
        [
            FactStockDaily(
                branch_id=s.branch_id,
                sku=s.sku,
                stock_date=yesterday,
                closing_on_hand=s.on_hand,
                stockout_flag=s.on_hand <= 0,
            )
            for s in StockCurrent.objects.all()
        ],
        update_conflicts=True,
        unique_fields=["branch_id", "sku", "stock_date"],
        update_fields=["closing_on_hand", "stockout_flag"],
    )
    months = {(branch_id, day.strftime("%Y-%m")) for branch_id, day in days}
    for branch_id, month in sorted(months):
        recompute_month(branch_id, month, today)
    return f"{len(days)} branch-days recomputed, {finalised} rows made FINAL, {len(months)} branch-months updated"


def month_close(today: date) -> str:
    months = AggSalesDaily.objects.annotate(month=TruncMonth("sale_date")).values_list("branch_id", "month").distinct()
    keys = sorted({(branch_id, month.strftime("%Y-%m")) for branch_id, month in months})
    for branch_id, month in keys:
        recompute_month(branch_id, month, today)
    return f"{len(keys)} branch-months recomputed"


def basket(revenue: Decimal, orders: int) -> Decimal:
    return (revenue / orders).quantize(Decimal("0.01")) if orders else Decimal("0.00")


def daily_sales(branch_id: str, first: date, last: date, today: date) -> list[dict]:
    facts = FactSalesLine.objects.filter(branch_id=branch_id, sale_date__range=(first, last))
    orders = dict(facts.values("sale_date").annotate(n=SALE_ORDERS).values_list("sale_date", "n"))
    days = {
        row["sale_date"]: row
        for row in AggSalesDaily.objects.filter(
            branch_id=branch_id, sale_date__range=(first, min(last, today - timedelta(days=1)))
        )
        .values("sale_date")
        .annotate(
            revenue=Sum("revenue"),
            units=Sum("units"),
            provisional=Count("sku", filter=Q(status=Status.PROVISIONAL)),
        )
    }
    for row in days.values():
        row["status"] = Status.PROVISIONAL if row["provisional"] else Status.FINAL
    if first <= today <= last:
        live = facts.filter(sale_date=today).aggregate(revenue=Sum("net_amount"), units=Sum("qty"))
        days[today] = {
            "revenue": live["revenue"] or Decimal("0.00"),
            "units": live["units"] or 0,
            "status": Status.PROVISIONAL,
        }
    return [
        {
            "period": day.isoformat(),
            "branch_id": branch_id,
            "revenue": f"{row['revenue']:.2f}",
            "units": row["units"],
            "orders": orders.get(day, 0),
            "avg_basket": f"{basket(row['revenue'], orders.get(day, 0)):.2f}",
            "status": row["status"],
        }
        for day, row in sorted(days.items(), reverse=True)
    ]
