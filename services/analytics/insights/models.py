import uuid

from django.db import models
from forecasting.models import ForecastRun
from replenishment.models import Recommendation

COMPANY_BRANCH_ID = "ALL"


class AiBriefing(models.Model):
    class Status(models.TextChoices):
        OK = "OK"
        FALLBACK = "FALLBACK"
        FAILED = "FAILED"

    briefing_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch_id = models.CharField(max_length=10)
    briefing_date = models.DateField()
    run = models.ForeignKey(ForecastRun, on_delete=models.PROTECT, null=True, blank=True, related_name="briefings")
    model = models.CharField(max_length=100)
    prompt_version = models.CharField(max_length=50)
    input_json = models.JSONField()
    output_json = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=8, choices=Status.choices)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ai_briefing"
        constraints = [
            models.UniqueConstraint(fields=["branch_id", "briefing_date"], name="ai_briefing_one_per_branch_day"),
        ]


class AiExplanation(models.Model):
    class Status(models.TextChoices):
        OK = "OK"
        FALLBACK = "FALLBACK"

    recommendation = models.OneToOneField(
        Recommendation, primary_key=True, on_delete=models.PROTECT, related_name="explanation"
    )
    model = models.CharField(max_length=100)
    prompt_version = models.CharField(max_length=50)
    input_json = models.JSONField()
    text = models.TextField()
    status = models.CharField(max_length=8, choices=Status.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ai_explanation"
