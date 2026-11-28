"""One staff confirmation buys a membership using today's actually paid admissions."""

import copy
import uuid

from django.core.exceptions import ValidationError
from django.db import transaction

from .membership_arrival import PROPOSED_ID, ProposedMembership
from .payments.amounts import COMPONENTS, ZERO, amount
from .payments.ledger import fingerprint, lock_sale

MARKER = "paid_visit_purchase"
CARD_MARKER = "paid_visit_card"


def prepare_offer(
    *,
    actor,
    booking_id,
    data,
    credit_amount,
    split=None,
    split_sender="",
    split_received_on=None,
    policy=None,
):
    from .membership_conversion import review
    from .models import Booking

    if (
        type(booking_id) is not int
        or booking_id <= 0
        or not Booking.objects.filter(pk=booking_id, customer_id=data["customer_id"]).exists()
    ):
        raise ValidationError("Choose this customer's paid visit for the conversion.")

    if (
        data["operation"] != "purchase"
        or data["comped"]
        or amount(credit_amount)
        or data["expected_method"] not in {"cash", "check", "split", "card"}
    ):
        raise ValidationError(
            "Choose a card, cash/check or received split payment for this paid-visit conversion."
        )
    proposed = ProposedMembership(data)
    converted = review(actor=actor, booking_id=booking_id, proposed_membership=proposed)
    if converted["on"] != data["starts_on"]:
        raise ValidationError(
            "This membership must start on today's visit date to replace admissions."
        )
    principal = amount(data["installments"][0]["quote"]["subtotal"])
    applied = min(principal, amount(converted["credit"]))
    remaining = principal - applied
    if data["expected_method"] == "card":
        from .pricing import Line, quote_lines

        quote = quote_lines(
            [
                Line(
                    f"{data['kind'].title()} Membership",
                    data["places"],
                    amount(data["unit_price"])
                    * (data["months"] if data["billing"] == "prepaid" else 1),
                    False,
                )
            ],
            policy,
            card_base=remaining,
        )
        data["installments"][0]["quote"] = quote
        remaining = amount(quote["total"]) - applied
    if data["expected_method"] == "split":
        from .membership_first_split import review as split_review
        from .pricing import Line, quote_lines

        plan = split_review(
            principal=principal,
            credit=applied,
            split=split or {},
            policy=policy,
            sender_name=split_sender,
            received_on=split_received_on,
        )
        # No card remainder is authorized in this flow yet. Show the actual
        # uncovered principal, without inventing a card receipt or its fee.
        plan.update(
            version="paid-visit-received-split-v1",
            parts=[part for part in plan["parts"] if part["tender"] != "card"],
            unallocated=plan["card_net"],
            card_net="0.00",
            card_total="0.00",
        )
        quote = quote_lines(
            [
                Line(
                    f"{data['kind'].title()} Membership",
                    data["places"],
                    amount(data["unit_price"])
                    * (data["months"] if data["billing"] == "prepaid" else 1),
                    False,
                )
            ],
            policy,
            card_base=ZERO,
        )
        quote["initial_split"] = plan
        data["installments"][0]["quote"] = quote
        data["first_payment_plan"] = plan
        remaining = amount(quote["total"]) - applied
    terms = data["terms"]
    pending_card = data["expected_method"] == "card" and bool(remaining)
    use_words = "will be applied after card confirmation" if pending_card else "is applied"
    credit_words = "will remain after transfer" if pending_card else "remains"
    terms += (
        f" Today's paid admissions and associated reversed tax supply ${converted['credit']} in existing funds."
        f" ${applied:.2f} {use_words} to this membership; ${amount(converted['credit']) - applied:.2f} {credit_words} as customer credit."
        f" The original processing fee of ${converted['retained_fee']} remains on the visit."
        " These are existing funds, not another receipt or a separate cash/card refund."
    )
    if data["expected_method"] == "card" and remaining:
        terms += (
            " The paid visit funds are reserved, not yet transferred. They are applied only after this separate card remainder is confirmed."
            " Until then the original paid visit stays unchanged and no membership benefit is used for it."
        )
    return data | dict(
        terms=terms,
        first_payment_total=str(remaining),
        paid_visit=dict(
            booking=booking_id,
            conversion=converted,
            applied=str(applied),
            remaining_credit=str(amount(converted["credit"]) - applied),
            new_payment=str(remaining),
        ),
    )


def require_known_split(data):
    """An incomplete preview is useful, but cannot consume funds or benefits."""
    if amount(data["first_payment_plan"].get("unallocated", ZERO)) or amount(
        data["first_payment_plan"]["card_total"]
    ):
        raise ValidationError(
            "Cover the remaining membership amount with received cash, check, verified Zelle or a verified physical gift card before confirming. No purchase or conversion was recorded."
        )


def complete_purchase(*, actor, member, offer, invoice, paid_intent=None):
    """Purchase holds the booking/customer locks; all writes share its transaction."""
    from .customer_credit_records import CustomerCreditAllocation, CustomerCreditApplication
    from .membership_conversion import record_funds, review, use_benefits
    from .membership_paid_visit_pending import release_completed
    from .membership_sales import installment_paid
    from .models import AuditEvent, Booking
    from .payments.ledger import record_manual, request_operation

    plan = offer["paid_visit"]
    booking = Booking.objects.select_related("session", "customer").get(pk=plan["booking"])
    lock_sale(plan["conversion"]["sale"])
    current = review(
        actor=actor,
        booking_id=booking.pk,
        proposed_membership=ProposedMembership(offer, recorded_purchase_id=member.pk),
        paid_intent=paid_intent,
    )
    if current["fingerprint"] != plan["conversion"]["fingerprint"]:
        raise ValidationError("The paid visit or its funds changed. Review the membership again.")
    details = copy.deepcopy(current)
    details["member"] = member.pk
    details["billing_revision"] = member.billing_state.revision
    for use in details["quote"]["membership_plan"]["uses"]:
        if use["membership_id"] == PROPOSED_ID:
            use["membership_id"] = member.pk
    details[MARKER] = dict(
        offer=member.fingerprint,
        request_key=str(member.request_key),
        applied=plan["applied"],
        new_payment=plan["new_payment"],
    )
    if paid_intent:
        from .membership_paid_visit_manual import plan as manual_plan
        from .membership_paid_visit_split import plan as split_plan

        manual = manual_plan(paid_intent)
        if manual:
            details[MARKER].update(
                original_new_payment=plan["new_payment"],
                new_payment=manual.facts["net"],
                unused_card_fee_removed=manual.facts["fee_removed"],
                payment_change=str(manual.pk),
            )
        split = split_plan(paid_intent)
        if split:
            details[MARKER].update(
                original_new_payment=plan["new_payment"],
                new_payment=split.facts["new_payment"],
                unused_card_fee_removed=split.facts["fee_removed"],
                payment_change=str(split.pk),
                payment_change_kind="split",
            )
    key = uuid.uuid5(member.request_key, "paid-visit-conversion")
    converted = record_funds(
        actor=actor,
        booking=booking,
        member_id=member.pk,
        data=details,
        key=key,
        identity=fingerprint(
            dict(purchase=member.pk, offer=member.fingerprint, visit=current["fingerprint"])
        ),
        before_funds=(lambda converted: release_completed(paid_intent, converted))
        if paid_intent
        else None,
    )
    applied = amount(plan["applied"])
    line = invoice.sale.lines.get()
    if applied:
        application = CustomerCreditApplication.objects.create(
            id=uuid.uuid5(member.request_key, "initial-customer-credit"),
            customer=member.customer,
            sale=invoice.sale,
            actor=actor,
            amount=applied,
            details=dict(conversion=str(converted.pk), **details[MARKER]),
            fingerprint=fingerprint(details[MARKER]),
        )
        left = applied
        for source in converted.credits.order_by("created_at", "pk"):
            taken = min(left, source.amount)
            if taken:
                CustomerCreditAllocation.objects.create(
                    application=application,
                    issue=source,
                    amount=taken,
                    allocation=[
                        dict(
                            line=str(line.pk),
                            net=str(taken),
                            fee="0.00",
                            item_tax="0.00",
                            fee_tax="0.00",
                        )
                    ],
                )
                left -= taken
        if left:
            raise ValidationError(
                "The converted visit cannot supply the accepted membership amount."
            )
        AuditEvent.objects.create(
            actor=actor,
            action="customer.credit_applied",
            record_type="membership",
            record_id=str(member.pk),
            changes=dict(
                application=str(application.pk), amount=str(applied), conversion=str(converted.pk)
            ),
        )
    remaining = amount(plan["new_payment"])
    if paid_intent:
        # This receipt is already known. Completion never makes another charge.
        pass
    elif offer.get("first_payment_plan"):
        from .membership_first_split import record

        require_known_split(offer)
        record(
            actor=actor,
            member=member,
            invoice=invoice,
            plan=offer["first_payment_plan"],
            method=None,
        )
    elif remaining:
        operation = request_operation(
            actor=actor,
            sale_id=invoice.sale_id,
            request_key=uuid.uuid5(member.request_key, "first-payment"),
            tender=member.membership.expected_method,
            allocation=[
                dict(
                    line=str(line.pk),
                    **{k: str(remaining if k == "net" else ZERO) for k in COMPONENTS},
                )
            ],
            purpose="member_purchase",
        )
        record_manual(actor=actor, operation_id=operation.pk, received=True)
    if not installment_paid(invoice.installment):
        raise ValidationError(
            "Complete the accepted membership funding before replacing visit benefits."
        )
    use_benefits(actor=actor, conversion=converted, key=key)
    queue_confirmation(member)
    return converted


def conversion_for(member):
    from .customer_credit_records import VisitMembershipConversion

    return (
        VisitMembershipConversion.objects.filter(
            purchase=member,
            details__paid_visit_purchase__offer=member.fingerprint,
        )
        .select_related(
            "purchase__membership",
            "purchase__customer",
            "purchase__billing_state",
            "booking__session",
            "updated_quote",
        )
        .first()
    )


def ready_for_confirmation(record):
    from .membership_funding import member_needs_review
    from .membership_sales import installment_paid

    member = record.purchase
    return (
        (member.membership.snapshot.get(MARKER) or member.membership.snapshot.get(CARD_MARKER))
        and member.send_confirmation
        and member.customer.email
        and not member.cancellations.exists()
        and not member_needs_review(member)
        and installment_paid(member.installments.first())
        and record.booking.attendance == "arrived"
        and record.booking.membership_benefits.filter(
            purchase=member, quote=record.updated_quote, current__status="used"
        ).exists()
    )


def confirmation_payload(record):
    from .communications.content import session_subject
    from .customer_credit import issue_balances
    from .date_display import display_date, display_time_range
    from .membership_sales import installment_paid
    from .payments.invoices import received, total

    member, booking = record.purchase, record.booking
    root, customer = member.membership, member.customer
    first = member.installments.first()
    source_credit = sum((i.remaining for i in issue_balances().filter(conversion=record)), ZERO)
    content = [
        f"Dear Family {customer.last_name},",
        "",
        "Today's visit has been applied toward your new membership.",
        f"Your visit: {display_date(booking.session.starts_at, 'l, F j, Y')} at {display_time_range(booking.session.starts_at, booking.session.ends_at)}.",
        f"{root.places} {root.get_kind_display()} Membership" + ("s" if root.places != 1 else ""),
        f"Begins: {display_date(root.starts_on, 'F j, Y')}",
        f"Continues through: {display_date(root.ends_on, 'F j, Y')}",
        "",
        f"Original visit payment received: ${amount(record.details['original_received']):.2f}",
        f"Original visit processing fee retained: ${amount(record.details['retained_fee']):.2f}",
        f"Paid visit funds applied to membership: ${amount(record.details[MARKER]['applied']):.2f}",
        f"New membership payment received: ${received(first.invoice.sale):.2f}",
        f"Membership{' first month' if root.billing == 'monthly' else ' full selected term'} total: ${total(first.invoice.sale):.2f}",
        f"Unused customer credit from this visit: ${source_credit:.2f}",
        "Converted funds are not a second payment or an additional cash/card refund.",
    ]
    used = record.booking.membership_benefits.filter(
        purchase=member, quote=record.updated_quote, current__status="used"
    )
    free = used.filter(kind__in=["subscription_free", "unlimited_daily"]).count()
    if free:
        content.append(
            f"Today's visit uses {free} free membership visit{'s' if free != 1 else ''}."
        )
    next_item = next(
        (
            i
            for i in member.installments.filter(number__gt=1).select_related("invoice__sale")
            if not installment_paid(i)
        ),
        None,
    )
    if next_item:
        content.append(
            f"Your next scheduled membership payment is ${next_item.quote['total']} on {display_date(next_item.due_on, 'F j, Y')}."
        )
    content += [
        "The purchased term ends without automatic renewal.",
        "",
        "Get ready to go bananas,",
        "The Monkey Do team",
    ]
    return dict(
        recipient=customer.email,
        subject=session_subject(booking, "Your Monkey Do membership and visit update"),
        text="\n".join(content),
    )


@transaction.atomic
def queue_confirmation(member):
    """Refresh only unattempted combined messages; never send from purchase itself."""
    from .communications.models import MessageDelivery, MessageEvent
    from .communications.services import enqueue
    from .membership_reservations import lock_customer

    lock_customer(member.customer_id)
    record = conversion_for(member)
    if record is None:
        return None  # Purchase funding is still inside its atomic confirmation.
    messages = MessageDelivery.objects.filter(
        kind="membership_visit_confirmation", membership=member, booking=record.booking
    ).order_by("created_at", "pk")
    attempted = messages.exclude(state__in=["queued", "cancelled"]).first()
    if attempted:
        return attempted
    current = messages.filter(state="queued").last() or messages.last()
    if current and current.state == "cancelled":
        return current
    if not ready_for_confirmation(record):
        if current:
            current.state, current.code = "cancelled", "paid_visit_purchase_changed"
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
    key = f"paid-visit-membership:{record.pk}"
    if current:
        current.state, current.code = "cancelled", "paid_visit_confirmation_changed"
        current.save(update_fields=["state", "code"])
        MessageEvent.objects.create(delivery=current, state="cancelled", code=current.code)
        key += ":" + str(current.pk) + ":" + fingerprint(payload)[:32]
    return enqueue(
        key=key,
        kind="membership_visit_confirmation",
        **payload,
        customer=record.purchase.customer,
        booking=record.booking,
        membership=record.purchase,
        actor=record.actor,
    )
