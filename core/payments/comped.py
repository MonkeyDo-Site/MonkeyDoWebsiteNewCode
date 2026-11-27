"""Owner-reviewed full complimentary ordinary bookings; no payment/card obligation."""

from django.core.exceptions import ValidationError
from django.db import transaction

from core.booking_management import check_editable, write_quote
from core.models import AuditEvent, Booking
from core.permissions import require_actor

from .amounts import amount
from .checkout import authorize
from .methods import queue_disposal
from .models import BookingChargeState


@transaction.atomic
def set_price(*, actor, booking_id, version, comped, special_admissions=None):
    authorize(actor)
    require_actor(actor, "core.change_booking", owner=True)
    if type(comped) is not bool:
        raise ValidationError("Review the complimentary-booking choice.")
    special = amount(special_admissions) if special_admissions is not None else None
    if comped and special is not None:
        raise ValidationError(
            "Choose either a special admissions price or a fully complimentary booking."
        )
    booking = Booking.objects.select_for_update().select_related("session").get(pk=booking_id)
    if booking.workflow != "integrated_v1" or booking.session.kind != "ordinary":
        raise ValidationError("Use a new ordinary integrated booking.")
    check_editable(booking, version)
    state, _ = BookingChargeState.objects.select_for_update().get_or_create(booking=booking)
    if state.comped == comped and state.special_subtotal == special:
        return booking
    quote = booking.quotes.first()
    if quote is None:
        raise ValidationError("This booking has no saved pricing policy.")
    before = state.comped
    previous_special = state.special_subtotal
    state.comped = comped
    state.special_subtotal = special
    if comped or special is not None:
        state.pending_fee_units = 0
    state.revision += 1
    state.save(update_fields=["comped", "revision", "special_subtotal", "pending_fee_units"])
    booking.edit_version += 1
    # Staff must explicitly confirm the revised setup and waiver instructions.
    if before != comped:
        booking.setup_pending = True
    booking.save(update_fields=["edit_version", "setup_pending"])
    write_quote(booking, quote.policy, actor)
    from core import membership_booking

    if membership_booking.active(booking):
        if booking.setup_pending:
            import uuid

            from core.membership_reservations import finish

            finish(
                actor=actor,
                booking_id=booking.pk,
                request_key=uuid.uuid5(booking.reference, f"owner-price:{booking.edit_version}"),
                action="released",
                reason="booking_changed",
            )
        else:
            membership_booking.confirm(booking, actor=actor)
    if comped:
        try:
            agreement = booking.card_agreement
        except Booking.card_agreement.RelatedObjectDoesNotExist:
            agreement = None
        if agreement:
            from django.utils import timezone

            agreement.resolved_at = timezone.now()
            agreement.save(update_fields=["resolved_at"])
            queue_disposal(agreement.method)
    AuditEvent.objects.create(
        actor=actor,
        action="booking.owner_price_changed",
        record_type="booking",
        record_id=str(booking.reference),
        changes={
            "comped": {"before": before, "after": comped},
            "special_admissions": {
                "before": str(previous_special)
                if previous_special is not None
                else "Standard pricing",
                "after": str(special) if special is not None else "Standard pricing",
            },
        },
    )
    return booking


def set_comped(*, actor, booking_id, version, comped):
    return set_price(actor=actor, booking_id=booking_id, version=version, comped=comped)


def notify_count_change(*, actor, booking, before, special):
    """An owner can optionally adjust a retained fixed price; no automatic fee."""
    keys = ("children", "adults", "babies", "supervised")
    if (
        special is None
        or actor.is_superuser
        or all(before[key] == getattr(booking, key) for key in keys)
    ):
        return
    from core.models import OwnerNotice

    OwnerNotice.objects.create(
        customer=booking.customer,
        subject="Special-price booking attendee details changed",
        details={
            "kind": "special_price_headcount",
            "booking_id": booking.pk,
            "booking_reference": str(booking.reference),
            "admissions_total": str(special),
            "before": {key: before[key] for key in keys},
            "after": {key: getattr(booking, key) for key in keys},
        },
    )
