import uuid

from django.db import models
from django.db.models import F, Q


class Channel(models.TextChoices):
    POS = "POS"


class OrderStatus(models.TextChoices):
    COMPLETED = "COMPLETED"
    REFUNDED = "REFUNDED"


class PaymentMethod(models.TextChoices):
    CASH = "CASH"
    CARD = "CARD"
    QR = "QR"


class SalesOrder(models.Model):
    order_id = models.UUIDField(primary_key=True)
    branch_id = models.CharField(max_length=10)
    cashier_id = models.UUIDField()
    channel = models.CharField(max_length=10, choices=Channel.choices, default=Channel.POS)
    status = models.CharField(max_length=10, choices=OrderStatus.choices, default=OrderStatus.COMPLETED)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    completed_at = models.DateTimeField()
    sale_date = models.DateField()
    refunded_at = models.DateTimeField(null=True, blank=True)
    refund_date = models.DateField(null=True, blank=True)
    refunded_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "sales_order"
        ordering = ["-completed_at"]
        indexes = [models.Index(fields=["branch_id", "sale_date"], name="sales_order_branch_day")]
        constraints = [
            models.CheckConstraint(name="sales_order_channel_valid", condition=Q(channel__in=Channel.values)),
            models.CheckConstraint(name="sales_order_total_non_negative", condition=Q(total_amount__gte=0)),
            models.CheckConstraint(
                name="sales_order_refund_state",
                condition=Q(
                    status=OrderStatus.COMPLETED,
                    refunded_at__isnull=True,
                    refund_date__isnull=True,
                    refunded_by__isnull=True,
                )
                | Q(
                    status=OrderStatus.REFUNDED,
                    refunded_at__isnull=False,
                    refund_date__isnull=False,
                    refunded_by__isnull=False,
                ),
            ),
        ]


class OrderLine(models.Model):
    pk = models.CompositePrimaryKey("order_id", "line_no")
    order = models.ForeignKey(
        SalesOrder, on_delete=models.PROTECT, related_name="lines", db_column="order_id", db_index=False
    )
    line_no = models.PositiveSmallIntegerField()
    sku = models.CharField(max_length=50)
    product_name_snapshot = models.CharField(max_length=200)
    unit_price_snapshot = models.DecimalField(max_digits=12, decimal_places=2)
    qty = models.PositiveIntegerField()
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "order_line"
        ordering = ["order_id", "line_no"]
        constraints = [
            models.CheckConstraint(name="order_line_line_no_positive", condition=Q(line_no__gt=0)),
            models.CheckConstraint(name="order_line_qty_positive", condition=Q(qty__gt=0)),
            models.CheckConstraint(name="order_line_price_non_negative", condition=Q(unit_price_snapshot__gte=0)),
            models.CheckConstraint(
                name="order_line_total_matches", condition=Q(line_total=F("unit_price_snapshot") * F("qty"))
            ),
        ]


class Payment(models.Model):
    payment_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(SalesOrder, on_delete=models.PROTECT, related_name="payments", db_column="order_id")
    method = models.CharField(max_length=10, choices=PaymentMethod.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        db_table = "payment"
        constraints = [
            models.CheckConstraint(name="payment_method_valid", condition=Q(method__in=PaymentMethod.values)),
            models.CheckConstraint(name="payment_amount_positive", condition=Q(amount__gt=0)),
        ]
