"""Thirty-minute staff capacity reservations, shared by every booking entry point."""

from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from .calendar import lock_calendar
from .models import BookingCapacityHold, Session
from .permissions import require_actor


def describe(key, actor):
    hold = BookingCapacityHold.objects.filter(pk=key, actor=actor).first()
    if not hold:
        return {"active": False}
    return {
        "active": hold.expires_at > timezone.now(),
        "seconds_remaining": max(0, int((hold.expires_at - timezone.now()).total_seconds())),
        "expires_at": hold.expires_at.isoformat(),
        "children": hold.children,
        "adults": hold.adults,
        "babies": hold.babies,
        "session_id": hold.session_id,
    }


@transaction.atomic
def reserve(
    *,
    key,
    actor,
    customer,
    session,
    children,
    adults,
    babies,
    supervised,
    override=False,
    renew=False,
):
    from .booking_management import assert_capacity
    from .payments.ledger import lock_request
    from .pricing import validate_attendees

    for permission in ("core.add_booking", "core.view_customer", "core.change_booking"):
        require_actor(actor, permission)
    lock_calendar()
    key = lock_request(key)
    hold = BookingCapacityHold.objects.select_for_update().filter(pk=key).first()
    if hold and hold.actor_id != actor.pk:
        raise PermissionDenied
    # Use the same session lock as actual bookings so competing callers cannot
    # both reserve the last places. Moving locks old and new sessions in order.
    sessions = {
        row.pk: row
        for row in Session.objects.select_for_update()
        .filter(pk__in={session.pk, hold.session_id if hold else session.pk})
        .order_by("pk")
    }
    current = sessions[session.pk]
    values = {
        "customer_id": customer.pk,
        "session_id": current.pk,
        "children": children,
        "adults": adults,
        "babies": babies,
        "supervised": supervised,
    }
    changed = hold is None or any(getattr(hold, key) != value for key, value in values.items())
    if hold and not changed and not renew and hold.expires_at <= timezone.now():
        return describe(key, actor)
    validate_attendees(children, adults, babies, supervised)
    assert_capacity(
        current,
        children=children,
        adults=adults,
        supervised=supervised,
        override=override,
        actor=actor,
        hold_key=key,
    )
    if hold is None:
        hold = BookingCapacityHold(id=key, actor=actor, **values)
    else:
        for name, value in values.items():
            setattr(hold, name, value)
    # Payment/waiver edits and polling never extend a hold. Explicit renewal,
    # changed counts/customer/session, or confirmation after expiry starts 30m.
    if changed or (renew and hold.expires_at <= timezone.now()):
        hold.expires_at = timezone.now() + timedelta(minutes=30)
    hold.save()
    return describe(key, actor)
