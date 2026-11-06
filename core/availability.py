from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db.models import Sum
from django.utils import timezone

from .models import Booking, Session

NEW_YORK = ZoneInfo("America/New_York")


def opening_time(day, horizon):
    if not 1 <= horizon <= 10:
        raise ValueError("Horizon must be 1–10 calendar days.")
    opens = day - timedelta(days=horizon)
    if day.weekday() == 6:  # Sunday must open by Friday midnight.
        opens = min(opens, day - timedelta(days=2))
    return datetime.combine(opens, time.min, NEW_YORK)


def occupancy(session):
    bookings = session.bookings.exclude(attendance=Booking.Attendance.CANCELLED)
    counts = bookings.aggregate(children=Sum("children"), adults=Sum("adults"))
    return (
        counts["children"] or 0,
        counts["adults"] or 0,
        bookings.filter(supervised=True).aggregate(n=Sum("children"))["n"] or 0,
    )


def availability(session, horizon=1, now=None):
    now = now or timezone.now()
    children, adults, supervised = occupancy(session)
    day = session.starts_at.astimezone(NEW_YORK).date()
    if not session.public or day.weekday() == 5:
        return {"available": False, "label": "Unavailable", "hidden": True}
    if session.kind == Session.Kind.PARTY:
        label = "A party is booked for this slot."
    elif session.closed or session.kind == Session.Kind.EXCLUSIVE:
        label = "Unavailable"
    elif now < opening_time(day, horizon):
        label = "Not yet open"
    elif now >= session.ends_at:
        label = "Session ended"
    elif children >= session.child_capacity or children + adults >= session.total_capacity:
        label = "Fully booked"
    else:
        return {
            "available": True,
            "label": "Available",
            "hidden": False,
            "supervised_available": now < session.starts_at
            and supervised < session.supervised_capacity,
        }
    return {"available": False, "label": label, "hidden": False}
