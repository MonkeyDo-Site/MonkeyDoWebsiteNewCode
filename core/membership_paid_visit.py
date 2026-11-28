"""One staff confirmation buys a membership using today's actually paid admissions."""

import copy
import uuid

from django.core.exceptions import ValidationError
from django.db import transaction

from .membership_arrival import PROPOSED_ID, ProposedMembership
from .payments.amounts import COMPONENTS, ZERO, amount
from .payments.ledger import fingerprint, lock_sale

MARKER = "paid_visit_purchase"


def prepare_offer(*, actor, booking_id, data, credit_amount):
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
        or data.get("first_payment_plan")
        or data["expected_method"] not in {"cash", "check"}
    ):
        raise ValidationError(
            "Use cash or check for the remaining payment in this combined paid-visit conversion. Other payment combinations are still in development."
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
    terms = data["terms"].replace(
        f"The first payment due today is ${data['installments'][0]['quote']['total']}, including",
        f"The new payment due today is ${remaining:.2f}, after applying ${applied:.2f} from this paid visit, including",
    )
    terms += (
        f" Today's paid admissions and associated reversed tax supply ${converted['credit']} in existing funds."
        f" ${applied:.2f} is applied to this membership; ${amount(converted['credit']) - applied:.2f} remains as customer credit."
        f" The original processing fee of ${converted['retained_fee']} remains on the visit."
        " These are existing funds, not another receipt or a separate cash/card refund."
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


def complete_purchase(*, actor, member, offer, invoice):
    """Purchase holds the booking/customer locks; all writes share its transaction."""
    from .customer_credit_records import CustomerCreditAllocation, CustomerCreditApplication
    from .membership_conversion import record_funds, review, use_benefits
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
    if remaining:
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
        member.membership.snapshot.get(MARKER)
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
