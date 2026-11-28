import uuid

from django.db import models
from django.db.models import Q


class PoStatus(models.TextChoices):
    OPEN = "OPEN"
    PARTIAL = "PARTIAL"
    RECEIVED = "RECEIVED"
    CANCELLED = "CANCELLED"


class PurchaseOrder(models.Model):
    po_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch_id = models.CharField(max_length=10)
    supplier_id = models.UUIDField()
    recommendation_id = models.UUIDField(unique=True, null=True, blank=True)
    status = models.CharField(max_length=10, choices=PoStatus.choices, default=PoStatus.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "purchase_order"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(name="purchase_order_status_valid", condition=Q(status__in=PoStatus.values)),
        ]


class PoLine(models.Model):
    pk = models.CompositePrimaryKey("po_id", "sku")
    po = models.ForeignKey(
        PurchaseOrder, on_delete=models.PROTECT, related_name="lines", db_column="po_id", db_index=False
    )
    sku = models.CharField(max_length=50)
    qty_ordered = models.PositiveIntegerField()
    qty_received = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "po_line"
        constraints = [models.CheckConstraint(name="po_line_qty_ordered_positive", condition=Q(qty_ordered__gt=0))]


class GoodsReceipt(models.Model):
    receipt_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    po = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="receipts",
        db_column="po_id",
    )
    branch_id = models.CharField(max_length=10)
    received_by = models.UUIDField()
    received_at = models.DateTimeField()

    class Meta:
        db_table = "goods_receipt"
        ordering = ["-received_at"]


class ReceiptLine(models.Model):
    pk = models.CompositePrimaryKey("receipt_id", "sku")
    receipt = models.ForeignKey(
        GoodsReceipt, on_delete=models.PROTECT, related_name="lines", db_column="receipt_id", db_index=False
    )
    sku = models.CharField(max_length=50)
    qty = models.PositiveIntegerField()

    class Meta:
        db_table = "receipt_line"
        constraints = [models.CheckConstraint(name="receipt_line_qty_positive", condition=Q(qty__gt=0))]
