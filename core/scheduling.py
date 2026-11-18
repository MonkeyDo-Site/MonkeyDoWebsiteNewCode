from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .availability import NEW_YORK, occupancy
from .calendar import lock_calendar, overlapping_sessions
from .models import AuditEvent, CalendarDate, Session
from .permissions import require_actor

SESSION_FIELDS = (
    "starts_at",
    "ends_at",
    "public",
    "closed",
    "custom_blocking",
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
def save_session(
    *,
    actor,
    data,
    pk=None,
    revision=None,
    preserve_management=False,
    reopen_affected_sessions=False,
    expected_conflicts=None,
):
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
        setattr(row, name, data.get(name, getattr(row, name)))
    row.full_clean()
    if timezone.is_naive(row.starts_at) or timezone.is_naive(row.ends_at):
        raise ValidationError("Use timezone-aware New York session times.")
    day = row.starts_at.astimezone(NEW_YORK).date()
    check_day(day)
    if current and not preserve_management and before["starts_at"][:10] != day.isoformat():
        raise ValidationError("You can’t switch the date of the session, only the timing.")
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
    from .session_blocks import SessionConflict, active_bookings, sync_custom_blocks

    conflicts = list(overlapping_sessions(row.starts_at, row.ends_at, exclude_pk=pk))
    if current and current.custom_blocking != row.custom_blocking:
        raise ValidationError(
            "Keep this session's original custom/standard type. Create a separate session instead."
        )
    if row.custom_blocking:
        if expected_conflicts is not None and sorted(
            (s.pk, s.revision) for s in conflicts
        ) != sorted(tuple(s) for s in expected_conflicts):
            raise ValidationError(
                "The affected sessions changed. Review the custom-session preview again."
            )
        blocked_bookings = active_bookings(conflicts)
        if blocked_bookings.exists():
            raise SessionConflict(blocked_bookings)
        if any(s.custom_blocking or s.kind != Session.Kind.ORDINARY for s in conflicts):
            raise SessionConflict(
                message="This custom time overlaps another custom or program session. Review that session first."
            )
    else:
        # Existing blocked sessions remain editable without allowing new overlaps.
        permitted = (
            set(
                current.reservation_blocks.filter(
                    active=True, source_session__isnull=False
                ).values_list("source_session_id", flat=True)
            )
            if current
            and row.starts_at == datetime.fromisoformat(before["starts_at"])
            and row.ends_at == datetime.fromisoformat(before["ends_at"])
            else set()
        )
        if any(s.pk not in permitted for s in conflicts):
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
    if row.custom_blocking:
        sync_custom_blocks(actor, row, conflicts, reopen_removed=reopen_affected_sessions)
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
def save_date(*, actor, day, closed, private_reason, chol_hamoed, revision, backend_only=False):
    require_actor(actor, "core.change_calendardate", owner=True)
    check_day(day)
    lock_calendar(exclusive=True)
    row = CalendarDate.objects.select_for_update().filter(day=day).first()
    if (row.revision if row else 0) != revision:
        raise ValidationError("Date changed while you were editing. Reload and review it.")
    fields = ("day", "closed", "backend_only", "private_reason", "chol_hamoed")
    before = values(row, fields) if row else None
    if closed and not private_reason.strip():
        raise ValidationError("Enter a private closure reason.")
    row = row or CalendarDate(day=day, revision=0)
    row.closed, row.private_reason, row.chol_hamoed = closed, private_reason, chol_hamoed
    row.backend_only = backend_only
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
