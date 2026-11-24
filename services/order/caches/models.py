"""Event-fed copies of Catalog data that the POS reads (design doc §5.4, §5.6)."""

from django.db import models


class ProductCache(models.Model):
    """Copy of product.upserted (owner: Catalog)."""

    sku = models.CharField(primary_key=True, max_length=50)
    barcode = models.CharField(max_length=50, unique=True, null=True, blank=True)
    name = models.CharField(max_length=200)
    active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "product_cache"
        ordering = ["sku"]


class PriceCache(models.Model):
    """Copy of price.changed. Price rule (§5.2): latest valid_from <= date for the branch, else for ALL."""

    ALL_BRANCHES = "ALL"

    pk = models.CompositePrimaryKey("sku", "branch_scope", "valid_from")
    # No FK to product_cache: price.changed and product.upserted are separate topics and may arrive in either order.
    sku = models.CharField(max_length=50)
    branch_scope = models.CharField(max_length=10)  # a branch_id or "ALL"
    valid_from = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "price_cache"
        constraints = [
            models.CheckConstraint(name="price_cache_amount_non_negative", condition=models.Q(amount__gte=0)),
        ]
