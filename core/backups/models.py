"""Backup status and integrity metadata; never plaintext archives or recovery keys."""

import uuid

from django.conf import settings
from django.db import models


class BackupRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    state = models.CharField(
        max_length=20,
        default="running",
        choices=[
            (s, label)
            for s, label in (
                ("running", "Running"),
                ("verified", "Encrypted upload verified"),
                ("failed", "Backup failed"),
                ("retention_failed", "Retention needs review"),
                ("removed", "Expired recovery point removed"),
            )
        ],
    )
    object_key = models.CharField(max_length=160, unique=True)
    sha256 = models.CharField(max_length=64, blank=True)
    size = models.PositiveBigIntegerField(default=0)
    encryption_fingerprint = models.CharField(max_length=64, blank=True)
    monthly = models.BooleanField(default=False)
    month = models.CharField(max_length=7)
    started_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True)
    removed_at = models.DateTimeField(null=True)
    code = models.CharField(max_length=40, blank=True)
    issue_reviewed_at = models.DateTimeField(null=True)
    issue_reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT
    )


class BackupDownload(models.Model):
    backup = models.ForeignKey(BackupRun, on_delete=models.PROTECT, related_name="downloads")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class BackupRestoreCheck(models.Model):
    backup = models.ForeignKey(BackupRun, on_delete=models.PROTECT, related_name="restore_checks")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    restored_at = models.DateTimeField()
    recorded_at = models.DateTimeField(auto_now_add=True)
    notes = models.CharField(max_length=1000, blank=True)
