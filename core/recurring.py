from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .availability import NEW_YORK
from .calendar import date_closed, lock_calendar, overlapping_sessions, weekly_default_blocked
from .models import AuditEvent, Booking, Session, SiteSettings, WeeklySlot
from .permissions import require_actor
from .scheduling import SESSION_FIELDS, check_day, values

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
def save_slots(*, actor, edits):
    """Validate the final weekly schedule, never intermediate single-slot positions."""
    require_actor(actor, "core.change_weeklyslot", owner=True)
    lock_calendar(exclusive=True)
    current = {
        row.pk: row
        for row in WeeklySlot.objects.select_for_update().filter(archived_at__isnull=True)
    }
    changed = []
    seen = set()
    for edit in edits:
        pk = edit.get("pk")
        if pk in seen and pk is not None:
            raise ValidationError("A weekly default was submitted twice.")
        seen.add(pk)
        row = current.get(pk) if pk else WeeklySlot()
        if row is None or (pk and row.revision != edit.get("revision")):
            raise ValidationError("Weekly schedule changed. Reload and review it.")
        before = snapshot(row) if pk else None
        data = edit["data"]
        days = data["weekdays"]
        if (
            not isinstance(days, list)
            or not days
            or any(type(d) is not int or d not in range(7) for d in days)
            or len(set(days)) != len(days)
        ):
            raise ValidationError("Choose one or more distinct weekdays.")
        for field in FIELDS:
            setattr(row, field, data[field])
        row.weekdays = sorted(days)
        row.full_clean()
        if (row.play_mode == "accompanied") != (row.supervised_capacity == 0):
            raise ValidationError(
                "Choose a supervised limit for Supervised Play, or zero for Open Play only."
            )
        changed.append((row, before))
    final = [row for row in current.values() if row.active] + [
        row for row, before in changed if before is None and row.active
    ]
    for i, row in enumerate(final):
        for other in final[i + 1 :]:
            if (
                set(row.weekdays) & set(other.weekdays)
                and row.starts_at < other.ends_at
                and row.ends_at > other.starts_at
            ):
                raise ValidationError(
                    f"Final schedule overlaps: {row.label} and {other.label}. Review their times and weekdays."
                )
    for row, before in changed:
        if before == snapshot(row):
            continue
        if row.pk:
            row.revision += 1
        row.save()
        AuditEvent.objects.create(
            actor=actor,
            action="schedule.weekly_slot_saved",
            record_type="weekly_slot",
            record_id=str(row.pk),
            changes={"before": before, "after": snapshot(row), "revision": row.revision},
        )
    return [row for row, before in changed]


def save_slot(*, actor, data, pk=None, revision=None):
    return save_slots(actor=actor, edits=[{"pk": pk, "revision": revision, "data": data}])[0]


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
        raise ValidationError("Choose open weekly defaults that have not been deleted.")
    results = []
    plans = []
    now = timezone.now()
    day = from_day

    def report(slot, day, reason, existing=None, outcome="Preserved", conflicts=None):
        result = {
            "day": day.isoformat(),
            "slot": slot.label,
            "outcome": outcome,
            "reason": reason,
            "display_outcome": "Not generated"
            if outcome == "Preserved" and not existing
            else "Unchanged",
        }
        if existing:
            result["session_id"] = existing.pk
        if conflicts:
            result["conflicts"] = conflicts
        results.append(result)

    while day <= through_day:
        for slot in slots:
            existing = Session.objects.filter(source_slot=slot, source_day=day).first()
            matches = day.weekday() in slot.weekdays
            if not matches and not existing:
                continue
            if existing:
                reason = None
                if existing.bookings.exists():
                    reason = "Existing session has booking history; its original time and bookings were retained."
                elif not existing.recurring_managed:
                    reason = "This session was individually edited and is no longer managed by the weekly default."
                elif existing.kind != Session.Kind.ORDINARY:
                    reason = (
                        "This is a program session and cannot be replaced by weekly generation."
                    )
                elif existing.starts_at <= now:
                    reason = "This session has already started."
                elif not update_existing:
                    reason = "Updating existing unbooked sessions was not selected."
                if reason:
                    report(slot, day, reason, existing)
                    continue
            if matches:
                data = dict(
                    starts_at=local_time(day, slot.starts_at),
                    ends_at=local_time(day, slot.ends_at),
                    public=slot.public,
                    closed=False,
                    private_label=slot.label,
                    play_mode=slot.play_mode,
                    child_capacity=slot.child_capacity,
                    total_capacity=slot.total_capacity,
                    supervised_capacity=slot.supervised_capacity,
                )
            else:
                data = {key: getattr(existing, key) for key in SESSION_FIELDS}
                data["closed"] = True
            if data["starts_at"] <= now:
                report(slot, day, "The proposed session start time has already passed.", existing)
                continue
            if (
                existing
                and existing.source_revision == slot.revision
                and all(getattr(existing, k) == v for k, v in data.items())
            ):
                report(
                    slot,
                    day,
                    "This dated session already matches the weekly default.",
                    existing,
                    outcome="Unchanged",
                )
                continue
            plans.append({"slot": slot, "day": day, "existing": existing, "data": data})
        day += timedelta(days=1)
    # Resolve the complete proposed schedule. A preserved session remains an obstacle
    # for every other move; repeat until preserving one move cannot invalidate another.
    while plans:
        moving_ids = [p["existing"].pk for p in plans if p["existing"]]
        rejected = []
        for plan in plans:
            data = plan["data"]
            conflicts = list(
                overlapping_sessions(data["starts_at"], data["ends_at"]).exclude(pk__in=moving_ids)
            )
            peer_conflicts = [
                p
                for p in plans
                if p is not plan
                and p["data"]["starts_at"] < data["ends_at"]
                and p["data"]["ends_at"] > data["starts_at"]
            ]
            if conflicts or peer_conflicts:
                details = [
                    {
                        "id": row.pk,
                        "label": row.private_label,
                        "time": row.starts_at.astimezone(NEW_YORK).strftime("%I:%M %p"),
                        "end_time": row.ends_at.astimezone(NEW_YORK).strftime("%I:%M %p"),
                        "closed": row.closed or date_closed(row) or weekly_default_blocked(row),
                        "has_bookings": row.bookings.exists(),
                    }
                    for row in conflicts
                ]
                reason = (
                    "Conflicts with another dated session; review it individually."
                    if conflicts
                    else "Proposed weekly sessions overlap on this date."
                )
                report(plan["slot"], plan["day"], reason, plan["existing"], conflicts=details)
                rejected.append(plan)
        if not rejected:
            break
        plans = [p for p in plans if p not in rejected]
    # Temporarily park eligible rows inside this transaction to permit start-time
    # swaps under the unique-start constraint. No temporary values are committed.
    parked = timezone.now().replace(
        year=9000, month=1, day=1, hour=0, minute=0, second=0, microsecond=0
    )
    for plan in plans:
        row = plan["existing"]
        if row:
            plan["before"] = values(row, SESSION_FIELDS)
            while Session.objects.filter(starts_at=parked).exists():
                parked += timedelta(days=1)
            Session.objects.filter(pk=row.pk).update(
                starts_at=parked, ends_at=parked + timedelta(hours=1)
            )
            parked += timedelta(days=1)
    for plan in plans:
        row = plan["existing"] or Session()
        for key, value in plan["data"].items():
            setattr(row, key, value)
        if row.pk:
            row.revision += 1
        row.source_slot = plan["slot"]
        row.source_day = plan["day"]
        row.source_revision = plan["slot"].revision
        row.recurring_managed = True
        row.full_clean()
        row.save()
        AuditEvent.objects.create(
            actor=actor,
            action="schedule.session_updated" if plan["existing"] else "schedule.session_created",
            record_type="session",
            record_id=str(row.pk),
            changes={
                "before": plan.get("before"),
                "after": values(row, SESSION_FIELDS),
                "revision": row.revision,
            },
        )
        results.append(
            {
                "day": plan["day"].isoformat(),
                "slot": plan["slot"].label,
                "outcome": "Updated" if plan["existing"] else "Created",
                "session_id": row.pk,
                "session_revision": row.revision,
                "reason": "Closed obsolete generated session." if row.closed else "",
            }
        )
    results.sort(key=lambda result: (result["day"], result["slot"]))
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
