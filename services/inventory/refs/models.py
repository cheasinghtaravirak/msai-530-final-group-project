"""Event-fed read-only copies of data owned by other services (design doc §5.3, §5.6)."""

from django.db import models


class BranchRef(models.Model):
    """Copy of branch.upserted (owner: Admin)."""

    branch_id = models.CharField(primary_key=True, max_length=10)
    name = models.CharField(max_length=200)
    status = models.CharField(max_length=10)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "branch_ref"
        ordering = ["branch_id"]
