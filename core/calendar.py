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
