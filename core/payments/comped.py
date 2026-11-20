"""Owner-reviewed full complimentary ordinary bookings; no payment/card obligation."""

from django.core.exceptions import ValidationError
from django.db import transaction

from core.booking_management import check_editable, write_quote
from core.models import AuditEvent, Booking
from core.permissions import require_actor

from .checkout import authorize
from .methods import queue_disposal
from .models import BookingChargeState


@transaction.atomic
def set_comped(*, actor, booking_id, version, comped):
    authorize(actor)
    require_actor(actor, "core.change_booking", owner=True)
    if type(comped) is not bool:
        raise ValidationError("Review the complimentary-booking choice.")
    booking = Booking.objects.select_for_update().select_related("session").get(pk=booking_id)
    if booking.workflow != "integrated_v1" or booking.session.kind != "ordinary":
        raise ValidationError("Use a new ordinary integrated booking.")
    check_editable(booking, version)
    state, _ = BookingChargeState.objects.select_for_update().get_or_create(booking=booking)
    if state.comped == comped:
        return booking
    quote = booking.quotes.first()
    if quote is None:
        raise ValidationError("This booking has no saved pricing policy.")
    before = state.comped
    state.comped = comped
    state.revision += 1
    state.save(update_fields=["comped", "revision"])
    booking.edit_version += 1
    # Staff must explicitly confirm the revised setup and waiver instructions.
    booking.setup_pending = True
    booking.save(update_fields=["edit_version", "setup_pending"])
    write_quote(booking, quote.policy, actor)
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
        action="booking.complimentary_changed",
        record_type="booking",
        record_id=str(booking.reference),
        changes={"comped": {"before": before, "after": comped}},
    )
    return booking
