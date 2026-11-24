from decimal import Decimal

from django.db import connection

from retail_common.consumer import handles

from .models import DimBranch, DimProduct, DirtyDay, FactSalesLine

UPSERT_NEWER_STOCK = """
INSERT INTO stock_current (branch_id, sku, on_hand, on_order, version) VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (branch_id, sku) DO UPDATE
    SET on_hand = EXCLUDED.on_hand, on_order = EXCLUDED.on_order, version = EXCLUDED.version
    WHERE stock_current.version < EXCLUDED.version
"""


@handles("branch.upserted")
def on_branch_upserted(event: dict) -> None:
    p = event["payload"]
    DimBranch.objects.update_or_create(
        branch_id=p["branch_id"],
        defaults={"name": p["name"], "region": p["region"], "status": p["status"]},
    )


@handles("product.upserted")
def on_product_upserted(event: dict) -> None:
    p = event["payload"]
    DimProduct.objects.update_or_create(
        sku=p["sku"],
        defaults={
            "name": p["name"],
            "category_id": p["category_id"],
            "category_name": p["category_name"],
            "brand": p["brand"],
        },
    )


def record_sales_lines(event: dict, entry_type: str, sign: int, day: str) -> None:
    """Facts are keyed by (order_id, line_no, entry_type), so a re-read event adds nothing."""
    p = event["payload"]
    FactSalesLine.objects.bulk_create(
        [
            FactSalesLine(
                order_id=p["order_id"],
                line_no=line["line_no"],
                entry_type=entry_type,
                branch_id=p["branch_id"],
                sku=line["sku"],
                channel=p.get("channel", FactSalesLine.Channel.POS),
                sale_date=day,
                qty=sign * line["qty"],
                net_amount=sign * Decimal(line["line_total"]),
                event_id=event["event_id"],
            )
            for line in p["lines"]
        ],
        ignore_conflicts=True,
    )
    DirtyDay.objects.bulk_create(
        [DirtyDay(branch_id=p["branch_id"], sale_date=day)],
        update_conflicts=True,
        unique_fields=["branch_id", "sale_date"],
        update_fields=["marked_at"],
    )


@handles("order.completed")
def on_order_completed(event: dict) -> None:
    record_sales_lines(event, FactSalesLine.EntryType.SALE, +1, event["payload"]["sale_date"])


@handles("order.refunded")
def on_order_refunded(event: dict) -> None:
    record_sales_lines(event, FactSalesLine.EntryType.REFUND, -1, event["payload"]["refund_date"])


@handles("stock.adjusted")
def on_stock_adjusted(event: dict) -> None:
    p = event["payload"]
    with connection.cursor() as cursor:
        cursor.execute(UPSERT_NEWER_STOCK, [p["branch_id"], p["sku"], p["on_hand"], p["on_order"], p["version"]])
