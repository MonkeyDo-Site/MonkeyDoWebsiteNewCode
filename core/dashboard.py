from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST, require_safe

from .models import AuditEvent, SecurityAlert
from .permissions import staff_permission


@staff_permission("core.view_booking")
@require_safe
def dashboard(request):
    alerts = (
        SecurityAlert.objects.filter(resolved_at__isnull=True) if request.user.is_superuser else []
    )
    return render(request, "core/dashboard.html", {"alerts": alerts})


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
