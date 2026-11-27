"""Reconcile a paid visit with a same-day purchased membership.

The combined new-purchase checkout will call these boundaries too. This service
only transfers verified existing funds; it never sends a charge or refund.
"""

import uuid

from django.core.exceptions import ValidationError
from django.db import transaction

from .availability import NEW_YORK
from .customer_credit_records import CustomerCreditIssue, VisitMembershipConversion
from .membership_booking import lines_for
from .membership_payments import member_record
from .membership_reservations import finish, lock_customer, payment_current, reserve
from .membership_sales import authorize, today
from .models import AuditEvent, Booking, BookingQuote, FinancialLineAdjustment
from .payments.amounts import COMPONENTS, ZERO, allocate, amount
from .payments.invoices import effective_components, settled, total
from .payments.ledger import (
    CATEGORIES,
    RESERVED,
    fingerprint,
    lock_request,
    lock_sale,
    used_components,
    writes_allowed,
)
from .pricing import Line, quote_lines

CHILD = {
    "open_child",
    "supervised_child",
    "member_unlimited_visit",
    "member_subscription_free",
    "member_subscription_additional",
    "member_subscription_supervised",
}


def group(category):
    return (
        "children"
        if category in CHILD
        else "adults"
        if category == "additional_adult"
        else category
    )


def review(*, actor, booking_id, member_id):
    authorize(actor, collect=True)
    from .permissions import require_actor

    require_actor(actor, "core.change_booking")
    member = member_record(member_id)
    booking = Booking.objects.select_related("session", "customer").get(pk=booking_id)
    on = booking.session.starts_at.astimezone(NEW_YORK).date()
    if (
        booking.customer_id != member.customer_id
        or booking.workflow != "integrated_v1"
        or booking.attendance != "arrived"
        or on != today()
        or member.accepted_at.astimezone(NEW_YORK).date() != on
        or member.purpose == "complimentary"
        or not payment_current(member)
    ):
        raise ValidationError(
            "Use today's arrived visit and a paid membership purchased today for the same customer."
        )
    if VisitMembershipConversion.objects.filter(booking=booking).exists():
        raise ValidationError(
            "This visit already has a membership conversion. Open its saved credit history."
        )
    checkout = booking.checkouts.select_related("sale").order_by("-created_at").first()
    if not checkout or checkout.kind != "arrival" or checkout.sale is None:
        raise ValidationError(
            "This visit has no paid admission invoice to convert. Unpaid visits create no credit."
        )
    sale = checkout.sale
    if sale.credit_applications.exists():
        raise ValidationError(
            "This visit already uses customer credit. Review returning that credit before converting it again; no new credit was issued."
        )
    operations = list(sale.operations.order_by("requested_at", "pk"))
    if any(
        op.kind != "receipt" or op.state in {"ready", "sending", "unknown", "action"}
        for op in operations
    ):
        raise ValidationError(
            "Reconcile existing payment or correction outcomes before converting this visit."
        )
    from .membership_cancellations import unrecorded_provider_return

    if any(unrecorded_provider_return(op) for op in operations if op.state == "succeeded"):
        raise ValidationError("A provider return still needs recording before conversion.")
    if settled(sale) != total(sale):
        raise ValidationError(
            "Use the fully paid visit balance. Unpaid amounts cannot become customer credit."
        )
    original = booking.quotes.select_related("policy").first()
    policy = sale.quote.policy
    values = {
        name: getattr(booking, name)
        for name in ("children", "adults", "babies", "socks", "supervised")
    }
    state = getattr(booking, "charge_state", None)
    if state and (state.comped or state.special_subtotal is not None):
        raise ValidationError(
            "This owner-priced visit needs an explicit owner conversion review; its price was not changed."
        )
    lines, meta = lines_for(
        policy,
        customer_id=booking.customer_id,
        session=booking.session,
        values=values,
        booking=booking,
        apply_available=True,
    )
    if not any(use["membership_id"] == member.pk for use in meta["membership_plan"]["uses"]):
        raise ValidationError("This membership does not replace any admission in today's visit.")
    financial_lines = list(sale.lines.all())
    current = effective_components(sale)
    before, after = {}, {}
    for line in financial_lines:
        key = group(line.category)
        before[key] = before.get(key, ZERO) + current[str(line.pk)]["net"]
        if line.category == "partial_cancellation":
            lines.append(Line(line.description, line.quantity, line.unit_price, line.taxable))
    for line in lines:
        if line.label not in CATEGORIES:
            raise ValidationError("This admission category requires owner reconciliation.")
        key = group(CATEGORIES[line.label])
        after[key] = after.get(key, ZERO) + line.quantity * line.unit_price
    reversals, converted_fee_base = [], ZERO
    for key in sorted(set(before) | set(after)):
        reduction = before.get(key, ZERO) - after.get(key, ZERO)
        if reduction < ZERO or (reduction and key not in {"children", "adults"}):
            raise ValidationError(
                "Only replaced admissions can fund this conversion; review other price changes separately."
            )
        originals = [line for line in financial_lines if group(line.category) == key]
        parts = (
            allocate(reduction, [current[str(line.pk)]["net"] for line in originals])
            if reduction
            else [ZERO] * len(originals)
        )
        for line, net in zip(originals, parts):
            if not net:
                continue
            values = current[str(line.pk)]
            if line.taxable:
                converted_fee_base += allocate(values["fee"], [net, values["net"] - net])[0]
            reversed_tax = {
                component: allocate(values[component], [net, values["net"] - net])[0]
                for component in ("item_tax", "fee_tax")
            }
            reversals.append(
                dict(
                    line=str(line.pk),
                    net=str(net),
                    fee="0.00",
                    **{key: str(value) for key, value in reversed_tax.items()},
                )
            )
    credit_amount = sum((amount(row[key]) for row in reversals for key in COMPONENTS), ZERO)
    if not credit_amount:
        raise ValidationError("No paid admission is replaced by this conversion.")
    paid_operations = [op for op in operations if op.state == "succeeded"]
    source_parts = [[] for op in paid_operations]
    for row in reversals:
        line = row["line"]
        available = []
        for op in paid_operations:
            consumed = used_components(op.adjustments.filter(state__in=RESERVED))
            original_parts = next((part for part in op.allocation if part["line"] == line), {})
            available.append(
                {
                    key: max(
                        ZERO,
                        amount(original_parts.get(key, ZERO))
                        - consumed.get(line, {}).get(key, ZERO),
                    )
                    for key in COMPONENTS
                }
            )
        distributed = []
        for component in COMPONENTS:
            weights = [part[component] for part in available]
            if amount(row[component]) > sum(weights, ZERO):
                raise ValidationError(
                    "The replaced amount is not backed by available recorded payments."
                )
            distributed.append(allocate(amount(row[component]), weights))
        for index in range(len(paid_operations)):
            parts = {
                key: str(distributed[position][index]) for position, key in enumerate(COMPONENTS)
            }
            if any(amount(value) for value in parts.values()):
                source_parts[index].append(dict(line=line, **parts))
    sources = []
    for op, parts in zip(paid_operations, source_parts):
        value = sum((amount(row[key]) for row in parts for key in COMPONENTS), ZERO)
        if value:
            sources.append(dict(original=str(op.pk), amount=str(value), allocation=parts))
    quote = quote_lines(lines, policy, card_base=ZERO)
    retained_fee = sum((values["fee"] for values in current.values()), ZERO)
    remaining_tax = sum(
        (values["item_tax"] + values["fee_tax"] for values in current.values()), ZERO
    ) - sum((amount(row["item_tax"]) + amount(row["fee_tax"]) for row in reversals), ZERO)
    quote.update(meta)
    quote.update(
        processing_fee=str(retained_fee),
        sales_tax=str(remaining_tax),
        total=str(amount(quote["subtotal"]) + retained_fee + remaining_tax),
        expected_method=original.snapshot.get("expected_method", booking.expected_method),
        membership_options=dict(allow_new_unlimited=True),
        membership_conversion=True,
        original_processing_fee_retained=str(retained_fee),
        taxable_processing_fee=str(
            sum((current[str(line.pk)]["fee"] for line in financial_lines if line.taxable), ZERO)
            - converted_fee_base
        ),
    )
    data = dict(
        booking=booking.pk,
        version=booking.edit_version,
        original_quote=original.pk,
        member=member.pk,
        billing_revision=member.billing_state.revision,
        sale=str(sale.pk),
        on=on.isoformat(),
        credit=str(credit_amount),
        original_total=str(total(sale)),
        original_received=str(
            sum((op.amount for op in operations if op.state == "succeeded"), ZERO)
        ),
        retained_fee=str(retained_fee),
        reversals=reversals,
        sources=sources,
        quote=quote,
        operations=[
            dict(id=str(op.pk), state=op.state, allocation=op.allocation) for op in operations
        ],
    )
    return data | dict(fingerprint=fingerprint(data))


@transaction.atomic
def convert(*, actor, booking_id, member_id, reviewed, request_key, confirmed=False):
    authorize(actor, collect=True)
    writes_allowed()
    key = lock_request(request_key)
    prior = VisitMembershipConversion.objects.filter(pk=key).first()
    identity = fingerprint(dict(booking=booking_id, member=member_id, reviewed=reviewed))
    if prior:
        if prior.actor_id != actor.pk or prior.fingerprint != identity:
            raise ValidationError("This conversion key already identifies a different action.")
        return prior
    if confirmed is not True:
        raise ValidationError(
            "Confirm the reviewed visit conversion and transfer to customer credit."
        )
    booking = Booking.objects.select_for_update().get(pk=booking_id)
    lock_customer(booking.customer_id)
    data = review(actor=actor, booking_id=booking.pk, member_id=member_id)
    lock_sale(data["sale"])
    if data["fingerprint"] != reviewed:
        raise ValidationError("The visit, membership or funds changed. Review conversion again.")
    original = booking.quotes.get(pk=data["original_quote"])
    updated = BookingQuote.objects.create(
        booking=booking,
        policy=original.policy,
        revision=original.revision + 1,
        snapshot=data["quote"],
        actor=actor,
    )
    conversion = VisitMembershipConversion.objects.create(
        id=key,
        booking=booking,
        purchase_id=member_id,
        original_quote=original,
        updated_quote=updated,
        fingerprint=identity,
        details=data,
        actor=actor,
    )
    for row in data["reversals"]:
        FinancialLineAdjustment.objects.create(
            request_key=key,
            line_id=row["line"],
            reason="membership_conversion",
            actor=actor,
            **{component: -amount(row[component]) for component in COMPONENTS},
        )
    for source in data["sources"]:
        CustomerCreditIssue.objects.create(
            id=uuid.uuid5(key, source["original"]),
            conversion=conversion,
            customer_id=booking.customer_id,
            original_id=source["original"],
            amount=source["amount"],
            allocation=source["allocation"],
        )
    reserve(
        actor=actor,
        booking_id=booking.pk,
        quote_id=updated.pk,
        request_key=uuid.uuid5(key, "reserve"),
        for_arrival=True,
    )
    finish(
        actor=actor,
        booking_id=booking.pk,
        request_key=uuid.uuid5(key, "use"),
        action="used",
        reason="arrival",
    )
    AuditEvent.objects.create(
        actor=actor,
        action="membership.visit_converted",
        record_type="booking",
        record_id=str(booking.pk),
        changes=dict(
            conversion=str(key),
            membership=member_id,
            credit=data["credit"],
            fee_retained=data["retained_fee"],
        ),
    )
    return conversion
