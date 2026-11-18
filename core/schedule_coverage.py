"""Compare actual dated records with today's default, without changing a session."""

from datetime import timedelta

from django.utils import timezone

from .availability import NEW_YORK
from .models import Session


def describe_coverage(slot):
    today = timezone.localdate(timezone=NEW_YORK)
    rows = list(
        Session.objects.filter(source_slot=slot, source_day__gte=today)
        .prefetch_related("bookings", "reservation_blocks")
        .order_by("source_day")
    )
    by_day = {row.source_day: row for row in rows}
    slot.generated_until = max(by_day, default=None)
    slot.gaps = []
    slot.current_until = None
    slot.coverage_ranges = []
    contiguous = slot.active
    day = today
    while slot.generated_until and day <= slot.generated_until:
        row = by_day.get(day)
        expected = day.weekday() in slot.weekdays
        if not expected and row is None:
            day += timedelta(days=1)
            continue
        matching = False
        clock = "—"
        if row is None:
            label = "Missing — not generated"
            slot.gaps.append(day)
        else:
            start, end = row.starts_at.astimezone(NEW_YORK), row.ends_at.astimezone(NEW_YORK)
            clock = (
                f"{start.strftime('%I:%M %p').lstrip('0')}–{end.strftime('%I:%M %p').lstrip('0')}"
            )
            matching = (
                expected
                and slot.active
                and not row.closed
                and start.time() == slot.starts_at
                and end.time() == slot.ends_at
                and all(
                    getattr(row, key) == getattr(slot, key)
                    for key in (
                        "public",
                        "play_mode",
                        "child_capacity",
                        "total_capacity",
                        "supervised_capacity",
                    )
                )
            )
            if any(block.active for block in row.reservation_blocks.all()):
                label, matching = "Blocked — review custom session / booking closure", False
            elif matching:
                label = "Matches current default"
            elif row.bookings.exists() or not row.recurring_managed:
                label = "Preserved booking / individual settings"
            else:
                label = "Earlier timing / settings — update not yet applied"
        if not expected:
            label = "Outside current weekdays — retained history"
        if expected and contiguous and matching:
            slot.current_until = day
        elif expected:
            contiguous = False
        key = (clock, label)
        if slot.coverage_ranges and slot.coverage_ranges[-1]["key"] == key:
            slot.coverage_ranges[-1]["end"] = day
            slot.coverage_ranges[-1]["count"] += 1
        else:
            slot.coverage_ranges.append(
                {"key": key, "start": day, "end": day, "count": 1, "time": clock, "status": label}
            )
        day += timedelta(days=1)
    return slot
