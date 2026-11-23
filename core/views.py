from datetime import timedelta

from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_safe

from .availability import availability
from .booking_progress import progress
from .models import Session, SiteSettings


@require_safe
def page(request, name="home"):
    return render(request, f"core/{name}.html")


@require_safe
def schedule(request):
    today = timezone.localdate()
    settings = SiteSettings.objects.filter(pk=1).first()
    horizon = settings.booking_horizon_days if settings else 1
    sessions = Session.objects.filter(
        public=True,
        ends_at__gt=timezone.now(),
        starts_at__date__lte=today + timedelta(days=horizon + 2),
    )
    days = {}
    for session in sessions:
        state = availability(session, horizon)
        if state["hidden"]:
            continue
        day = timezone.localtime(session.starts_at).date()
        days.setdefault(day, []).append({"session": session, **state})
    dates = [
        {
            "date": day,
            "slots": slots,
            "full": all(
                s["label"] in ("Fully booked", "A party is booked for this slot.") for s in slots
            ),
        }
        for day, slots in days.items()
    ]
    return render(
        request,
        "core/schedule.html",
        {
            "dates": dates,
            "progress_steps": progress(
                1,
                waivers=__import__(
                    "django.conf", fromlist=["settings"]
                ).settings.BOOKING_COMPLETION_ENABLED,
            ),
        },
    )


@login_required
@permission_required("core.view_booking", raise_exception=True)
@require_safe
def today(request):
    if not request.user.is_active or not request.user.is_staff:
        raise PermissionDenied
    from .booking_filters import booking_context

    context = booking_context(request, today_only=True)
    from .pagination import paginate

    context["bookings"] = paginate(request, context.pop("rows"))
    return render(request, "core/today.html", context)


@require_safe
def health(request):
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    return JsonResponse({"status": "ok", "mode": "test", "checkout_enabled": False})


def csrf_failure(request, reason=""):
    return render(
        request,
        "csrf_failure.html",
        {"booking_form": request.path.startswith("/book/")},
        status=403,
    )
