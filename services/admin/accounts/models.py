"""admin_db (design doc §5.1): shop, branch, app_user, role_grant."""

import uuid

from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.db.models import Q


class Shop(models.Model):
    shop_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    base_currency = models.CharField(max_length=3, default="USD")

    class Meta:
        db_table = "shop"

    def __str__(self) -> str:
        return self.name


class Branch(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN"
        CLOSED = "CLOSED"

    branch_id = models.CharField(primary_key=True, max_length=10)  # "BR-01"
    shop = models.ForeignKey(Shop, on_delete=models.PROTECT, related_name="branches", db_column="shop_id")
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=500, blank=True, default="")
    region = models.CharField(max_length=50)  # PHNOM_PENH, SIEM_REAP, ...
    timezone = models.CharField(max_length=50, default="Asia/Phnom_Penh")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    opened_on = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "branch"
        ordering = ["branch_id"]

    def __str__(self) -> str:
        return f"{self.branch_id} {self.name}"


class AppUser(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE"
        DISABLED = "DISABLED"

    user_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=256)
    full_name = models.CharField(max_length=200)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "app_user"
        ordering = ["email"]

    def set_password(self, raw: str) -> None:
        self.password_hash = make_password(raw)

    def check_password(self, raw: str) -> bool:
        return check_password(raw, self.password_hash)

    def active_grants(self):
        return self.grants.filter(revoked_at__isnull=True)

    def __str__(self) -> str:
        return self.email


class RoleGrant(models.Model):
    class Role(models.TextChoices):
        HQ_ADMIN = "HQ_ADMIN"
        BRANCH_MANAGER = "BRANCH_MANAGER"
        CASHIER = "CASHIER"
        CUSTOMER = "CUSTOMER"  # reserved for Option B

    grant_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(AppUser, on_delete=models.CASCADE, related_name="grants", db_column="user_id")
    role_code = models.CharField(max_length=20, choices=Role.choices)
    branch = models.ForeignKey(
        Branch, on_delete=models.PROTECT, null=True, blank=True, related_name="grants", db_column="branch_id"
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "role_grant"
        constraints = [
            # HQ_ADMIN and CUSTOMER are not tied to a branch; branch staff always are.
            models.CheckConstraint(
                name="role_grant_branch_scope",
                condition=(Q(role_code__in=["HQ_ADMIN", "CUSTOMER"], branch__isnull=True))
                | (Q(role_code__in=["BRANCH_MANAGER", "CASHIER"], branch__isnull=False)),
            ),
        ]

    def as_claim(self) -> dict:
        return {"role": self.role_code, "branch_id": self.branch_id}

    def __str__(self) -> str:
        return f"{self.user_id} {self.role_code} {self.branch_id or '*'}"
