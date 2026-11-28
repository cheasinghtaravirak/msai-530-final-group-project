from django.db import models

SKU_MAX_LENGTH = 40


class Outbox(models.Model):
    """Events waiting to be published. Written in the same transaction as the business change."""

    event_id = models.UUIDField(primary_key=True)
    event_type = models.CharField(max_length=100)
    topic = models.CharField(max_length=100)
    key = models.CharField(max_length=200)
    envelope = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "outbox"
        indexes = [
            models.Index(
                fields=["created_at"],
                condition=models.Q(published_at__isnull=True),
                name="outbox_unpublished_idx",
            )
        ]

    def __str__(self) -> str:
        return f"{self.event_type} {self.event_id}"


class ProcessedEvent(models.Model):
    """Events this service has already applied. The primary key makes redelivery a no-op."""

    event_id = models.UUIDField(primary_key=True)
    event_type = models.CharField(max_length=100)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "processed_event"

    def __str__(self) -> str:
        return f"{self.event_type} {self.event_id}"
