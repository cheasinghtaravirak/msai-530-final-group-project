"""Reporting schema (design doc §5.5): dimensions, facts and rollups."""

from django.db import models
from django.db.models import Q


class Status(models.TextChoices):
    PROVISIONAL = "PROVISIONAL"
    FINAL = "FINAL"


class DimBranch(models.Model):
    """Copy of branch.upserted (owner: Admin)."""

    branch_id = models.CharField(primary_key=True, max_length=10)
    name = models.CharField(max_length=200)
    region = models.CharField(max_length=50)
    status = models.CharField(max_length=10)

    class Meta:
        db_table = "dim_branch"
        ordering = ["branch_id"]


class DimProduct(models.Model):
    """Copy of product.upserted (owner: Catalog)."""

    sku = models.CharField(primary_key=True, max_length=40)
    name = models.CharField(max_length=200)
    category_id = models.UUIDField()
    category_name = models.CharField(max_length=100)
    brand = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        db_table = "dim_product"
        ordering = ["sku"]


class Calendar(models.Model):
    calendar_date = models.DateField(primary_key=True)
    iso_week = models.PositiveSmallIntegerField()
    weekday = models.PositiveSmallIntegerField()  # ISO: Monday = 1 ... Sunday = 7
    is_holiday = models.BooleanField(default=False)

    class Meta:
        db_table = "calendar"
        ordering = ["calendar_date"]
        constraints = [
            models.CheckConstraint(condition=Q(weekday__range=(1, 7)), name="calendar_weekday_iso"),
            models.CheckConstraint(condition=Q(iso_week__range=(1, 53)), name="calendar_iso_week_range"),
        ]


class FactSalesLine(models.Model):
    """One row per order line and entry type. Written with ON CONFLICT DO NOTHING (design doc §8.2)."""

    class EntryType(models.TextChoices):
        SALE = "SALE"
        REFUND = "REFUND"

    class Channel(models.TextChoices):
        POS = "POS"

    pk = models.CompositePrimaryKey("order_id", "line_no", "entry_type")
    order_id = models.UUIDField()
    line_no = models.PositiveSmallIntegerField()
    entry_type = models.CharField(max_length=6, choices=EntryType.choices)
    branch_id = models.CharField(max_length=10)
    sku = models.CharField(max_length=40)
    channel = models.CharField(max_length=10, choices=Channel.choices, default=Channel.POS)
    sale_date = models.DateField()  # the day the sale or refund counts on
    qty = models.IntegerField()  # negative for REFUND
    net_amount = models.DecimalField(max_digits=12, decimal_places=2)  # negative for REFUND
    event_id = models.UUIDField(null=True, blank=True)  # null for bulk-loaded history

    class Meta:
        db_table = "fact_sales_line"
        indexes = [models.Index(fields=["branch_id", "sale_date"], name="fact_sales_branch_day_idx")]
        constraints = [
            models.CheckConstraint(
                condition=(Q(entry_type="SALE", qty__gt=0, net_amount__gte=0))
                | Q(entry_type="REFUND", qty__lt=0, net_amount__lte=0),
                name="fact_sales_line_sign_matches_entry_type",
            ),
        ]


class StockCurrent(models.Model):
    """Latest stock.adjusted snapshot per branch and SKU; applied only when `version` is newer."""

    pk = models.CompositePrimaryKey("branch_id", "sku")
    branch_id = models.CharField(max_length=10)
    sku = models.CharField(max_length=40)
    on_hand = models.IntegerField()  # may be negative (design doc §5.3)
    on_order = models.IntegerField(default=0)
    version = models.PositiveIntegerField()

    class Meta:
        db_table = "stock_current"


class FactStockDaily(models.Model):
    pk = models.CompositePrimaryKey("branch_id", "sku", "stock_date")
    branch_id = models.CharField(max_length=10)
    sku = models.CharField(max_length=40)
    stock_date = models.DateField()
    closing_on_hand = models.IntegerField()
    stockout_flag = models.BooleanField(default=False)

    class Meta:
        db_table = "fact_stock_daily"


class DirtyDay(models.Model):
    """A (branch, day) whose rollups J2 must recompute."""

    pk = models.CompositePrimaryKey("branch_id", "sale_date")
    branch_id = models.CharField(max_length=10)
    sale_date = models.DateField()
    marked_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "dirty_day"


class AggSalesDaily(models.Model):
    pk = models.CompositePrimaryKey("branch_id", "sku", "sale_date")
    branch_id = models.CharField(max_length=10)
    sku = models.CharField(max_length=40)
    sale_date = models.DateField()
    units = models.IntegerField()
    revenue = models.DecimalField(max_digits=12, decimal_places=2)
    order_count = models.PositiveIntegerField()  # distinct orders with this SKU, not summable across SKUs
    status = models.CharField(max_length=11, choices=Status.choices, default=Status.PROVISIONAL)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "agg_sales_daily"
        indexes = [models.Index(fields=["branch_id", "sale_date"], name="agg_daily_branch_day_idx")]


class AggSalesMonthly(models.Model):
    pk = models.CompositePrimaryKey("branch_id", "month")
    branch_id = models.CharField(max_length=10)
    month = models.CharField(max_length=7)  # YYYY-MM
    revenue = models.DecimalField(max_digits=12, decimal_places=2)
    units = models.IntegerField()
    orders = models.PositiveIntegerField()
    avg_basket = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=11, choices=Status.choices, default=Status.PROVISIONAL)

    class Meta:
        db_table = "agg_sales_monthly"
        constraints = [
            models.CheckConstraint(
                condition=Q(month__regex=r"^\d{4}-(0[1-9]|1[0-2])$"), name="agg_monthly_month_format"
            ),
        ]
