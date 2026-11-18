"""Owner-managed reservation blocks with independent, auditable sources."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .calendar import lock_calendar
from .models import AuditEvent, Booking, Session, SessionReservationBlock
from .permissions import require_actor


class SessionConflict(ValidationError):
    def __init__(
        self,
        bookings=None,
        message="Existing bookings prevent this custom session. Move or cancel the linked bookings first.",
    ):
        self.bookings = list(bookings or [])
        super().__init__(message)


def active_bookings(sessions):
    return (
        Booking.objects.filter(session__in=sessions)
        .exclude(attendance=Booking.Attendance.CANCELLED)
        .select_related("customer", "session")
        .order_by("session__starts_at", "pk")
    )


def audit_block(actor, block, active):
    AuditEvent.objects.create(
        actor=actor,
        action="schedule.reservation_block_changed",
        record_type="session",
        record_id=str(block.session_id),
        changes={
            "block_id": block.pk,
            "source_session_id": block.source_session_id,
            "booking_id": block.booking_id,
            "active": active,
        },
    )


def sync_custom_blocks(actor, session, conflicts, *, reopen_removed=False):
    """Caller holds the exclusive calendar lock and transaction."""
    ids = {row.pk for row in conflicts}
    if reopen_removed:
        for block in (
            session.caused_blocks.select_for_update()
            .filter(active=True)
            .exclude(session_id__in=ids)
        ):
            block.active = False
            block.save(update_fields=["active"])
            audit_block(actor, block, False)
    for target in conflicts:
        block, created = SessionReservationBlock.objects.get_or_create(
            session=target, source_session=session, defaults={"actor": actor}
        )
        if created or not block.active:
            block.active = True
            block.save(update_fields=["active"])
            audit_block(actor, block, True)


def close_for_booking(actor, booking):
    require_actor(actor, "core.change_session", owner=True)
    block, created = SessionReservationBlock.objects.get_or_create(
        session=booking.session, booking=booking, defaults={"actor": actor}
    )
    if created or not block.active:
        block.active = True
        block.save(update_fields=["active"])
        audit_block(actor, block, True)


def booking_has_blocks(booking):
    return (
        booking.session_blocks.filter(active=True).exists()
        or booking.session.caused_blocks.filter(active=True).exists()
    )


def reopen_for_booking(actor, booking, old_session):
    require_actor(actor, "core.change_session", owner=True)
    for block in SessionReservationBlock.objects.select_for_update().filter(
        booking=booking, active=True
    ):
        block.active = False
        block.save(update_fields=["active"])
        audit_block(actor, block, False)
    if old_session.custom_blocking:
        if (
            old_session.bookings.exclude(pk=booking.pk)
            .exclude(attendance=Booking.Attendance.CANCELLED)
            .exists()
        ):
            raise ValidationError(
                "Other bookings still use this custom session. Move or cancel those bookings before reopening its affected sessions."
            )
        # Retain the custom interval/history but prevent fresh reservations in it.
        old_session.closed = True
        old_session.revision += 1
        old_session.save(update_fields=["closed", "revision"])
        for block in old_session.caused_blocks.select_for_update().filter(active=True):
            block.active = False
            block.save(update_fields=["active"])
            audit_block(actor, block, False)


@transaction.atomic
def reopen_custom(actor, session_id, revision):
    require_actor(actor, "core.change_session", owner=True)
    lock_calendar(exclusive=True)
    session = Session.objects.select_for_update().get(pk=session_id)
    if not session.custom_blocking or session.revision != revision:
        raise ValidationError(
            "Session changed. Reload its settings before reopening affected sessions."
        )
    if active_bookings([session]).exists():
        raise ValidationError(
            "Move or cancel the custom session's bookings before reopening affected sessions."
        )
    session.closed = True
    session.revision += 1
    session.save(update_fields=["closed", "revision"])
    sync_custom_blocks(actor, session, [], reopen_removed=True)
    AuditEvent.objects.create(
        actor=actor,
        action="schedule.custom_session_reopened",
        record_type="session",
        record_id=str(session.pk),
        changes={"closed": True, "at": timezone.now().isoformat()},
    )


def custom_preview(data):
    from django.core import signing

    from .calendar import overlapping_sessions

    conflicts = list(
        overlapping_sessions(data["starts_at"], data["ends_at"], exclude_pk=data.get("pk"))
    )
    bookings = active_bookings(conflicts)
    if bookings.exists():
        raise SessionConflict(bookings)
    if any(s.custom_blocking or s.kind != Session.Kind.ORDINARY for s in conflicts):
        raise SessionConflict(
            message="This custom time overlaps another custom or program session. Review that session first."
        )
    payload = {
        "start": data["starts_at"].isoformat(),
        "end": data["ends_at"].isoformat(),
        "sessions": sorted((s.pk, s.revision) for s in conflicts),
    }
    return conflicts, signing.dumps(payload, salt="custom-session-preview"), payload
