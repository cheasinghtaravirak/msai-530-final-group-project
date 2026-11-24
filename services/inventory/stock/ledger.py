from dataclasses import dataclass
from datetime import datetime

from django.db import connection, transaction

from retail_common.events import publish_event

from .models import StockLevel

MOVE = """
WITH movement AS (
    INSERT INTO stock_movement
        (movement_id, branch_id, sku, qty_delta, reason, source_ref, source_line, note, created_by, occurred_at)
    VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (source_ref, source_line, branch_id, reason) DO NOTHING
    RETURNING branch_id, sku, qty_delta
)
INSERT INTO stock_level (branch_id, sku, on_hand, on_order, version, updated_at)
SELECT branch_id, sku, qty_delta, 0, 1, now() FROM movement
ON CONFLICT (branch_id, sku) DO UPDATE
    SET on_hand = stock_level.on_hand + EXCLUDED.on_hand, version = stock_level.version + 1, updated_at = now()
RETURNING on_hand, on_order, version
"""


@dataclass(frozen=True)
class Cause:
    reason: str
    source_ref: str
    source_line: int


def move_stock(
    branch_id: str,
    sku: str,
    qty_delta: int,
    cause: Cause,
    occurred_at: datetime | str,
    *,
    note: str = "",
    created_by: str | None = None,
) -> StockLevel | None:
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            MOVE,
            [
                branch_id,
                sku,
                qty_delta,
                cause.reason,
                str(cause.source_ref),
                cause.source_line,
                note,
                created_by,
                occurred_at,
            ],
        )
        row = cursor.fetchone()
        if row is None:
            return None
        on_hand, on_order, version = row
        publish_event(
            "stock.adjusted",
            {
                "branch_id": branch_id,
                "sku": sku,
                "qty_delta": qty_delta,
                "reason": cause.reason,
                "on_hand": on_hand,
                "on_order": on_order,
                "version": version,
                "occurred_at": occurred_at,
            },
            key=f"{branch_id}:{sku}",
        )
    return StockLevel(branch_id=branch_id, sku=sku, on_hand=on_hand, on_order=on_order, version=version)
