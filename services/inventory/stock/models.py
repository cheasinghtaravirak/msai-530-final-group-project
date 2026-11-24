"""inventory_db (design doc §5.3): stock_level, the stock_movement ledger, and transfers."""

import uuid

from django.db import models
from django.db.models import F, Q


class MovementReason(models.TextChoices):
    SALE = "SALE"
    REFUND = "REFUND"
    RECEIPT = "RECEIPT"
    ADJUST = "ADJUST"
    TRANSFER_OUT = "TRANSFER_OUT"
    TRANSFER_IN = "TRANSFER_IN"


class TransferStatus(models.TextChoices):
    REQUESTED = "REQUESTED"
    SHIPPED = "SHIPPED"
    RECEIVED = "RECEIVED"
    CANCELLED = "CANCELLED"


class StockLevel(models.Model):
    """Every change here writes one stock_movement row in the same transaction."""

    pk = models.CompositePrimaryKey("branch_id", "sku")
    branch_id = models.CharField(max_length=10)
    sku = models.CharField(max_length=50)
    # May go negative: a sale is accepted even when the count is wrong, and the manager adjusts later.
    on_hand = models.IntegerField(default=0)
    on_order = models.IntegerField(default=0)
    version = models.PositiveIntegerField(default=0)  # bumped on every change, sent in stock.adjusted
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "stock_level"
        ordering = ["branch_id", "sku"]
        constraints = [
            models.CheckConstraint(name="stock_level_on_order_non_negative", condition=Q(on_order__gte=0)),
        ]


class StockMovement(models.Model):
    movement_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch_id = models.CharField(max_length=10)
    sku = models.CharField(max_length=50)
    qty_delta = models.IntegerField()
    reason = models.CharField(max_length=20, choices=MovementReason.choices)
    source_ref = models.CharField(max_length=64)  # order_id, receipt_id or transfer_id
    source_line = models.PositiveIntegerField()
    note = models.CharField(max_length=500, blank=True, default="")
    created_by = models.UUIDField(null=True, blank=True)  # user_id; null when written by an event consumer
    occurred_at = models.DateTimeField()

    class Meta:
        db_table = "stock_movement"
        ordering = ["-occurred_at"]
        indexes = [models.Index(fields=["branch_id", "sku", "-occurred_at"], name="stock_movement_history")]
        constraints = [
            # Even if consumer idempotency failed, the same source line can't change stock twice.
            models.UniqueConstraint(
                fields=["source_ref", "source_line", "branch_id", "reason"], name="stock_movement_source_unique"
            ),
            models.CheckConstraint(name="stock_movement_reason_valid", condition=Q(reason__in=MovementReason.values)),
            models.CheckConstraint(name="stock_movement_qty_nonzero", condition=~Q(qty_delta=0)),
        ]


class Transfer(models.Model):
    transfer_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    from_branch_id = models.CharField(max_length=10)
    to_branch_id = models.CharField(max_length=10)
    recommendation_id = models.UUIDField(unique=True, null=True, blank=True)  # null when created manually
    status = models.CharField(max_length=10, choices=TransferStatus.choices, default=TransferStatus.REQUESTED)

    class Meta:
        db_table = "transfer"
        constraints = [
            models.CheckConstraint(name="transfer_status_valid", condition=Q(status__in=TransferStatus.values)),
            models.CheckConstraint(name="transfer_distinct_branches", condition=~Q(from_branch_id=F("to_branch_id"))),
        ]


class TransferLine(models.Model):
    pk = models.CompositePrimaryKey("transfer_id", "sku")
    transfer = models.ForeignKey(
        Transfer, on_delete=models.PROTECT, related_name="lines", db_column="transfer_id", db_index=False
    )
    sku = models.CharField(max_length=50)
    qty = models.PositiveIntegerField()

    class Meta:
        db_table = "transfer_line"
        constraints = [models.CheckConstraint(name="transfer_line_qty_positive", condition=Q(qty__gt=0))]
