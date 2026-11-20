from datetime import timedelta

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST, require_safe

from .backups.models import BackupDownload, BackupRestoreCheck, BackupRun
from .models import (
    AuditEvent,
    DurableJob,
    MessageDelivery,
    OwnerNotice,
    PaymentOperation,
    PaymentSetup,
    SecurityAlert,
)
from .permissions import staff_permission


@staff_permission("core.view_booking")
@require_safe
def dashboard(request):
    alerts = (
        SecurityAlert.objects.filter(resolved_at__isnull=True) if request.user.is_superuser else []
    )
    return render(
        request,
        "core/dashboard.html",
        {
            "alerts": alerts,
            "backup_issues": BackupRun.objects.filter(
                state__in=["failed", "retention_failed"]
            ).order_by("-started_at")[:10]
            if settings.BACKUP_ENABLED and request.user.is_superuser
            else [],
            "backup_download_due": settings.BACKUP_ENABLED
            and request.user.is_superuser
            and not BackupDownload.objects.filter(
                created_at__gte=timezone.now() - timedelta(days=30)
            ).exists(),
            "backup_restore_due": settings.BACKUP_ENABLED
            and request.user.is_superuser
            and not BackupRestoreCheck.objects.filter(
                restored_at__gte=timezone.now() - timedelta(days=30)
            ).exists(),
            "email_issues": MessageDelivery.objects.filter(
                state__in=["failed", "unknown", "bounced"]
            )
            .select_related("customer")
            .order_by("created_at")[:20]
            if settings.BOOKING_EMAIL_ENABLED and request.user.is_superuser
            else [],
            "payment_issues": PaymentOperation.objects.filter(
                state__in=["unknown", "action", "sending", "declined"],
                followup__resolved_at__isnull=True,
            )
            .select_related("sale__customer")
            .order_by("requested_at")[:20]
            if settings.PAYMENT_SANDBOX_ENABLED
            and request.user.has_perm("core.view_paymentoperation")
            and request.user.has_perm("core.view_customer")
            else [],
            "setup_issues": PaymentSetup.objects.filter(
                state__in=["unknown", "customer_sending", "method_sending"]
            ).order_by("created_at")[:20]
            if settings.PAYMENT_SANDBOX_ENABLED and request.user.is_superuser
            else [],
            "blocked_jobs": DurableJob.objects.filter(state="blocked").order_by("created_at")[:20]
            if settings.PAYMENT_SANDBOX_ENABLED and request.user.is_superuser
            else [],
            "notices": OwnerNotice.objects.filter(reviewed_at__isnull=True).select_related(
                "customer"
            )
            if request.user.is_superuser
            else [],
        },
    )


@staff_permission("core.view_securityalert")
@require_POST
@transaction.atomic
def resolve_alert(request, pk):
    if not request.user.is_superuser:
        raise PermissionDenied
    alert = get_object_or_404(SecurityAlert.objects.select_for_update(), pk=pk)
    if alert.resolved_at is None:
        alert.resolved_at = timezone.now()
        alert.resolved_by = request.user
        alert.save()
        AuditEvent.objects.create(
            actor=request.user,
            action="security.alert_resolved",
            record_type="security_alert",
            record_id=str(pk),
        )
    return redirect("dashboard")


@staff_permission("core.view_booking")
@require_POST
@transaction.atomic
def review_notice(request, pk):
    if not request.user.is_superuser:
        raise PermissionDenied
    notice = get_object_or_404(OwnerNotice.objects.select_for_update(), pk=pk)
    if notice.reviewed_at is None:
        notice.reviewed_at = timezone.now()
        notice.reviewed_by = request.user
        notice.save(update_fields=["reviewed_at", "reviewed_by"])
        AuditEvent.objects.create(
            actor=request.user,
            action="customer.profile_conflict_reviewed"
            if notice.details.get("kind") == "booking_profile_conflict"
            else "customer.email_notice_reviewed",
            record_type="customer",
            record_id=str(notice.customer_id),
            changes={"notice_id": notice.pk},
        )
    return redirect("dashboard")
