import uuid

from django.db import models
from django.db.models import Q

ALL_BRANCHES = "ALL"


class Category(models.Model):
    category_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="children", db_column="parent_id"
    )
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = "category"
        ordering = ["name"]


class Product(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE"
        DISCONTINUED = "DISCONTINUED"

    product_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products", db_column="category_id")
    name = models.CharField(max_length=200)
    brand = models.CharField(max_length=100, blank=True, default="")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        db_table = "product"
        ordering = ["name"]


class Sku(models.Model):
    class Unit(models.TextChoices):
        EA = "EA"
        KG = "KG"

    sku = models.CharField(primary_key=True, max_length=50)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="skus", db_column="product_id")
    name = models.CharField(max_length=200)
    barcode = models.CharField(max_length=50, unique=True, null=True, blank=True)
    unit = models.CharField(max_length=2, choices=Unit.choices, default=Unit.EA)
    pack_size = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "sku"
        ordering = ["sku"]
        constraints = [models.CheckConstraint(name="sku_pack_size_positive", condition=Q(pack_size__gte=1))]


class Price(models.Model):
    pk = models.CompositePrimaryKey("sku_id", "branch_scope", "valid_from")
    sku = models.ForeignKey(Sku, on_delete=models.PROTECT, related_name="prices", db_column="sku", db_index=False)
    branch_scope = models.CharField(max_length=10)
    valid_from = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "price"
        ordering = ["sku_id", "branch_scope", "-valid_from"]
        constraints = [models.CheckConstraint(name="price_amount_non_negative", condition=Q(amount__gte=0))]


class Supplier(models.Model):
    supplier_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, unique=True)
    contact_email = models.EmailField(blank=True, default="")
    lead_time_days = models.PositiveSmallIntegerField()

    class Meta:
        db_table = "supplier"
        ordering = ["name"]


class SupplierSku(models.Model):
    pk = models.CompositePrimaryKey("supplier_id", "sku_id")
    supplier = models.ForeignKey(
        Supplier, on_delete=models.PROTECT, related_name="terms", db_column="supplier_id", db_index=False
    )
    sku = models.ForeignKey(Sku, on_delete=models.PROTECT, related_name="supplier_terms", db_column="sku")
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    min_order_qty = models.PositiveIntegerField(default=1)
    is_preferred = models.BooleanField(default=False)

    class Meta:
        db_table = "supplier_sku"
        constraints = [
            models.UniqueConstraint(fields=["sku"], condition=Q(is_preferred=True), name="supplier_sku_one_preferred"),
            models.CheckConstraint(name="supplier_sku_unit_cost_non_negative", condition=Q(unit_cost__gte=0)),
        ]
