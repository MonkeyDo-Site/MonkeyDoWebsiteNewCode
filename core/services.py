"""Internal reservation primitive. No public checkout until payment/waiver integration."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .availability import availability, occupancy
from .calendar import lock_calendar
from .models import AuditEvent, Booking, Session, SiteSettings


@transaction.atomic
def reserve_booking(*, actor, customer, session_id, children, adults, babies=0, supervised=False):
    lock_calendar()
    if not actor.is_active or not actor.is_staff or not actor.has_perm("core.add_booking"):
        raise PermissionError("Booking permission is required.")
    if any(type(n) is not int or n < 0 for n in (children, adults, babies)):
        raise ValidationError("Attendee counts must be nonnegative integers.")
    if not children + adults + babies:
        raise ValidationError("At least one attendee is required.")
    if supervised and (not children or adults or babies):
        raise ValidationError("Supervised bookings contain children only.")
    if not supervised and adults < 1:
        raise ValidationError("Accompanied play requires an adult.")
    try:
        session = Session.objects.select_for_update().get(pk=session_id)
    except Session.DoesNotExist:
        raise ValidationError("This session is no longer available. Choose another time.") from None
    if (supervised and session.play_mode == "accompanied") or (
        not supervised and session.play_mode == "supervised"
    ):
        raise ValidationError("This play type is not enabled for the session.")
    horizon = (
        SiteSettings.objects.filter(pk=1).values_list("booking_horizon_days", flat=True).first()
        or 1
    )
    state = availability(session, horizon)
    if not state["available"]:
        raise ValidationError(state["label"])
    used_children, used_adults, used_supervised = occupancy(session)
    if (
        used_children + children > session.child_capacity
        or used_children + used_adults + children + adults > session.total_capacity
    ):
        raise ValidationError("The requested attendees exceed session capacity.")
    if supervised and (
        timezone.now() >= session.starts_at
        or used_supervised + children > session.supervised_capacity
    ):
        raise ValidationError("Supervised play is unavailable.")
    booking = Booking.objects.create(
        customer=customer,
        session=session,
        children=children,
        adults=adults,
        babies=babies,
        supervised=supervised,
    )
    AuditEvent.objects.create(
        actor=actor,
        action="booking.reserved",
        record_type="booking",
        record_id=str(booking.reference),
        changes={
            "session_id": session.pk,
            "children": children,
            "adults": adults,
            "babies": babies,
        },
    )
    return booking
