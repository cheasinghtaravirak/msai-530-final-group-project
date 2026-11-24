import uuid

from django.db import models
from django.db.models import F, Q


class ForecastRun(models.Model):
    class Method(models.TextChoices):
        WEEKDAY_AVG = "WEEKDAY_AVG"
        HOLT_WINTERS = "HOLT_WINTERS"
        FALLBACK = "FALLBACK"

    class Status(models.TextChoices):
        RUNNING = "RUNNING"
        DONE = "DONE"
        FAILED = "FAILED"

    run_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    method = models.CharField(max_length=12, choices=Method.choices)
    data_cutoff = models.DateField()
    horizon_days = models.PositiveSmallIntegerField(default=14)
    status = models.CharField(max_length=7, choices=Status.choices, default=Status.RUNNING)
    wape = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "forecast_run"
        ordering = ["-data_cutoff"]


class DemandForecast(models.Model):
    pk = models.CompositePrimaryKey("run_id", "branch_id", "sku", "target_date")
    run = models.ForeignKey(ForecastRun, on_delete=models.PROTECT, related_name="forecasts")
    branch_id = models.CharField(max_length=10)
    sku = models.CharField(max_length=40)
    target_date = models.DateField()
    units_low = models.DecimalField(max_digits=10, decimal_places=2)
    units_mid = models.DecimalField(max_digits=10, decimal_places=2)
    units_high = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = "demand_forecast"
        indexes = [models.Index(fields=["branch_id", "sku", "target_date"], name="forecast_branch_sku_day_idx")]
        constraints = [
            models.CheckConstraint(
                condition=Q(units_low__gte=0, units_low__lte=F("units_mid"), units_mid__lte=F("units_high")),
                name="demand_forecast_band_ordered",
            ),
        ]


class SalesAnomaly(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN"
        CHECKED = "CHECKED"
        DISMISSED = "DISMISSED"

    anomaly_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch_id = models.CharField(max_length=10)
    sku = models.CharField(max_length=40)
    sale_date = models.DateField()
    run = models.ForeignKey(ForecastRun, on_delete=models.PROTECT, related_name="anomalies")
    actual_units = models.IntegerField()
    expected_low = models.DecimalField(max_digits=10, decimal_places=2)
    days_below = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.OPEN)

    class Meta:
        db_table = "sales_anomaly"
        constraints = [
            models.UniqueConstraint(fields=["run", "branch_id", "sku", "sale_date"], name="sales_anomaly_once_per_run"),
        ]
