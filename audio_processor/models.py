from django.db import models

# Create your models here.
import uuid
from django.db import models


class AudioFile(models.Model):
    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    original_file = models.FileField(
        upload_to="audio/original/"
    )

    converted_file = models.FileField(
        upload_to="audio/converted/",
        null=True,
        blank=True
    )

    output_audio = models.FileField(
        upload_to="audio/output/",
        null=True,
        blank=True
    )

    duration = models.FloatField(
        help_text="Duration in seconds",
        null=True,
        blank=True
    )

    file_size = models.IntegerField(
        help_text="File size in bytes",
        null=True,
        blank=True
    )

    source_language = models.CharField(
        max_length=10
    )

    target_language = models.CharField(
        max_length=10
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )

    transcription = models.TextField(
        null=True,
        blank=True
    )

    translation = models.TextField(
        null=True,
        blank=True
    )

    progress = models.IntegerField(
        default=0,
        help_text="Processing progress (0-100)"
    )

    error_message = models.TextField(
        null=True,
        blank=True,
        help_text="Error message if processing failed"
    )

    celery_task_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Celery task ID for tracking"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    def __str__(self):
        return f"{self.id} | {self.status}"
