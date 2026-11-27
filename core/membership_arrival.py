"""Reviewed in-person membership purchase and arrival share one atomic confirmation.

The prospective cohort exists only in pure price planning. Final arrival uses
the ordinary paid-membership planner after the manual purchase is recorded in
the same transaction. A failure rolls back the purchase, receipts and arrival.
"""

import copy
import uuid
from dataclasses import dataclass
from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction

from .availability import NEW_YORK
from .calendar import lock_calendar
from .membership_benefits import Place
from .membership_records import MembershipArrivalCheckout
from .membership_reservations import accepted_rules, lock_customer
from .membership_sales import authorize, offer, purchase, today
from .models import Booking, Customer, Session
from .payments import checkout
from .payments.amounts import ZERO, amount
from .payments.ledger import fingerprint, lock_request

# A pure preview identifier, replaced with the actual paid cohort at confirmation.
# No reservation, invoice or membership is ever saved with this identifier.
PROPOSED_ID = 9223372036854775807


@dataclass(frozen=True)
class ProposedMembership:
    offer: dict


def proposed_places(proposed, appointment_on, children):
    if not isinstance(proposed, ProposedMembership):
        raise ValidationError("Review the proposed membership with this arrival.")
    data = proposed.offer
    cycle = next(
        (row for row in data["cycles"] if row["starts_on"] <= appointment_on <= row["ends_on"]),
        None,
    )
    if cycle is None:
        return []
    return [
        Place(
            membership_id=PROPOSED_ID,
            number=number,
            kind=data["kind"],
            starts_on=date.fromisoformat(data["starts_on"]),
            ends_on=date.fromisoformat(data["ends_on"]),
            cycle_starts_on=cycle["starts_on"],
            cycle_ends_on=cycle["ends_on"],
            payments_current=True,
            rules=accepted_rules(data["rules"]),
        )
        for number in range(1, min(data["places"], children) + 1)
    ]


def normalized(facts, member_id=PROPOSED_ID):
    result = copy.deepcopy(facts)
    for use in result["quote"].get("membership_plan", {}).get("uses", []):
        if use["membership_id"] == member_id:
            use["membership_id"] = "new_membership"
    return result


def review(*, actor, booking_id, data, selection, method_id=None, validate_waivers=True):
    authorize(actor, collect=True)
    booking = Booking.objects.select_related("customer", "session").get(pk=booking_id)
    checkout.require_current(booking, "arrival")
    if booking.session.starts_at.astimezone(NEW_YORK).date() != today():
        raise ValidationError("Combine a membership purchase with arrival on the visit date.")
    tender = data.get("method")
    if tender not in {"cash", "check"}:
        raise ValidationError(
            "Choose cash or check for this combined payment, or clear the membership purchase to use another arrival payment."
        )
    # These values are derived from this booking, never supplied by the browser.
    values = selection | {"customer": booking.customer, "expected_method": tender}
    proposed = offer(actor=actor, **values)
    result = checkout.preview(
        actor=actor,
        booking_id=booking_id,
        kind="arrival",
        data=data | {"apply_available_benefits": True},
        validate_waivers=validate_waivers,
        proposed_membership=ProposedMembership(proposed),
    )
    membership_due = (
        amount(proposed.get("first_payment_total", proposed["installments"][0]["quote"]["total"]))
        if proposed["installments"]
        else ZERO
    )
    visit_due = sum((amount(p["amount"]) for p in result[3] if not p.get("advance")), ZERO)
    facts = {
        "booking": booking.pk,
        "actor": actor.pk,
        "offer": proposed["fingerprint"],
        "method_id": str(method_id) if method_id else None,
        "arrival": normalized(result[4]),
        "membership_due": str(membership_due),
        "visit_due": str(visit_due),
        "received_today": str(membership_due + visit_due),
    }
    return {
        "offer": proposed,
        "quote": result[2],
        "plan": result[3],
        "facts": facts,
        "fingerprint": fingerprint(facts),
    }


@transaction.atomic
def confirm(
    *,
    actor,
    booking_id,
    data,
    selection,
    method_id,
    request_key,
    reviewed_hash,
    confirmed,
    accepted,
    verified_received,
    send_confirmation=None,
):
    authorize(actor, collect=True)
    checkout.authorize(actor)
    if confirmed is not True or accepted is not True:
        raise ValidationError("Accept the membership terms and confirm the combined arrival.")
    key = lock_request(request_key)
    previous = MembershipArrivalCheckout.objects.select_related("checkout").filter(pk=key).first()
    if previous:
        if (
            previous.actor_id != actor.pk
            or previous.checkout.booking_id != booking_id
            or previous.fingerprint != reviewed_hash
        ):
            raise ValidationError(
                "This confirmation already identifies another purchase or arrival."
            )
        return previous
    lock_calendar()
    booking = Booking.objects.select_for_update().get(pk=booking_id)
    Session.objects.select_for_update().get(pk=booking.session_id)
    Customer.objects.select_for_update(no_key=True).get(pk=booking.customer_id)
    lock_customer(booking.customer_id)
    reviewed = review(
        actor=actor,
        booking_id=booking_id,
        data=data,
        selection=selection,
        method_id=method_id,
    )
    if reviewed["fingerprint"] != reviewed_hash:
        raise ValidationError(
            "The membership, visit or payments changed. Review the current combined total."
        )
    if amount(reviewed["facts"]["received_today"]) > ZERO and verified_received is not True:
        raise ValidationError(
            "Confirm that the combined cash or check payment was actually received."
        )
    member = purchase(
        actor=actor,
        request_key=uuid.uuid5(key, "membership"),
        reviewed=reviewed["offer"]["fingerprint"],
        accepted=True,
        method_id=method_id,
        verified_received=verified_received,
        send_confirmation=send_confirmation,
        combined_booking=booking,
        customer=booking.customer,
        expected_method=data["method"],
        **selection,
    )
    final_data = data | {"apply_available_benefits": True}
    real = checkout.preview(actor=actor, booking_id=booking_id, kind="arrival", data=final_data)
    if normalized(real[4], member.pk) != reviewed["facts"]["arrival"]:
        raise ValidationError(
            "The available membership benefits changed. Review the combined price again."
        )
    arrival = checkout.confirm(
        actor=actor,
        booking_id=booking_id,
        kind="arrival",
        data=final_data,
        request_key=key,
        reviewed_hash=real[-1],
        confirmed=True,
    )
    record = MembershipArrivalCheckout.objects.create(
        id=key,
        purchase=member,
        checkout=arrival,
        fingerprint=reviewed_hash,
        facts=reviewed["facts"],
        actor=actor,
    )
    queue_confirmation(record)
    return record


def queue_confirmation(record):
    """One combined immutable message; normal membership-only hooks are suppressed."""
    from .communications.content import session_subject
    from .communications.services import enqueue
    from .date_display import display_date, display_time_range
    from .payments.invoices import received

    member, arrival = record.purchase, record.checkout
    customer, root, booking = member.customer, member.membership, arrival.booking
    if not member.send_confirmation or not customer.email:
        return
    member_paid = sum(
        (received(i.invoice.sale) for i in member.installments.filter(invoice__isnull=False)), ZERO
    )
    quote = arrival.details["quote"]
    content = [
        f"Dear Family {customer.last_name},",
        "",
        "You're all set for more Monkey Do adventures!",
        "",
        "Your visit",
        f"{display_date(booking.session.starts_at, 'l, F j, Y')} at {display_time_range(booking.session.starts_at, booking.session.ends_at)}.",
        f"{booking.adults} adults · {booking.children} children · {booking.babies} babies",
        "",
        "Your Membership",
        f"You've purchased {root.places} {root.get_kind_display()} Membership"
        + ("s." if root.places != 1 else "."),
        f"Begins: {display_date(root.starts_on, 'l, F j, Y')}",
        f"Continues through: {display_date(root.ends_on, 'F j, Y')}",
        "Enjoy two free play sessions per membership each month, then just $5.99 for each additional play session that month. Your membership also includes two free adults for every visit, 25% off supervised play, and 15% off parties."
        if root.kind == "subscription"
        else "Enjoy one free visit per membership each day, with two free adults, plus 15% off parties. Unlimited Membership benefits exclude supervised play and Chol Hamoed. You may book those visits at full price.",
    ]
    used = [
        u
        for u in quote.get("membership_plan", {}).get("uses", [])
        if u["membership_id"] == member.pk
    ]
    if used:
        free = sum(u["kind"] in {"subscription_free", "unlimited_daily"} for u in used)
        content += [
            f"Today's visit uses {free} free membership visit(s)."
            if free
            else "Today's visit uses the membership prices shown below."
        ]
    content += ["", "Here's your payment details for the membership and visit:"]
    first = member.installments.first()
    combined_total = (amount(first.quote["total"]) if first else ZERO) + amount(quote["total"])
    content += [
        f"Membership{'—first month' if root.billing == 'monthly' else '—full selected term'}: ${first.quote['total']}"
        if first
        else "Complimentary membership: $0.00",
        *[f"{row['label']}: ${row['amount']}" for row in quote["lines"]],
        f"Credit-card processing fee: ${quote['processing_fee']}",
        f"Sales tax: ${quote['sales_tax']}",
        f"Visit total: ${quote['total']}",
        f"Membership and visit total: ${combined_total:.2f}",
        f"Membership payment received: ${member_paid:.2f}",
        f"Visit payment received today: ${record.facts['visit_due']}",
        f"New payment received: ${record.facts['received_today']}",
    ]
    from .customer_credit import applied

    credited = applied(first.invoice.sale) if first else ZERO
    if credited:
        content += [f"Existing customer credit applied to membership: ${credited:.2f}"]
    prepaid = sum((amount(p["amount"]) for p in arrival.details["plan"] if p["advance"]), ZERO)
    if prepaid:
        content += [f"Previously received Zelle applied to visit: ${prepaid:.2f}"]
    next_item = member.installments.filter(number__gt=1).first()
    if next_item:
        content += [
            f"Your next scheduled membership payment is ${next_item.quote['total']} on {display_date(next_item.due_on, 'F j, Y')}."
        ]
    content += [
        "The purchased term ends without automatic renewal.",
        "",
        "Swing your way over to:",
        "56 Budleman Way, Lakewood, NJ 08701",
        "Please use the basement entrance. Parking is in the driveway or cul-de-sac.",
        "",
        "After the initial 3 months, membership can be renewed each month, consecutively, without a new 3 month minimum. Renew within one week of expiry to retain this option.",
        "In the event that you must cancel, please call or text us at 848-238-5147. Cancellation fees will apply.",
        "",
        "Get ready to go bananas,",
        "The Monkey Do team",
    ]
    return enqueue(
        key=f"membership-arrival:{record.pk}",
        kind="membership_visit_confirmation",
        recipient=customer.email,
        subject=session_subject(booking, "Your Monkey Do membership and visit are ready!"),
        text="\n".join(content),
        customer=customer,
        booking=booking,
        membership=member,
        actor=record.actor,
    )
