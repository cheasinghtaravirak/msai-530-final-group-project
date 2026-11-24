import uuid
from decimal import Decimal

from django.db import models
from django.db.models import Q
from forecasting.models import ForecastRun


class StockPolicy(models.Model):
    pk = models.CompositePrimaryKey("branch_id", "category_id")
    branch_id = models.CharField(max_length=10)
    category_id = models.UUIDField()
    service_level = models.DecimalField(max_digits=4, decimal_places=3, default=Decimal("0.950"))
    review_days = models.PositiveSmallIntegerField(default=1)

    class Meta:
        db_table = "stock_policy"
        constraints = [
            models.CheckConstraint(
                condition=Q(service_level__gt=0, service_level__lt=1), name="stock_policy_service_level_range"
            ),
        ]


class SupplierTerms(models.Model):
    sku = models.CharField(primary_key=True, max_length=40)
    supplier_id = models.UUIDField()
    lead_time_days = models.PositiveSmallIntegerField()
    pack_size = models.PositiveIntegerField(default=1)
    min_order_qty = models.PositiveIntegerField(default=1)
    occurred_at = models.DateTimeField(null=True, blank=True)  # of the event that made this supplier preferred

    class Meta:
        db_table = "supplier_terms"
        constraints = [models.CheckConstraint(condition=Q(pack_size__gte=1), name="supplier_terms_pack_size_positive")]


class Recommendation(models.Model):
    class Type(models.TextChoices):
        REORDER = "REORDER"
        TRANSFER = "TRANSFER"

    class Status(models.TextChoices):
        PENDING = "PENDING"
        APPROVED = "APPROVED"
        EDITED = "EDITED"
        REJECTED = "REJECTED"
        EXPIRED = "EXPIRED"

    recommendation_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(ForecastRun, on_delete=models.PROTECT, related_name="recommendations")
    branch_id = models.CharField(max_length=10)
    sku = models.CharField(max_length=40)
    type = models.CharField(max_length=8, choices=Type.choices)
    suggested_qty = models.PositiveIntegerField()
    supplier_id = models.UUIDField(null=True, blank=True)
    source_branch_id = models.CharField(max_length=10, null=True, blank=True)
    reason = models.TextField()
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)

    class Meta:
        db_table = "recommendation"
        indexes = [models.Index(fields=["branch_id", "status"], name="rec_branch_status_idx")]
        constraints = [
            models.CheckConstraint(
                condition=Q(type="REORDER", supplier_id__isnull=False, source_branch_id__isnull=True)
                | Q(type="TRANSFER", supplier_id__isnull=True, source_branch_id__isnull=False),
                name="recommendation_target_matches_type",
            ),
            models.CheckConstraint(condition=Q(suggested_qty__gt=0), name="recommendation_qty_positive"),
            models.UniqueConstraint(
                fields=["branch_id", "sku"], condition=Q(status="PENDING"), name="recommendation_one_pending"
            ),
        ]


class Decision(models.Model):
    class Outcome(models.TextChoices):
        APPROVED = "APPROVED"
        EDITED = "EDITED"
        REJECTED = "REJECTED"

    recommendation = models.OneToOneField(
        Recommendation, primary_key=True, on_delete=models.PROTECT, related_name="decision"
    )
    decided_by = models.UUIDField()
    final_qty = models.PositiveIntegerField()
    outcome = models.CharField(max_length=8, choices=Outcome.choices)
    note = models.TextField(blank=True, default="")
    decided_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "decision"
