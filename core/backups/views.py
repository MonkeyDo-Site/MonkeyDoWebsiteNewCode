"""Owner-only encrypted downloads and explicit evidence of an isolated restore."""

import json
from datetime import timedelta

from django import forms
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404, HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from core.models import AuditEvent
from core.pagination import paginate
from core.permissions import staff_permission

from .models import BackupDownload, BackupRestoreCheck, BackupRun
from .services import enabled
from .storage import BackupStore, BackupUnavailable


def owner(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    if not settings.BACKUP_ENABLED:
        raise Http404
    enabled()


class RestoreCheckForm(forms.Form):
    restored_at = forms.DateTimeField(
        label="When the isolated restore was verified",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )
    notes = forms.CharField(
        required=False,
        max_length=1000,
        widget=forms.Textarea,
        label="Verification details (no secrets or customer details)",
    )
    confirmed = forms.BooleanField(
        label="I decrypted and restored this archive in an isolated nonproduction database, checked its data and removed that temporary database. This is not a production restore."
    )

    def clean_restored_at(self):
        value = self.cleaned_data["restored_at"]
        if value > timezone.now():
            raise forms.ValidationError("Use the actual completed restore-test time.")
        return value


@staff_permission("core.view_booking")
@require_http_methods(["GET", "POST"])
def backups(request):
    owner(request)
    records = BackupRun.objects.order_by("-started_at")
    last_download = BackupDownload.objects.order_by("-created_at").first()
    last_restore = BackupRestoreCheck.objects.order_by("-restored_at").first()
    return render(
        request,
        "core/backups.html",
        {
            "backups": paginate(request, records),
            "download_due": not last_download
            or last_download.created_at < timezone.now() - timedelta(days=30),
            "restore_due": not last_restore
            or last_restore.restored_at < timezone.now() - timedelta(days=30),
            "last_restore": last_restore,
        },
    )


def manifest(run):
    return {
        "format": "MonkeyDo-CMS-AES256-GCM-v1",
        "backup_id": str(run.pk),
        "object_key": run.object_key,
        "ciphertext_sha256": run.sha256,
        "ciphertext_bytes": run.size,
        "public_certificate_sha256": run.encryption_fingerprint,
        "verified_at": run.verified_at.isoformat() if run.verified_at else None,
    }


@staff_permission("core.view_booking")
@require_GET
def download(request, pk, metadata=False):
    owner(request)
    run = get_object_or_404(BackupRun, pk=pk, state__in=["verified", "retention_failed"])
    name = "MonkeyDo-staging-" + run.started_at.strftime("%Y-%m-%d") + "-" + str(run.pk)
    if metadata:
        response = HttpResponse(
            json.dumps(manifest(run), indent=2), content_type="application/json"
        )
        response["Content-Disposition"] = f'attachment; filename="{name}.json"'
    else:
        try:
            result = BackupStore(read_only=True).read(run.object_key)
            if result["ContentLength"] != run.size:
                result["Body"].close()
                raise BackupUnavailable("backup_integrity")
        except Exception:
            return HttpResponse(
                "Encrypted download could not be verified. No archive was released. Review private storage access.",
                status=503,
            )
        body = result["Body"]

        def chunks():
            try:
                while block := body.read(1024 * 1024):
                    yield block
            finally:
                body.close()

        response = StreamingHttpResponse(chunks(), content_type="application/pkcs7-mime")
        response["Content-Length"] = str(run.size)
        response["Content-Disposition"] = f'attachment; filename="{name}.cms"'
        BackupDownload.objects.create(backup=run, actor=request.user)
        AuditEvent.objects.create(
            actor=request.user,
            action="backup.download_started",
            record_type="backup",
            record_id=str(run.pk),
        )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@staff_permission("core.view_booking")
@require_http_methods(["GET", "POST"])
def record_restore(request, pk):
    owner(request)
    run = get_object_or_404(BackupRun, pk=pk, state__in=["verified", "retention_failed"])
    form = RestoreCheckForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        if form.cleaned_data["restored_at"] < run.started_at:
            form.add_error(
                "restored_at", "The restore check must be after this backup was created."
            )
        else:
            result = BackupRestoreCheck.objects.create(
                backup=run,
                actor=request.user,
                restored_at=form.cleaned_data["restored_at"],
                notes=form.cleaned_data["notes"],
            )
            AuditEvent.objects.create(
                actor=request.user,
                action="backup.restore_check_reported",
                record_type="backup",
                record_id=str(run.pk),
                changes={"restore_check_id": result.pk, "source": "owner_report"},
            )
            return redirect("backups")
    return render(request, "core/backup_restore.html", {"backup": run, "form": form})


@staff_permission("core.view_booking")
@require_POST
@transaction.atomic
def review_issue(request, pk):
    owner(request)
    run = get_object_or_404(
        BackupRun.objects.select_for_update(), pk=pk, state__in=["failed", "retention_failed"]
    )
    if run.issue_reviewed_at is None:
        run.issue_reviewed_at, run.issue_reviewed_by = timezone.now(), request.user
        run.save(update_fields=["issue_reviewed_at", "issue_reviewed_by"])
        AuditEvent.objects.create(
            actor=request.user,
            action="backup.issue_reviewed",
            record_type="backup",
            record_id=str(run.pk),
        )
    return redirect("backups")
