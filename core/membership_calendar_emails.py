"""Current, explicitly requested date updates preserve prior message evidence."""

from django.conf import settings

from .communications.models import MessageDelivery, MessageEvent
from .membership_calendar_changes import available
from .membership_calendar_records import MembershipCalendarMessage, MembershipCalendarState
from .payments.ledger import fingerprint


def cancel_unattempted(message, code="membership_dates_changed"):
    if message.state != "queued" or message.dispatched_at is not None:
        return
    message.state, message.code = "cancelled", code
    message.save(update_fields=["state", "code"])
    MessageEvent.objects.create(delivery=message, state="cancelled", code=code)


def source_for(member):
    if not available():
        return None
    state = (
        MembershipCalendarState.objects.select_related("correction")
        .filter(purchase_id=member.pk)
        .first()
    )
    return state.correction if state else None


def supersede(member):
    """A corrected calendar cannot leave an unsent original-date notice queued."""
    for message in MessageDelivery.objects.filter(
        membership_id=member.pk,
        state="queued",
        dispatched_at__isnull=True,
        kind__in=[
            "membership_confirmation",
            "membership_expiry_notice",
            "membership_grace_notice",
            "membership_requested_renewal",
        ],
    ):
        cancel_unattempted(message)


def queue(correction):
    from .communications.services import enqueue
    from .date_display import display_date
    from .membership_calendar_changes import member_record
    from .membership_reservations import payment_current

    member = member_record(correction.purchase_id)
    current = source_for(member)
    if (
        current is None
        or current.pk != correction.pk
        or not correction.send_confirmation
        or not settings.BOOKING_EMAIL_ENABLED
        or not member.customer.email
        or member.billing_state.stopped_on
        or not payment_current(member)
    ):
        for link in correction.messages.select_related("message"):
            cancel_unattempted(link.message)
        return None
    key = f"membership-calendar:{correction.pk}:" + fingerprint(
        dict(email=member.customer.email.casefold(), revision=member.customer.revision)
    )
    links = list(correction.messages.select_related("message"))
    for link in links:
        if link.message.dedupe_key == key:
            return (
                link.message
                if link.message.state == "queued" and link.message.dispatched_at is None
                else None
            )
    if any(
        link.message.dispatched_at is not None or link.message.state not in {"queued", "cancelled"}
        for link in links
    ):
        return None
    for link in links:
        cancel_unattempted(link.message, "contact_changed")
    root = member.membership
    text = "\n".join(
        [
            f"Dear Family {member.customer.last_name},",
            "",
            "Your membership dates have been updated:",
            "",
            f"{root.places} {root.get_kind_display()} Membership"
            + ("s" if root.places != 1 else ""),
            f"Begins: {display_date(correction.starts_on, 'F j, Y')}",
            f"Ends: {display_date(correction.ends_on, 'F j, Y')}",
            "",
            "We look forward to seeing you!",
            "",
            "The Monkey Do team",
        ]
    )
    message = enqueue(
        key=key,
        kind="membership_confirmation",
        recipient=member.customer.email,
        subject="Your Monkey Do membership dates have been updated",
        text=text,
        customer=member.customer,
        membership=member,
        actor=correction.actor,
    )
    MembershipCalendarMessage.objects.create(correction=correction, message=message)
    return message


def refresh_for_claim(message):
    """Return eligibility and the typed source for any further contact refresh."""
    if message.kind != "membership_confirmation" or not message.membership_id or not available():
        return True, None
    link = (
        MembershipCalendarMessage.objects.select_related("correction")
        .filter(message=message)
        .first()
    )
    if link:
        refreshed = queue(link.correction)
        return bool(
            refreshed and refreshed.pk == message.pk and refreshed.state == "queued"
        ), link.correction
    if message.dedupe_key == f"membership-confirmation:{message.membership_id}" and source_for(
        message.membership
    ):
        cancel_unattempted(message)
        return False, None
    return True, None
