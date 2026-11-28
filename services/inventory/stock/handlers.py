from retail_common.consumer import handles

from .ledger import Cause, move_stock
from .models import MovementReason


def apply_order(event: dict, reason: str, sign: int, at_field: str) -> None:
    p = event["payload"]
    for line in p["lines"]:
        cause = Cause(reason, p["order_id"], line["line_no"])
        move_stock(p["branch_id"], line["sku"], sign * line["qty"], cause, p[at_field])


@handles("order.completed")
def on_order_completed(event: dict) -> None:
    apply_order(event, MovementReason.SALE, -1, "completed_at")


@handles("order.refunded")
def on_order_refunded(event: dict) -> None:
    apply_order(event, MovementReason.REFUND, +1, "refunded_at")
