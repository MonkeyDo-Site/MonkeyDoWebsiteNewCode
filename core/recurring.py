from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .availability import NEW_YORK
from .calendar import lock_calendar, overlapping_sessions
from .models import AuditEvent, Booking, Session, SiteSettings, WeeklySlot
from .permissions import require_actor
from .scheduling import SESSION_FIELDS, check_day, save_session, values

FIELDS = (
    "label",
    "weekdays",
    "starts_at",
    "ends_at",
    "active",
    "public",
    "play_mode",
    "child_capacity",
    "total_capacity",
    "supervised_capacity",
)


def snapshot(slot):
    return {
        field: getattr(slot, field).isoformat()
        if field in {"starts_at", "ends_at"}
        else getattr(slot, field)
        for field in FIELDS
    }


@transaction.atomic
def save_slot(*, actor, data, pk=None, revision=None):
    require_actor(actor, "core.change_weeklyslot", owner=True)
    lock_calendar(exclusive=True)
    slot = WeeklySlot.objects.select_for_update().get(pk=pk) if pk else WeeklySlot()
    if pk and slot.revision != revision:
        raise ValidationError("Weekly slot changed while you were editing. Reload and review it.")
    if slot.archived_at is not None:
        raise ValidationError("This weekly default was deleted. Add a new default if needed.")
    before = snapshot(slot) if pk else None
    days = data["weekdays"]
    if (
        not isinstance(days, list)
        or not days
        or any(type(d) is not int or d not in range(7) for d in days)
        or len(set(days)) != len(days)
    ):
        raise ValidationError("Choose one or more distinct weekdays.")
    for field in FIELDS:
        setattr(slot, field, data[field])
    slot.weekdays = sorted(days)
    slot.full_clean()
    if (
        slot.play_mode == "accompanied"
        and slot.supervised_capacity
        or slot.play_mode != "accompanied"
        and slot.supervised_capacity == 0
    ):
        raise ValidationError(
            "Choose a supervised limit for supervised/mixed play, or zero for accompanied-only play."
        )
    if slot.active:
        for other in WeeklySlot.objects.filter(
            active=True,
            archived_at__isnull=True,
            starts_at__lt=slot.ends_at,
            ends_at__gt=slot.starts_at,
        ).exclude(pk=pk):
            if set(other.weekdays) & set(slot.weekdays):
                raise ValidationError("This weekly slot overlaps another active weekly slot.")
    if pk:
        slot.revision += 1
    slot.save()
    AuditEvent.objects.create(
        actor=actor,
        action="schedule.weekly_slot_saved",
        record_type="weekly_slot",
        record_id=str(slot.pk),
        changes={"before": before, "after": snapshot(slot), "revision": slot.revision},
    )
    return slot


def local_time(day, clock):
    naive = datetime.combine(day, clock)
    value = naive.replace(tzinfo=NEW_YORK)
    if value.utcoffset() != value.replace(fold=1).utcoffset():
        raise ValidationError(
            f"{day.isoformat()} {clock.isoformat()} is ambiguous or nonexistent in New York. Choose another time or a shorter date range."
        )
    return value


@transaction.atomic
def generate_sessions(*, actor, slot_ids, from_day, through_day, update_existing=False):
    require_actor(actor, "core.change_weeklyslot", owner=True)
    require_actor(actor, "core.change_session", owner=True)
    check_day(from_day)
    check_day(through_day)
    if through_day < from_day:
        raise ValidationError("End date must be on or after start date.")
    lock_calendar(exclusive=True)
    slots = list(
        WeeklySlot.objects.filter(pk__in=slot_ids, active=True, archived_at__isnull=True).order_by(
            "pk"
        )
    )
    if not slots or {s.pk for s in slots} != set(slot_ids):
        raise ValidationError("Choose active weekly defaults that have not been deleted.")
    results = []
    day = from_day
    while day <= through_day:
        for slot in slots:
            existing = Session.objects.filter(source_slot=slot, source_day=day).first()
            matches = slot.active and day.weekday() in slot.weekdays
            if not matches and not existing:
                continue
            if existing and (
                not update_existing
                or not existing.recurring_managed
                or existing.kind != Session.Kind.ORDINARY
                or existing.bookings.exists()
                or existing.starts_at <= timezone.now()
            ):
                results.append(
                    {
                        "day": day.isoformat(),
                        "slot": slot.label,
                        "outcome": "Preserved",
                        "reason": "Existing session: updates off, manual edit, program session, booking history or already started.",
                    }
                )
                continue
            if not matches:
                if existing.closed:
                    continue
                data = {
                    field: getattr(existing, field)
                    for field in (
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
                }
                data["closed"] = True
            else:
                starts = local_time(day, slot.starts_at)
                ends = local_time(day, slot.ends_at)
                if starts <= timezone.now():
                    continue
                data = dict(
                    starts_at=starts,
                    ends_at=ends,
                    public=slot.public,
                    closed=False,
                    private_label=slot.label,
                    play_mode=slot.play_mode,
                    child_capacity=slot.child_capacity,
                    total_capacity=slot.total_capacity,
                    supervised_capacity=slot.supervised_capacity,
                )
            # Preserve independent sessions, including legacy seed rows. Never
            # adopt their identity or overwrite their visibility/program state.
            if overlapping_sessions(
                data["starts_at"], data["ends_at"], exclude_pk=existing.pk if existing else None
            ).exists():
                results.append(
                    {
                        "day": day.isoformat(),
                        "slot": slot.label,
                        "outcome": "Preserved",
                        "reason": "Conflicts with another dated session; review it individually.",
                    }
                )
                continue
            if (
                existing
                and existing.source_revision == slot.revision
                and all(getattr(existing, k) == v for k, v in data.items())
            ):
                continue
            row = save_session(
                actor=actor,
                data=data,
                pk=existing.pk if existing else None,
                revision=existing.revision if existing else None,
                preserve_management=True,
            )
            row.source_slot = slot
            row.source_day = day
            row.source_revision = slot.revision
            row.recurring_managed = True
            row.save(
                update_fields=["source_slot", "source_day", "source_revision", "recurring_managed"]
            )
            results.append(
                {
                    "day": day.isoformat(),
                    "slot": slot.label,
                    "outcome": "Updated" if existing else "Created",
                    "session_id": row.pk,
                    "session_revision": row.revision,
                    "reason": "Closed obsolete generated session." if not matches else "",
                }
            )
        day += timedelta(days=1)
    AuditEvent.objects.create(
        actor=actor,
        action="schedule.sessions_generated",
        record_type="weekly_schedule",
        record_id="batch",
        changes={
            "from": from_day.isoformat(),
            "through": through_day.isoformat(),
            "slot_ids": [s.pk for s in slots],
            "slot_revisions": {str(s.pk): s.revision for s in slots},
            "update_existing": update_existing,
            "results": results,
        },
    )
    return results


@transaction.atomic
def save_horizon(*, actor, days, expected_days, reset_confirmed=False):
    require_actor(actor, "core.change_sitesettings", owner=True)
    if type(days) is not int or not 1 <= days <= 10:
        raise ValidationError("Choose a whole number from 1 through 10 days.")
    lock_calendar(exclusive=True)
    settings, _ = SiteSettings.objects.get_or_create(pk=1)
    settings = SiteSettings.objects.select_for_update().get(pk=1)
    if settings.booking_horizon_days != expected_days:
        raise ValidationError(
            "Booking horizon changed while you were editing. Reload and review it."
        )
    if days == 1 and expected_days != 1 and not reset_confirmed:
        raise ValidationError("Confirm reverting the booking horizon to its default of 1 day.")
    settings.booking_horizon_days = days
    settings.save(update_fields=["booking_horizon_days"])
    AuditEvent.objects.create(
        actor=actor,
        action="schedule.horizon_changed",
        record_type="site_settings",
        record_id="1",
        changes={"before": expected_days, "after": days},
    )
    return settings


@transaction.atomic
def delete_slot(*, actor, pk, revision, expected_bookings):
    require_actor(actor, "core.change_weeklyslot", owner=True)
    lock_calendar(exclusive=True)
    slot = WeeklySlot.objects.select_for_update().get(pk=pk)
    if slot.archived_at is not None or slot.revision != revision:
        raise ValidationError("This weekly default changed. Reload and review it before deleting.")
    count = Booking.objects.filter(session__source_slot=slot).count()
    if count != expected_bookings:
        raise ValidationError(
            "The booking count changed. Review the updated warning before deleting."
        )
    before = snapshot(slot)
    # Only untouched, future generated sessions with no booking history can be
    # removed. Booked/manual/past records retain their original identity/time.
    unused = list(
        Session.objects.filter(
            source_slot=slot,
            recurring_managed=True,
            starts_at__gt=timezone.now(),
            kind=Session.Kind.ORDINARY,
            bookings__isnull=True,
        )
    )
    removed = [
        {
            "id": row.pk,
            **values(row, SESSION_FIELDS),
            "source_day": row.source_day.isoformat() if row.source_day else None,
            "source_revision": row.source_revision,
        }
        for row in unused
    ]
    Session.objects.filter(pk__in=[row.pk for row in unused]).delete()
    slot.active = False
    slot.archived_at = timezone.now()
    slot.revision += 1
    slot.save(update_fields=["active", "archived_at", "revision"])
    AuditEvent.objects.create(
        actor=actor,
        action="schedule.weekly_slot_deleted",
        record_type="weekly_slot",
        record_id=str(slot.pk),
        changes={
            "before": before,
            "archived_at": slot.archived_at.isoformat(),
            "retained_bookings": count,
            "removed_unused_generated_sessions": removed,
            "revision": slot.revision,
        },
    )
    return slot
