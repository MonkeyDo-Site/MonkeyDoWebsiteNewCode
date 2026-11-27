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


def review(
    *,
    actor,
    booking_id,
    data,
    selection,
    method_id=None,
    validate_waivers=True,
    card_authorization_id=None,
):
    from .membership_arrival_pending import session_facts, waivers

    authorize(actor, collect=True)
    booking = Booking.objects.select_related("customer", "session").get(pk=booking_id)
    checkout.require_current(booking, "arrival")
    if booking.session.starts_at.astimezone(NEW_YORK).date() != today():
        raise ValidationError("Combine a membership purchase with arrival on the visit date.")
    tender = data.get("method")
    if tender not in {"cash", "check", "card"}:
        raise ValidationError(
            "Choose cash, check or card for this combined payment, or clear the membership purchase to use another arrival payment."
        )
    # These values are derived from this booking, never supplied by the browser.
    values = selection | {"customer": booking.customer, "expected_method": tender}
    proposed = offer(actor=actor, **values)
    membership_due = (
        amount(proposed.get("first_payment_total", proposed["installments"][0]["quote"]["total"]))
        if proposed["installments"]
        else ZERO
    )
    result = checkout.preview(
        actor=actor,
        booking_id=booking_id,
        kind="arrival",
        data=data | {"apply_available_benefits": True},
        validate_waivers=validate_waivers,
        proposed_membership=ProposedMembership(proposed),
    )
    visit_due = sum((amount(p["amount"]) for p in result[3] if not p.get("advance")), ZERO)
    from .models import PaymentMethod

    selected = (
        PaymentMethod.objects.filter(pk=method_id, customer=booking.customer).first()
        if method_id
        else None
    )
    facts = {
        "booking": booking.pk,
        "actor": actor.pk,
        "offer": proposed["fingerprint"],
        "method_id": str(method_id) if method_id else None,
        "arrival": normalized(result[4]),
        "membership_due": str(membership_due),
        "visit_due": str(visit_due),
        "received_today": str(membership_due + visit_due),
        "session": session_facts(booking),
        "waiver_evidence": waivers(booking),
        "membership_card_last_four": selected.last_four if selected else "",
        "visit_card_last_four": booking.card_agreement.method.last_four
        if tender == "card" and visit_due
        else "",
    }
    if tender == "card":
        facts.update(payment_due_today=str(membership_due + visit_due), received_today="0.00")
    if card_authorization_id:
        facts["card_authorization_id"] = str(card_authorization_id)
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
    card_authorization_id=None,
):
    authorize(actor, collect=True)
    checkout.authorize(actor)
    if confirmed is not True or accepted is not True:
        raise ValidationError("Accept the membership terms and confirm the combined arrival.")
    key = lock_request(request_key)
    from .membership_arrival_pending import MembershipArrivalIntent
    from .membership_arrival_pending import create as create_pending

    pending = MembershipArrivalIntent.objects.filter(pk=key).first()
    if pending:
        if (
            pending.actor_id != actor.pk
            or pending.booking_id != booking_id
            or pending.fingerprint != reviewed_hash
        ):
            raise ValidationError(
                "This confirmation already identifies another membership arrival."
            )
        return pending
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
        card_authorization_id=card_authorization_id,
    )
    if reviewed["fingerprint"] != reviewed_hash:
        raise ValidationError(
            "The membership, visit or payments changed. Review the current combined total."
        )
    if (
        data["method"] != "card"
        and amount(reviewed["facts"]["received_today"]) > ZERO
        and verified_received is not True
    ):
        raise ValidationError(
            "Confirm that the combined cash or check payment was actually received."
        )
    member = purchase(
        actor=actor,
        request_key=uuid.uuid5(key, "membership"),
        reviewed=reviewed["offer"]["fingerprint"],
        accepted=True,
        method_id=method_id,
        card_authorization_id=card_authorization_id,
        verified_received=verified_received,
        send_confirmation=send_confirmation,
        combined_booking=booking,
        customer=booking.customer,
        expected_method=data["method"],
        **selection,
    )
    if data["method"] == "card" and amount(reviewed["facts"]["membership_due"]):
        return create_pending(
            actor=actor, key=key, booking=booking, member=member, data=data, reviewed=reviewed
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


def membership_funded(record):
    from .membership_funding import member_needs_review
    from .membership_sales import installment_paid

    member = record.purchase
    if member_needs_review(member):
        return False
    stopped = member.billing_state.stopped_on
    on = record.checkout.booking.session.starts_at.astimezone(NEW_YORK).date()
    if stopped and stopped <= on:
        return False
    first = member.installments.first()
    return member.purpose == "complimentary" or (first is not None and installment_paid(first))


def ready_for_confirmation(record):
    from .membership_funding import sale_needs_review
    from .membership_sales import membership_status
    from .payments.invoices import settled, total

    if not membership_funded(record) or record.checkout.booking.attendance != "arrived":
        return False
    if membership_status(record.purchase) not in {"active", "scheduled"}:
        return False
    arrival = record.checkout
    if arrival.sale_id:
        if (
            sale_needs_review(arrival.sale)
            or settled(arrival.sale) < total(arrival.sale)
            or arrival.sale.operations.exclude(kind="receipt").filter(state="succeeded").exists()
            or arrival.sale.operations.filter(
                state__in=["ready", "sending", "unknown", "action"]
            ).exists()
        ):
            return False
    return True


def for_sale(sale_id):
    from .membership_schema import available

    if not available("core_membershiparrivalcheckout"):
        return None
    return (
        MembershipArrivalCheckout.objects.select_related(
            "purchase__membership",
            "purchase__customer",
            "purchase__billing_state",
            "checkout__booking__session",
            "checkout__sale",
        )
        .filter(checkout__sale_id=sale_id)
        .first()
    )


def lock_payment(operation):
    """Keep known funding corrections ordered with this dependent visit charge."""
    if operation.kind != "receipt" or operation.sale.kind != "visit":
        return None
    record = for_sale(operation.sale_id)
    if record:
        Booking.objects.select_for_update().get(pk=record.checkout.booking_id)
        lock_customer(operation.sale.customer_id)
        record = for_sale(operation.sale_id)
    return record


def payment_updated(operation):
    record = for_sale(operation.sale_id)
    if record:
        queue_confirmation(record)


def receipt_summary(record):
    from .customer_credit import applied
    from .payments.invoices import received

    first = record.purchase.installments.first()
    member_paid = received(first.invoice.sale) if first else ZERO
    prepaid = sum(
        (amount(p["amount"]) for p in record.checkout.details["plan"] if p["advance"]), ZERO
    )
    visit_paid = (
        max(ZERO, received(record.checkout.sale) - prepaid) if record.checkout.sale_id else ZERO
    )
    return {
        "membership_received": member_paid,
        "visit_received": visit_paid,
        "new_received": member_paid + visit_paid,
        "credit_applied": applied(first.invoice.sale) if first else ZERO,
    }


def confirmation_payload(record):
    """Pure current content; queued snapshots can be superseded before any send."""
    from .communications.content import session_subject
    from .date_display import display_date, display_time_range
    from .payments.invoices import received

    member, arrival = record.purchase, record.checkout
    customer, root, booking = member.customer, member.membership, arrival.booking
    first = member.installments.first()
    member_paid = received(first.invoice.sale) if first else ZERO
    prepaid = sum((amount(p["amount"]) for p in arrival.details["plan"] if p["advance"]), ZERO)
    visit_paid = max(ZERO, received(arrival.sale) - prepaid) if arrival.sale_id else ZERO
    quote = dict(arrival.details["quote"])
    if arrival.sale_id:
        from .payments.presentation import invoice_breakdown

        quote.update(invoice_breakdown(arrival.sale))
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
            f"Today's visit uses {free} free membership visit{'s' if free != 1 else ''}."
            if free
            else "Today's visit uses the membership prices shown below."
        ]
    content += ["", "Here's your payment details for the membership and visit:"]
    from .payments.presentation import invoice_breakdown

    member_quote = (
        invoice_breakdown(first.invoice.sale)
        if first
        else {"total": "0.00", "subtotal": "0.00", "processing_fee": "0.00", "sales_tax": "0.00"}
    )
    combined_total = amount(member_quote["total"]) + amount(quote["total"])
    combined_fee = amount(member_quote["processing_fee"]) + amount(quote["processing_fee"])
    combined_tax = amount(member_quote["sales_tax"]) + amount(quote["sales_tax"])
    content += [
        f"Membership{'—first month' if root.billing == 'monthly' else '—full selected term'}: ${member_quote['subtotal']}"
        if first
        else "Complimentary membership: $0.00",
        *[f"{row['label']}: ${row['amount']}" for row in quote["lines"]],
        f"Credit-card processing fee: ${combined_fee:.2f}",
        f"Sales tax: ${combined_tax:.2f}",
        f"Visit total: ${quote['total']}",
        f"Membership and visit total: ${combined_total:.2f}",
        f"Membership payment received: ${member_paid:.2f}",
        f"Visit payment received: ${visit_paid:.2f}",
        f"New payment received: ${member_paid + visit_paid:.2f}",
    ]
    from .customer_credit import applied

    credited = applied(first.invoice.sale) if first else ZERO
    if credited:
        content += [f"Existing customer credit applied to membership: ${credited:.2f}"]
    if prepaid:
        content += [f"Previously received Zelle applied to visit: ${prepaid:.2f}"]
    from .membership_sales import installment_paid

    next_item = next(
        (
            item
            for item in member.installments.filter(number__gt=1).select_related("invoice__sale")
            if not installment_paid(item)
        ),
        None,
    )
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
    return {
        "recipient": customer.email,
        "subject": session_subject(booking, "Your Monkey Do membership and visit are ready!"),
        "text": "\n".join(content),
    }


@transaction.atomic
def queue_confirmation(record):
    """Refresh unsent content; an attempted/unknown message is never repeated."""
    from .communications.models import MessageDelivery, MessageEvent
    from .communications.services import enqueue

    lock_customer(record.purchase.customer_id)
    record = MembershipArrivalCheckout.objects.select_related(
        "purchase__membership",
        "purchase__customer",
        "purchase__billing_state",
        "checkout__booking__session",
        "checkout__sale",
    ).get(pk=record.pk)
    messages = MessageDelivery.objects.filter(
        kind="membership_visit_confirmation",
        membership=record.purchase,
        booking_id=record.checkout.booking_id,
    ).order_by("created_at", "pk")
    attempted = messages.exclude(state__in=["queued", "cancelled"]).first()
    if attempted:
        return attempted
    current = messages.filter(state="queued").last() or messages.last()
    if current and current.state == "cancelled":
        return current
    if (
        not record.purchase.send_confirmation
        or not record.purchase.customer.email
        or not ready_for_confirmation(record)
    ):
        if current:
            current.state, current.code = "cancelled", "combined_payment_changed"
            current.save(update_fields=["state", "code"])
            MessageEvent.objects.create(delivery=current, state="cancelled", code=current.code)
        return None
    payload = confirmation_payload(record)
    if current and (current.recipient, current.subject, current.text_body) == (
        payload["recipient"],
        payload["subject"],
        payload["text"],
    ):
        return current
    key = f"membership-arrival:{record.pk}"
    if current:
        current.state, current.code = "cancelled", "combined_confirmation_changed"
        current.save(update_fields=["state", "code"])
        MessageEvent.objects.create(delivery=current, state="cancelled", code=current.code)
        key += ":" + str(current.pk) + ":" + fingerprint(payload)[:32]
    return enqueue(
        key=key,
        kind="membership_visit_confirmation",
        **payload,
        customer=record.purchase.customer,
        booking=record.checkout.booking,
        membership=record.purchase,
        actor=record.actor,
    )
