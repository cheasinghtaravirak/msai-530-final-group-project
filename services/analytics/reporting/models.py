"""Reporting schema (design doc §5.5). Only dim_branch so far; facts and aggregates come in Phase 3."""

from django.db import models


class DimBranch(models.Model):
    """Copy of branch.upserted (owner: Admin)."""

    branch_id = models.CharField(primary_key=True, max_length=10)
    name = models.CharField(max_length=200)
    region = models.CharField(max_length=50)
    status = models.CharField(max_length=10)

    class Meta:
        db_table = "dim_branch"
        ordering = ["branch_id"]
