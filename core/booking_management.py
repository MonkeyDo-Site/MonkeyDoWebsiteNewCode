"""Staff test reservations only. No confirmation, waiver assertion or payment."""

import uuid

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.utils import timezone

from .calendar import date_closed, lock_calendar, reservation_blocked, weekly_default_blocked
from .models import AuditEvent, Booking, BookingQuote, PricingPolicy, Session
from .permissions import require_actor
from .pricing import booking_quote, validate_attendees
from .session_blocks import close_for_booking, reopen_for_booking


def snapshot(booking):
    return {
        "session_starts_at": booking.session.starts_at.isoformat(),
        "session_ends_at": booking.session.ends_at.isoformat(),
        **{
            key: getattr(booking, key)
            for key in (
                "session_id",
                "children",
                "adults",
                "babies",
                "socks",
                "supervised",
                "referral_source",
                "expected_method",
                "zelle_sender",
                "attendance",
                "edit_version",
            )
        },
    }


def assert_capacity(
    session,
    *,
    booking_id=None,
    children,
    adults,
    supervised,
    override=False,
    actor,
    supervised_exception=False,
    hold_key=None,
):
    if override:
        if not actor.is_superuser:
            raise ValidationError("Only the owner may override advance capacity.")
    from .payments.models import BookingChargeState

    existing_exception = (
        booking_id
        and BookingChargeState.objects.filter(
            booking_id=booking_id, supervised_exception_session=session
        ).exists()
    )
    if type(supervised_exception) is not bool:
        raise ValidationError("Review the booking-specific supervised exception.")
    if supervised_exception and (not booking_id or actor is None or not actor.is_superuser):
        raise ValidationError("Only the owner may approve a supervised exception for this booking.")
    exception = supervised and (supervised_exception or existing_exception)
    if (supervised and session.play_mode == "accompanied" and not exception) or (
        not supervised and session.play_mode == "supervised"
    ):
        raise ValidationError(
            "This session is marked as open play only. Do you want to change this booking only to supervised play?"
            if supervised
            else "This play type is not enabled for the session.",
            code="supervised_exception_required" if supervised else None,
        )
    now = timezone.now()
    if (
        session.closed
        or date_closed(session)
        or reservation_blocked(session, ignore_booking_id=booking_id)
        or weekly_default_blocked(session)
        or session.kind != Session.Kind.ORDINARY
    ):
        raise ValidationError("This session is blocked for ordinary reservations.")
    if now >= session.ends_at or (supervised and not exception and now >= session.starts_at):
        raise ValidationError(
            "This session is no longer open for the selected play type.",
            code="supervised_exception_required" if supervised and now < session.ends_at else None,
        )
    from .availability import occupancy

    used_children, used_adults, used_supervised = occupancy(
        session, ignore_booking_id=booking_id, ignore_hold=hold_key
    )
    if supervised and not exception and session.supervised_capacity == 0:
        raise ValidationError(
            "Supervised play is not enabled for this session.",
            code="supervised_exception_required",
        )
    over = (
        used_children + children > session.child_capacity
        or used_children + used_adults + children + adults > session.total_capacity
    )
    over = over or (
        supervised and not exception and used_supervised + children > session.supervised_capacity
    )
    if over and not override:
        if actor is not None:
            if (
                supervised
                and not exception
                and used_supervised + children > session.supervised_capacity
            ):
                reminder = (
                    f"The supervised play capacity for this session is {session.supervised_capacity}, "
                    f"of which {used_supervised} slots are already booked."
                )
            elif used_children + children > session.child_capacity:
                reminder = (
                    f"The child capacity for this session is {session.child_capacity}, "
                    f"of which {used_children} slots are already booked."
                )
            else:
                reminder = (
                    f"The total available capacity for this session is {session.total_capacity}, "
                    f"of which {used_children + used_adults} slots are already booked."
                )
            raise ValidationError(
                reminder
                + (
                    " Check the owner override checkbox to proceed."
                    if actor.is_superuser
                    else " Ask the owner to approve a capacity override to proceed."
                )
            )
        if (
            supervised
            and not exception
            and used_supervised + children > session.supervised_capacity
        ):
            raise ValidationError(
                f"The supervised play capacity for this session is {session.supervised_capacity}, of which {used_supervised} places are already booked. The amount of children you entered goes beyond the available capacity. Please enter a smaller amount, "
                + ("choose open play, " if session.play_mode != "supervised" else "")
                + "choose another session time, or call 848-238-5147 for assistance.",
                code="session_capacity",
            )
        if used_children + children > session.child_capacity:
            raise ValidationError(
                f"The child capacity for this session is {session.child_capacity}, of which {used_children} slots are already booked. The amount of children you entered goes beyond the available capacity. Please enter a smaller amount or choose another session time. You can call 848-238-5147 for further assistance.",
                code="session_capacity",
            )
        raise ValidationError(
            f"The total available capacity for this session is {session.total_capacity}, of which {used_children + used_adults} slots are already booked. The amount of children you entered is within capacity limits, however the amount of adults you entered exceeds total capacity. Please enter a smaller number of adults or call 848-238-5147 for further assistance.",
            code="session_capacity",
        )


def check_editable(booking, version):
    if booking.edit_version != version:
        raise ValidationError(
            "Booking changed while you were editing. Reload and review the latest record."
        )
    if booking.workflow == "integrated_v1":
        from .membership_arrival_pending import check_access

        check_access(booking)
        from .booking_completion import enabled
        from .payments.models import PaymentOperation

        enabled()
        if (
            booking.attendance
            or PaymentOperation.objects.filter(
                sale__booking=booking,
                state__in=["ready", "sending", "unknown", "action", "succeeded"],
            ).exists()
        ):
            raise ValidationError(
                "Review the recorded attendance/payment before changing this booking."
            )
        return
    if not booking.setup_pending or booking.attendance:
        raise ValidationError(
            "Only a pending test reservation can be edited in this development increment."
        )


def calculate_quote(booking, policy, values=None):
    from . import membership_booking

    if membership_booking.active(booking):
        return membership_booking.booking_quote(booking, policy, values)
    fields = ("children", "adults", "babies", "socks", "supervised", "expected_method")
    editing = values is not None
    values = values or {key: getattr(booking, key) for key in fields}
    special_choice = values.get("special_admissions")
    values = {key: values[key] for key in fields}
    data = booking_quote(policy, **values)
    if booking.workflow == "integrated_v1":
        from decimal import Decimal

        from .payments.checkout_pricing import visit_lines
        from .payments.models import BookingChargeState
        from .pricing import Line, quote_lines

        state = BookingChargeState.objects.filter(booking=booking).first()
        units = max(
            0,
            (state.pending_fee_units if state else 0)
            + (booking.children - values["children"] if editing else 0),
        )
        comped = bool(state and state.comped)
        special = (
            special_choice
            if special_choice is not None
            else state.special_subtotal
            if state
            else None
        )
        if units or comped or special is not None:
            standard_lines = list(data["lines"])
            lines = visit_lines(
                policy,
                **{key: values[key] for key in fields if key != "expected_method"},
                fee_units=0 if special is not None else units,
                special_admissions=special,
            )
            if comped:
                lines = [
                    Line(line.label, line.quantity, Decimal("0.00"), line.taxable) for line in lines
                ]
            data = quote_lines(
                lines,
                policy,
                card_base=None
                if values["expected_method"] == "card" and not comped
                else Decimal("0.00"),
            )
            data.update(
                expected_method=values["expected_method"],
                membership_benefits_applied=False,
                owner_comped=comped,
                owner_special_admissions=str(special) if special is not None else None,
                standard_admission_lines=[
                    row
                    for row in standard_lines
                    if row["label"] != "Grip socks — pick up upon arrival"
                ],
            )
    return data


def write_quote(booking, policy, actor, *, apply_available_benefits=False):
    from .membership_booking import lock

    lock(booking)
    return BookingQuote.objects.create(
        booking=booking,
        policy=policy,
        revision=booking.edit_version,
        snapshot=calculate_quote(
            booking,
            policy,
            {
                key: getattr(booking, key)
                for key in (
                    "children",
                    "adults",
                    "babies",
                    "socks",
                    "supervised",
                    "expected_method",
                )
            }
            | {"apply_available_benefits": True}
            if apply_available_benefits
            else None,
        ),
        actor=actor,
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
    referral_source="",
    close_session=False,
    workflow="legacy_test",
    zelle_sender="",
):
    if workflow == "integrated_v1":
        from .booking_completion import enabled

        enabled()
    elif workflow != "legacy_test":
        raise ValidationError("Choose a supported booking workflow.")
    from .payments.receipts import sender

    zelle_sender = sender(
        zelle_sender, required=workflow == "integrated_v1" and expected_method == "zelle"
    )
    lock_calendar(exclusive=close_session)
    if close_session:
        require_actor(actor, "core.change_session", owner=True)
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
    if not isinstance(referral_source, str) or len(referral_source) > 240:
        raise ValidationError("Referral source must be 240 characters or fewer.")
    referral_source = referral_source.strip()
    existing = Booking.objects.filter(creation_key=key).first()
    if existing:
        same = (
            existing.creation_actor_id == actor.pk
            and existing.workflow == workflow
            and existing.zelle_sender == zelle_sender
            and close_session == existing.session_blocks.exists()
            and existing.customer_id == customer.pk
            and existing.session_id == session_id
            and existing.referral_source == referral_source
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
        zelle_sender=zelle_sender,
        creation_key=key,
        creation_actor=actor,
        referral_source=referral_source,
        workflow=workflow,
    )
    quote = write_quote(booking, policy, actor)
    AuditEvent.objects.create(
        actor=actor,
        action="booking.test_created" if workflow == "legacy_test" else "booking.setup_started",
        record_type="booking",
        record_id=str(booking.reference),
        changes={
            "after": snapshot(booking),
            "quote_id": quote.pk,
            "capacity_override": override_capacity,
        },
    )
    if close_session:
        close_for_booking(actor, booking)
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
    session=None,
    supervised=None,
    payment_reviewed=None,
    referral_source=None,
    close_session=False,
    reopen_affected_sessions=False,
    zelle_sender=None,
    special_admissions=None,
    supervised_exception=False,
    apply_available_benefits=False,
    membership_resolution="",
    membership_resolution_reason="",
):
    lock_calendar(exclusive=close_session or reopen_affected_sessions)
    if close_session or reopen_affected_sessions:
        require_actor(actor, "core.change_session", owner=True)
    require_actor(actor, "core.change_booking")
    require_actor(actor, "core.view_booking")
    if type(apply_available_benefits) is not bool:
        raise ValidationError("Review the available membership benefit choice.")
    booking = Booking.objects.select_for_update().get(pk=booking_id)
    check_editable(booking, version)
    from .membership_booking_exceptions import persist as persist_membership_decision
    from .membership_booking_exceptions import resolve as resolve_membership_decision

    if membership_resolution:
        resolve_membership_decision(
            booking,
            actor=actor,
            choice=membership_resolution,
            reason=membership_resolution_reason,
            session=session,
        )
    target_id = session.pk if session is not None else booking.session_id
    supervised = booking.supervised if supervised is None else supervised
    sessions = {
        row.pk: row
        for row in Session.objects.select_for_update()
        .filter(pk__in={booking.session_id, target_id})
        .order_by("pk")
    }
    if target_id not in sessions:
        raise ValidationError("The selected session no longer exists.")
    session = sessions[target_id]
    validate_attendees(children, adults, babies, supervised, socks)
    assert_capacity(
        session,
        booking_id=booking.pk,
        children=children,
        adults=adults,
        supervised=supervised,
        override=override_capacity,
        actor=actor,
        supervised_exception=supervised_exception,
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
    old_session = booking.session
    booking.session = session
    booking.supervised = supervised
    booking.expected_method = expected_method
    if zelle_sender is not None:
        from .payments.receipts import sender

        booking.zelle_sender = sender(
            zelle_sender,
            required=booking.workflow == "integrated_v1" and expected_method == "zelle",
        )
    if referral_source is not None:
        if not isinstance(referral_source, str) or len(referral_source) > 240:
            raise ValidationError("Referral source must be 240 characters or fewer.")
        booking.referral_source = referral_source.strip()
    booking.edit_version += 1
    booking.save()
    if booking.workflow == "integrated_v1":
        from .payments.models import BookingChargeState
        from .waivers.models import BookingWaiverReview

        state, _ = BookingChargeState.objects.get_or_create(booking=booking)
        if membership_resolution:
            from .membership_booking import lock

            lock(booking)
            persist_membership_decision(
                actor=actor,
                booking=booking,
                state=state,
                choice=membership_resolution,
                reason=membership_resolution_reason,
                request_key=uuid.uuid5(
                    booking.reference, f"owner-membership:{booking.edit_version}"
                ),
            )
        if supervised_exception:
            require_actor(actor, "core.change_booking", owner=True)
            state.supervised_exception_session = session
            state.save(update_fields=["supervised_exception_session"])
        old_special = state.special_subtotal
        if special_admissions is not None:
            from .payments.amounts import amount

            require_actor(actor, "core.change_booking", owner=True)
            if state.special_subtotal is None or state.comped:
                raise ValidationError(
                    "Use owner pricing settings to apply a special admissions price first."
                )
            state.special_subtotal = amount(special_admissions)
        state.pending_fee_units = (
            0
            if state.special_subtotal is not None or state.comped
            else max(0, state.pending_fee_units + before["children"] - booking.children)
        )
        state.revision += 1
        state.save(
            update_fields=[
                "pending_fee_units",
                "revision",
                "special_subtotal",
                "membership_decision",
            ]
        )
        booking.charge_state = state
        from .payments.comped import notify_count_change

        notify_count_change(
            actor=actor, booking=booking, before=before, special=state.special_subtotal
        )
        if old_special != state.special_subtotal:
            AuditEvent.objects.create(
                actor=actor,
                action="booking.owner_price_changed",
                record_type="booking",
                record_id=str(booking.reference),
                changes={
                    "special_admissions": {
                        "before": str(old_special),
                        "after": str(state.special_subtotal),
                    }
                },
            )
        if booking.children > before["children"] or booking.babies > before["babies"]:
            review = BookingWaiverReview.objects.filter(booking=booking).first()
            if review:
                review.coverage_confirmed = False
                review.paper_signed = False
                review.revision += 1
                review.save(
                    update_fields=["coverage_confirmed", "paper_signed", "revision", "updated_at"]
                )
    price_changed = any(
        before[field] != getattr(booking, field)
        for field in ("children", "adults", "babies", "socks", "supervised", "expected_method")
    )
    from . import membership_booking

    if membership_booking.active(booking):
        price_changed = (
            price_changed
            or old_session.pk != session.pk
            or apply_available_benefits
            or bool(membership_resolution)
        )
    if booking.workflow == "integrated_v1" and special_admissions is not None:
        price_changed = price_changed or old_special != state.special_subtotal
    quote = (
        write_quote(
            booking, current.policy, actor, apply_available_benefits=apply_available_benefits
        )
        if price_changed
        else current
    )
    if price_changed and not booking.setup_pending:
        membership_booking.confirm(booking, actor=actor)
    AuditEvent.objects.create(
        actor=actor,
        action="booking.updated",
        record_type="booking",
        record_id=str(booking.reference),
        changes={
            "before": before,
            "after": snapshot(booking),
            "quote_id": quote.pk,
            "capacity_override": override_capacity,
            "supervised_exception": supervised_exception,
        },
    )
    if reopen_affected_sessions:
        if old_session.pk == session.pk:
            raise ValidationError(
                "Choose a different session before reopening the original session’s blocks."
            )
        reopen_for_booking(actor, booking, old_session)
    if close_session:
        close_for_booking(actor, booking)
    return booking


@transaction.atomic
def move_test_booking(
    *,
    actor,
    booking_id,
    version,
    session_id,
    override_capacity=False,
    close_session=False,
    reopen_affected_sessions=False,
    zelle_sender=None,
):
    lock_calendar(exclusive=close_session or reopen_affected_sessions)
    if close_session or reopen_affected_sessions:
        require_actor(actor, "core.change_session", owner=True)
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
    old_session = booking.session
    booking.session = target
    booking.edit_version += 1
    booking.save()
    from . import membership_booking

    if membership_booking.active(booking):
        saved = booking.quotes.first()
        if saved is None:
            raise ValidationError("Review the current membership price before changing timing.")
        write_quote(booking, saved.policy, actor)
        if not booking.setup_pending:
            membership_booking.confirm(booking, actor=actor)
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
    if reopen_affected_sessions:
        if old_session.pk == target.pk:
            raise ValidationError(
                "Choose a different session before reopening the original session’s blocks."
            )
        reopen_for_booking(actor, booking, old_session)
    if close_session:
        close_for_booking(actor, booking)
    return booking


@transaction.atomic
def release_test_booking(*, actor, booking_id, version, reopen_affected_sessions=False):
    lock_calendar(exclusive=reopen_affected_sessions)
    if reopen_affected_sessions:
        require_actor(actor, "core.change_session", owner=True)
    require_actor(actor, "core.change_booking")
    require_actor(actor, "core.view_booking")
    booking = Booking.objects.select_for_update().get(pk=booking_id)
    if booking.workflow == "integrated_v1":
        raise ValidationError("Use the reviewed cancellation action for an integrated booking.")
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
    if reopen_affected_sessions:
        reopen_for_booking(actor, booking, booking.session)
    return booking
