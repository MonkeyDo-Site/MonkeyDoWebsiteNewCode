from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .availability import NEW_YORK, occupancy
from .calendar import lock_calendar
from .models import AuditEvent, CalendarDate, Session
from .permissions import require_actor

SESSION_FIELDS = (
    "starts_at",
    "ends_at",
    "public",
    "closed",
    "private_label",
    "play_mode",
    "child_capacity",
    "total_capacity",
    "supervised_capacity",
)


def check_day(day):
    today = timezone.localdate(timezone=NEW_YORK)
    try:
        limit = today.replace(year=today.year + 2)
    except ValueError:
        limit = today.replace(year=today.year + 2, day=28)
    if not today <= day <= limit:
        raise ValidationError("Choose a date from today through two years ahead.")


def values(record, fields):
    return {
        name: (
            getattr(record, name).astimezone(NEW_YORK).isoformat()
            if name in {"starts_at", "ends_at"}
            else getattr(record, name).isoformat()
            if name == "day"
            else getattr(record, name)
        )
        for name in fields
    }


@transaction.atomic
def save_session(*, actor, data, pk=None, revision=None, preserve_management=False):
    require_actor(actor, "core.change_session", owner=True)
    lock_calendar(exclusive=True)
    current = Session.objects.select_for_update().get(pk=pk) if pk else None
    if current and (current.revision != revision or current.kind != Session.Kind.ORDINARY):
        raise ValidationError(
            "Session changed or belongs to a separate program. Reload and review it."
        )
    before = values(current, SESSION_FIELDS) if current else None
    row = current or Session()
    for name in SESSION_FIELDS:
        setattr(row, name, data[name])
    row.full_clean()
    if timezone.is_naive(row.starts_at) or timezone.is_naive(row.ends_at):
        raise ValidationError("Use timezone-aware New York session times.")
    day = row.starts_at.astimezone(NEW_YORK).date()
    check_day(day)
    if row.starts_at <= timezone.now():
        raise ValidationError("Only future sessions can be configured here.")
    if row.ends_at.astimezone(NEW_YORK).date() != day:
        raise ValidationError("Session must begin and end on the same New York date.")
    if row.play_mode not in {"both", "accompanied", "supervised"}:
        raise ValidationError("Choose a supported play type.")
    if row.play_mode == "accompanied" and row.supervised_capacity:
        raise ValidationError("Accompanied-only sessions must have zero supervised capacity.")
    if row.play_mode != "accompanied" and row.supervised_capacity == 0:
        # Existing seed rows default to both/zero. Owner must explicitly select
        # accompanied-only when editing these, never imply supervised availability.
        raise ValidationError("Enable a supervised limit or choose accompanied only.")
    if not row.private_label.strip():
        raise ValidationError("An internal session label is required.")
    if (
        Session.objects.exclude(pk=pk)
        .filter(starts_at__lt=row.ends_at, ends_at__gt=row.starts_at)
        .exists()
    ):
        raise ValidationError("This time overlaps another session. Edit that session instead.")
    if current:
        after = values(row, SESSION_FIELDS)
        # Earlier seed rows used both/zero to mean accompanied-only. Making
        # that implicit state explicit changes no booked play eligibility.
        equivalent_mode = (
            before["play_mode"] == "both"
            and before["supervised_capacity"] == 0
            and row.play_mode == "accompanied"
            and row.supervised_capacity == 0
        )
        timing_changed = any(before[name] != after[name] for name in ("starts_at", "ends_at"))
        mode_changed = before["play_mode"] != row.play_mode and not equivalent_mode
        if current.bookings.exists() and (timing_changed or mode_changed):
            raise ValidationError(
                "Booked session timing/play type cannot change here. Move bookings individually; notification integration remains pending."
            )
        children, adults, supervised = occupancy(row)
        if (
            children > row.child_capacity
            or children + adults > row.total_capacity
            or supervised > row.supervised_capacity
        ):
            raise ValidationError("Capacity cannot be reduced below existing reserved attendance.")
        row.revision += 1
    # Explicit per-date editing ends automatic template management.
    management_ended = row.recurring_managed and not preserve_management
    if not preserve_management:
        row.recurring_managed = False
    row.save()
    AuditEvent.objects.create(
        actor=actor,
        action="schedule.session_updated" if current else "schedule.session_created",
        record_type="session",
        record_id=str(row.pk),
        changes={
            "before": before,
            "after": values(row, SESSION_FIELDS),
            "revision": row.revision,
            "automatic_management_ended": management_ended,
        },
    )
    return row


@transaction.atomic
def save_date(*, actor, day, closed, private_reason, chol_hamoed, revision):
    require_actor(actor, "core.change_calendardate", owner=True)
    check_day(day)
    lock_calendar(exclusive=True)
    row = CalendarDate.objects.select_for_update().filter(day=day).first()
    if (row.revision if row else 0) != revision:
        raise ValidationError("Date changed while you were editing. Reload and review it.")
    fields = ("day", "closed", "private_reason", "chol_hamoed")
    before = values(row, fields) if row else None
    if closed and not private_reason.strip():
        raise ValidationError("Enter a private closure reason.")
    row = row or CalendarDate(day=day, revision=0)
    row.closed, row.private_reason, row.chol_hamoed = closed, private_reason, chol_hamoed
    row.revision += 1
    row.full_clean()
    row.save()
    AuditEvent.objects.create(
        actor=actor,
        action="schedule.date_updated",
        record_type="calendar_date",
        record_id=str(row.pk),
        changes={"before": before, "after": values(row, fields), "revision": row.revision},
    )
    return row
