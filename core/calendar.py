"""Calendar gates shared by public availability and transactional reservations."""

from django.db import connection

from .models import CalendarDate


def lock_calendar(*, exclusive=False):
    # All callers run inside atomic(). Shared booking locks permit concurrent
    # bookings; exclusive owner changes cannot race a capacity/closure decision.
    if connection.vendor == "postgresql":
        function = "pg_advisory_xact_lock" if exclusive else "pg_advisory_xact_lock_shared"
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT {function}(%s, %s)", [73216, 1])


def date_closed(session):
    from .availability import NEW_YORK

    return CalendarDate.objects.filter(
        day=session.starts_at.astimezone(NEW_YORK).date(), closed=True
    ).exists()


def weekly_default_blocked(session):
    """Read current policy, even when the caller holds an older Session instance."""
    from .models import WeeklySlot

    return (
        bool(session.source_slot_id)
        and not WeeklySlot.objects.filter(
            pk=session.source_slot_id, active=True, archived_at__isnull=True
        ).exists()
    )


def overlapping_sessions(starts_at, ends_at, *, exclude_pk=None):
    """Retain dated-session identity and overlap protections, including hidden history."""
    from .models import Session

    return Session.objects.exclude(pk=exclude_pk).filter(
        starts_at__lt=ends_at, ends_at__gt=starts_at
    )
