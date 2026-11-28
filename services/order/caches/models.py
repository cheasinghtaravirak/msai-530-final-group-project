from django.db import models


class BranchRef(models.Model):
    CLOSED = "CLOSED"

    branch_id = models.CharField(primary_key=True, max_length=10)
    status = models.CharField(max_length=10)
    timezone = models.CharField(max_length=50)

    class Meta:
        db_table = "branch_ref"


class ProductCache(models.Model):
    sku = models.CharField(primary_key=True, max_length=50)
    barcode = models.CharField(max_length=50, unique=True, null=True, blank=True)
    name = models.CharField(max_length=200)
    active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "product_cache"
        ordering = ["sku"]


class PriceCache(models.Model):
    ALL_BRANCHES = "ALL"

    pk = models.CompositePrimaryKey("sku", "branch_scope", "valid_from")
    # No FK to product_cache: price.changed and product.upserted are separate topics and may arrive in either order.
    sku = models.CharField(max_length=50)
    branch_scope = models.CharField(max_length=10)
    valid_from = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "price_cache"
        constraints = [
            models.CheckConstraint(name="price_cache_amount_non_negative", condition=models.Q(amount__gte=0)),
        ]
