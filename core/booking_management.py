"""Staff test reservations only. No confirmation, waiver assertion or payment."""

import uuid

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.utils import timezone

from .calendar import date_closed, lock_calendar, weekly_default_blocked
from .models import AuditEvent, Booking, BookingQuote, PricingPolicy, Session
from .permissions import require_actor
from .pricing import booking_quote, validate_attendees


def snapshot(booking):
    return {
        key: getattr(booking, key)
        for key in (
            "session_id",
            "children",
            "adults",
            "babies",
            "socks",
            "supervised",
            "expected_method",
            "attendance",
            "edit_version",
        )
    }


def assert_capacity(
    session, *, booking_id=None, children, adults, supervised, override=False, actor
):
    if override:
        if not actor.is_superuser:
            raise ValidationError("Only the owner may override advance capacity.")
    if (supervised and session.play_mode == "accompanied") or (
        not supervised and session.play_mode == "supervised"
    ):
        raise ValidationError("This play type is not enabled for the session.")
    now = timezone.now()
    if (
        session.closed
        or date_closed(session)
        or weekly_default_blocked(session)
        or session.kind != Session.Kind.ORDINARY
    ):
        raise ValidationError("This session is blocked for ordinary reservations.")
    if now >= session.ends_at or (supervised and now >= session.starts_at):
        raise ValidationError("This session is no longer open for the selected play type.")
    bookings = session.bookings.exclude(attendance=Booking.Attendance.CANCELLED)
    if booking_id:
        bookings = bookings.exclude(pk=booking_id)
    counts = list(bookings.values("children", "adults", "supervised"))
    used_children = sum(row["children"] for row in counts)
    used_adults = sum(row["adults"] for row in counts)
    used_supervised = sum(row["children"] for row in counts if row["supervised"])
    if supervised and session.supervised_capacity == 0:
        raise ValidationError("Supervised play is not enabled for this session.")
    over = (
        used_children + children > session.child_capacity
        or used_children + used_adults + children + adults > session.total_capacity
    )
    over = over or (supervised and used_supervised + children > session.supervised_capacity)
    if over and not override:
        raise ValidationError("The requested attendees exceed available capacity.")


def check_editable(booking, version):
    if booking.edit_version != version:
        raise ValidationError(
            "Booking changed while you were editing. Reload and review the latest record."
        )
    if not booking.setup_pending or booking.attendance:
        raise ValidationError(
            "Only a pending test reservation can be edited in this development increment."
        )


def write_quote(booking, policy, actor):
    data = booking_quote(
        policy,
        children=booking.children,
        adults=booking.adults,
        babies=booking.babies,
        socks=booking.socks,
        supervised=booking.supervised,
        expected_method=booking.expected_method,
    )
    return BookingQuote.objects.create(
        booking=booking, policy=policy, revision=booking.edit_version, snapshot=data, actor=actor
    )


@transaction.atomic
def create_test_booking(
    *,
    actor,
    customer,
    session_id,
    children,
    adults,
    babies=0,
    socks=0,
    supervised=False,
    expected_method="card",
    creation_key,
    override_capacity=False,
):
    lock_calendar()
    require_actor(actor, "core.add_booking")
    require_actor(actor, "core.view_customer")
    require_actor(actor, "core.view_booking")
    validate_attendees(children, adults, babies, supervised, socks)
    try:
        key = uuid.UUID(str(creation_key))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("A valid submission identifier is required.") from None
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(%s, %s)",
                [73215, int.from_bytes(key.bytes[:4], signed=True)],
            )
    existing = Booking.objects.filter(creation_key=key).first()
    if existing:
        same = (
            existing.creation_actor_id == actor.pk
            and existing.customer_id == customer.pk
            and existing.session_id == session_id
            and (
                existing.children,
                existing.adults,
                existing.babies,
                existing.socks,
                existing.supervised,
                existing.expected_method,
            )
            == (children, adults, babies, socks, supervised, expected_method)
        )
        if not same:
            raise ValidationError(
                "This submission identifier was already used. Reload to start another reservation."
            )
        return existing
    try:
        session = Session.objects.select_for_update().get(pk=session_id)
    except Session.DoesNotExist:
        raise ValidationError("This session is no longer available. Choose another time.") from None
    assert_capacity(
        session,
        children=children,
        adults=adults,
        supervised=supervised,
        override=override_capacity,
        actor=actor,
    )
    policy = PricingPolicy.objects.first()
    if not policy:
        raise ValidationError("Pricing policy is not initialized. Run the reviewed migrations.")
    booking = Booking.objects.create(
        customer=customer,
        session=session,
        children=children,
        adults=adults,
        babies=babies,
        socks=socks,
        supervised=supervised,
        expected_method=expected_method,
        creation_key=key,
        creation_actor=actor,
    )
    quote = write_quote(booking, policy, actor)
    AuditEvent.objects.create(
        actor=actor,
        action="booking.test_created",
        record_type="booking",
        record_id=str(booking.reference),
        changes={
            "after": snapshot(booking),
            "quote_id": quote.pk,
            "capacity_override": override_capacity,
        },
    )
    return booking


@transaction.atomic
def edit_test_booking(
    *,
    actor,
    booking_id,
    version,
    children,
    adults,
    babies,
    socks,
    expected_method,
    override_capacity=False,
):
    lock_calendar()
    require_actor(actor, "core.change_booking")
    require_actor(actor, "core.view_booking")
    booking = Booking.objects.select_for_update().get(pk=booking_id)
    check_editable(booking, version)
    validate_attendees(children, adults, babies, booking.supervised, socks)
    session = Session.objects.select_for_update().get(pk=booking.session_id)
    assert_capacity(
        session,
        booking_id=booking.pk,
        children=children,
        adults=adults,
        supervised=booking.supervised,
        override=override_capacity,
        actor=actor,
    )
    current = booking.quotes.first()
    if not current:
        raise ValidationError(
            "This earlier test record has no saved price snapshot. Automatic repricing is disabled."
        )
    before = snapshot(booking)
    booking.children, booking.adults, booking.babies, booking.socks = (
        children,
        adults,
        babies,
        socks,
    )
    booking.expected_method = expected_method
    booking.edit_version += 1
    booking.save()
    quote = write_quote(booking, current.policy, actor)
    AuditEvent.objects.create(
        actor=actor,
        action="booking.attendees_changed",
        record_type="booking",
        record_id=str(booking.reference),
        changes={
            "before": before,
            "after": snapshot(booking),
            "quote_id": quote.pk,
            "capacity_override": override_capacity,
        },
    )
    return booking


@transaction.atomic
def move_test_booking(*, actor, booking_id, version, session_id, override_capacity=False):
    lock_calendar()
    require_actor(actor, "core.change_booking")
    require_actor(actor, "core.view_booking")
    booking = Booking.objects.select_for_update().get(pk=booking_id)
    check_editable(booking, version)
    # Deterministic lock order protects reciprocal moves from overselling/deadlock.
    sessions = {
        session.pk: session
        for session in Session.objects.select_for_update()
        .filter(pk__in={booking.session_id, session_id})
        .order_by("pk")
    }
    if session_id not in sessions:
        raise ValidationError("Target session does not exist.")
    target = sessions[session_id]
    assert_capacity(
        target,
        booking_id=booking.pk,
        children=booking.children,
        adults=booking.adults,
        supervised=booking.supervised,
        override=override_capacity,
        actor=actor,
    )
    before = snapshot(booking)
    booking.session = target
    booking.edit_version += 1
    booking.save()
    AuditEvent.objects.create(
        actor=actor,
        action="booking.timing_changed",
        record_type="booking",
        record_id=str(booking.reference),
        changes={
            "before": before,
            "after": snapshot(booking),
            "capacity_override": override_capacity,
        },
    )
    return booking


@transaction.atomic
def release_test_booking(*, actor, booking_id, version):
    lock_calendar()
    require_actor(actor, "core.change_booking")
    require_actor(actor, "core.view_booking")
    booking = Booking.objects.select_for_update().get(pk=booking_id)
    check_editable(booking, version)
    Session.objects.select_for_update().get(pk=booking.session_id)
    before = snapshot(booking)
    booking.attendance = Booking.Attendance.CANCELLED
    booking.edit_version += 1
    booking.save()
    AuditEvent.objects.create(
        actor=actor,
        action="booking.test_released",
        record_type="booking",
        record_id=str(booking.reference),
        changes={"before": before, "after": snapshot(booking), "fee_processed": False},
    )
    return booking
