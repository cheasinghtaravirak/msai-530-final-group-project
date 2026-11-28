"""Event-fed read-only copies of data owned by other services (design doc §5.3, §5.6)."""

from django.db import models

from retail_common.models import SKU_MAX_LENGTH


class BranchRef(models.Model):
    """Copy of branch.upserted (owner: Admin)."""

    branch_id = models.CharField(primary_key=True, max_length=10)
    name = models.CharField(max_length=200)
    status = models.CharField(max_length=10)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "branch_ref"
        ordering = ["branch_id"]


class SkuRef(models.Model):
    sku = models.CharField(primary_key=True, max_length=SKU_MAX_LENGTH)
    name = models.CharField(max_length=200)
    category_id = models.UUIDField()
    pack_size = models.PositiveIntegerField(default=1)
    active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sku_ref"
        ordering = ["sku"]
