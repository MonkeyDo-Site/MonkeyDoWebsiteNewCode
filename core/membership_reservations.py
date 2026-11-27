"""Durable anonymous-place benefits. Caller locks its booking before customer lock.

Final mutations serialize on a customer advisory lock. Read-only estimates never
hold places. Accepted assignments and transition batches are append-only; the
small mutable state table is only the current projection of those facts.
"""

import uuid
from collections import Counter
from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction

from .availability import NEW_YORK
from .membership_benefits import BenefitRules, Place, plan_visit
from .membership_records import (
    MembershipBenefitAssignment,
    MembershipBenefitBatch,
    MembershipBenefitEvent,
    MembershipBenefitState,
    MembershipPurchase,
)
from .membership_sales import enabled, installment_paid, today
from .models import AuditEvent, Booking, BookingQuote, CalendarDate
from .payments.ledger import fingerprint, lock_request
from .permissions import require_actor
from .pricing import quote_lines


@transaction.atomic
def lock_customer(customer_id):
    if type(customer_id) is not int or customer_id <= 0:
        raise ValidationError("Use a current customer for membership benefits.")
    # A signed bigint key fits the existing customer BigAutoField. Namespace is
    # specific to membership benefit/billing mutations, not capacity locks.
    key = uuid.uuid5(uuid.NAMESPACE_URL, f"monkeydo:membership:{customer_id}")
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(%s,%s)",
                [73220, int.from_bytes(key.bytes[:4], signed=True)],
            )


def payment_current(member, *, on=None):
    on = on or today()
    if member.purpose == "complimentary":
        return True
    installments = list(member.installments.select_related("invoice__sale"))
    stop = member.billing_state.stopped_on
    return (
        bool(installments)
        and installment_paid(installments[0])
        and all(
            installment_paid(item)
            for item in installments
            if item.due_on <= on and (stop is None or item.cycle.starts_on < stop)
        )
    )


def accepted_rules(snapshot):
    values = dict(snapshot)
    for key in (
        "subscription_additional_price",
        "subscription_supervised_discount",
        "party_discount",
    ):
        values[key] = Decimal(values[key])
    try:
        return BenefitRules(**values)
    except (TypeError, ValueError):
        raise ValidationError("The accepted membership rules need owner review.") from None


def fresh_numbers(size, occupied, limit):
    """Bound materialization by attendee demand, not an arbitrarily large grant."""
    number, count = 1, 0
    while number <= size and count < limit:
        if number not in occupied:
            yield number
            count += 1
        number += 1


def places_for(
    customer_id,
    *,
    appointment_on,
    children,
    exclude_booking=None,
    supervised=False,
    unlimited_places=None,
):
    if type(appointment_on) is not date or type(children) is not int or not 0 <= children <= 32767:
        raise ValidationError("Use the appointment date and valid child count.")
    if not children:
        return []
    result = []
    members = (
        MembershipPurchase.objects.filter(
            customer_id=customer_id,
            membership__starts_on__lte=appointment_on,
            membership__ends_on__gte=appointment_on,
        )
        .select_related("membership", "billing_state")
        .order_by("membership__ends_on", "pk")
    )
    for member in members:
        root = member.membership
        if member.billing_state.stopped_on and member.billing_state.stopped_on <= appointment_on:
            continue
        cycle = root.cycles.filter(
            starts_on__lte=appointment_on, ends_on__gte=appointment_on
        ).first()
        if cycle is None or not payment_current(member):
            continue
        rules = accepted_rules(member.benefit_rules)
        states = MembershipBenefitState.objects.filter(
            status__in=["reserved", "used"],
            assignment__purchase=member,
        ).exclude(assignment__booking_id=exclude_booking)
        counts, occupied = Counter(), set()
        if root.kind == "unlimited":
            occupied = set(
                states.filter(
                    assignment__kind="unlimited_daily", assignment__appointment_on=appointment_on
                ).values_list("assignment__place", flat=True)
            )
            numbers = (
                fresh_numbers(root.places, occupied, children)
                if unlimited_places is None
                else sorted(
                    number
                    for membership_id, number in unlimited_places
                    if membership_id == member.pk
                    and 1 <= number <= root.places
                    and number not in occupied
                )
            )
        elif supervised:
            numbers = range(1, min(children, root.places) + 1)
        else:
            counts = Counter(
                states.filter(
                    assignment__kind="subscription_free", assignment__cycle=cycle
                ).values_list("assignment__place", flat=True)
            )
            numbers = sorted(set(counts) | set(fresh_numbers(root.places, counts, children)))
        for number in numbers:
            result.append(
                Place(
                    membership_id=member.pk,
                    number=number,
                    kind=root.kind,
                    starts_on=root.starts_on,
                    ends_on=root.ends_on,
                    cycle_starts_on=cycle.starts_on,
                    cycle_ends_on=cycle.ends_on,
                    payments_current=True,
                    free_visits_used=counts[number],
                    daily_used=number in occupied,
                    rules=rules,
                )
            )
    return result


def visit_plan(
    policy,
    *,
    customer_id,
    appointment_on,
    children,
    adults,
    babies=0,
    socks=0,
    supervised=False,
    exclude_booking=None,
    special_admissions=None,
    comped=False,
    unlimited_places=None,
):
    enabled()
    chol_hamoed = CalendarDate.objects.filter(day=appointment_on, chol_hamoed=True).exists()
    places = places_for(
        customer_id,
        appointment_on=appointment_on,
        children=children,
        exclude_booking=exclude_booking,
        supervised=supervised,
        unlimited_places=unlimited_places,
    )
    return plan_visit(
        policy,
        places,
        appointment_on=appointment_on,
        children=children,
        adults=adults,
        babies=babies,
        socks=socks,
        supervised=supervised,
        chol_hamoed=chol_hamoed,
        special_admissions=special_admissions,
        comped=comped,
    )


def quote_visit(policy, *, expected_method, **values):
    if expected_method not in {"card", "cash", "check", "zelle", "gift_card"}:
        raise ValidationError("Choose a supported visit payment method.")
    plan = visit_plan(policy, **values)
    quote = quote_lines(
        plan.lines, policy, card_base=None if expected_method == "card" else Decimal("0.00")
    )
    return quote | {
        "expected_method": expected_method,
        "membership_benefits_applied": bool(plan.uses),
        "membership_plan": plan.snapshot(),
    }


def actor_allowed(actor, booking):
    if actor is not None:
        require_actor(actor, "core.change_booking")
    elif booking.source != "customer_test" or booking.creation_actor_id is not None:
        raise PermissionDenied
    if booking.workflow != "integrated_v1":
        raise ValidationError("Use a confirmed integrated booking for membership benefits.")


def batch_for(*, actor, booking, request_key, action, reason, quote=None):
    key = lock_request(request_key)
    identity = fingerprint(
        dict(
            booking=booking.pk,
            quote=quote.pk if quote else None,
            action=action,
            reason=reason,
            actor=actor.pk if actor else None,
        )
    )
    previous = MembershipBenefitBatch.objects.filter(pk=key).first()
    if previous and previous.fingerprint != identity:
        raise ValidationError("This benefit request has already been used for a different change.")
    if previous:
        return previous, False
    batch = MembershipBenefitBatch.objects.create(
        id=key,
        booking=booking,
        quote=quote,
        action=action,
        reason=reason,
        fingerprint=identity,
        actor=actor,
    )
    AuditEvent.objects.create(
        actor=actor,
        action="membership.benefits_" + action,
        record_type="booking",
        record_id=str(booking.pk),
        changes={"batch": str(key), "quote": quote.pk if quote else None, "reason": reason},
    )
    return batch, True


def transition(assignment, batch):
    event = MembershipBenefitEvent.objects.create(assignment=assignment, batch=batch)
    MembershipBenefitState.objects.update_or_create(
        assignment=assignment, defaults={"status": batch.action, "event": event}
    )


@transaction.atomic
def reserve(*, actor, booking_id, quote_id, request_key, for_arrival=False):
    enabled()
    booking = Booking.objects.select_for_update().select_related("session").get(pk=booking_id)
    actor_allowed(actor, booking)
    request_key = lock_request(request_key)
    lock_customer(booking.customer_id)
    quote = BookingQuote.objects.select_related("policy").get(pk=quote_id, booking=booking)
    if type(for_arrival) is not bool or (
        for_arrival and (actor is None or booking.attendance != "arrived")
    ):
        raise ValidationError("Use the staff arrival confirmation for benefit usage.")
    if quote.pk != booking.quotes.first().pk or (booking.attendance and not for_arrival):
        raise ValidationError("Review the current upcoming booking before reserving benefits.")
    prior = MembershipBenefitBatch.objects.filter(pk=request_key).first()
    if prior:
        batch, _ = batch_for(
            actor=actor,
            booking=booking,
            quote=quote,
            request_key=request_key,
            action="reserved",
            reason="booking_confirmed",
        )
        return list(batch.assignments.all())
    current = quote.snapshot.get("membership_plan")
    if current is None:
        raise ValidationError("Review the member-aware visit estimate before confirming.")
    state = getattr(booking, "charge_state", None)
    comped = bool(state and state.comped)
    special = state.special_subtotal if state else None
    options = quote.snapshot.get("membership_options", {})
    if type(options.get("allow_new_unlimited", True)) is not bool:
        raise ValidationError("Review the membership benefit choices.")
    allowed = (
        None
        if options.get("allow_new_unlimited", True)
        else set(
            booking.membership_benefits.filter(
                current__status__in=["reserved", "used"], kind="unlimited_daily"
            ).values_list("purchase_id", "place")
        )
    )
    plan = visit_plan(
        quote.policy,
        customer_id=booking.customer_id,
        appointment_on=booking.session.starts_at.astimezone(NEW_YORK).date(),
        children=booking.children,
        adults=booking.adults,
        babies=booking.babies,
        socks=booking.socks,
        supervised=booking.supervised,
        exclude_booking=booking.pk,
        comped=comped,
        special_admissions=special,
        unlimited_places=allowed,
    )
    if current != plan.snapshot():
        raise ValidationError(
            "Membership benefits changed. Review the updated price before confirming."
        )
    # Replacing a quote atomically releases its old allocations. Their evidence
    # stays intact; excluding this booking above permits a same-day transfer.
    existing = list(booking.membership_benefits.filter(current__status__in=["reserved", "used"]))
    if any(item.quote_id == quote.pk for item in existing):
        raise ValidationError(
            "This quote already has a benefit reservation. Use its original request."
        )
    if existing:
        release_batch, created = batch_for(
            actor=actor,
            booking=booking,
            request_key=uuid.uuid5(uuid.UUID(str(request_key)), "replace"),
            action="released",
            reason="booking_changed",
        )
        if created:
            for item in existing:
                transition(item, release_batch)
    batch, _ = batch_for(
        actor=actor,
        booking=booking,
        quote=quote,
        request_key=request_key,
        action="reserved",
        reason="booking_confirmed",
    )
    assignments = []
    for use in plan.uses:
        member = MembershipPurchase.objects.get(
            pk=use.membership_id, customer_id=booking.customer_id
        )
        cycle = member.membership.cycles.get(
            starts_on=use.cycle_starts_on, ends_on=use.cycle_ends_on
        )
        item = MembershipBenefitAssignment.objects.create(
            booking=booking,
            quote=quote,
            purchase=member,
            place=use.place,
            kind=use.kind,
            appointment_on=use.appointment_on,
            cycle=cycle,
            price=use.price,
            rules_version=use.rules_version,
            reserved_by=batch,
        )
        transition(item, batch)
        assignments.append(item)
    return assignments


@transaction.atomic
def finish(*, actor, booking_id, request_key, action, reason):
    enabled()
    if actor is None:
        raise PermissionDenied
    booking = Booking.objects.select_for_update().get(pk=booking_id)
    actor_allowed(actor, booking)
    lock_customer(booking.customer_id)
    allowed = {
        "used": {"arrival"},
        "released": {"cancellation", "no_show", "booking_changed", "owner_correction"},
    }
    if action not in allowed or reason not in allowed[action]:
        raise ValidationError("Use an explicit arrival or benefit-release reason.")
    if reason == "owner_correction":
        require_actor(actor, "core.change_booking", owner=True)
    batch, created = batch_for(
        actor=actor, booking=booking, request_key=request_key, action=action, reason=reason
    )
    if created:
        states = ["reserved"] if action == "used" else ["reserved", "used"]
        for item in booking.membership_benefits.filter(current__status__in=states):
            transition(item, batch)
    return batch


def summary_for(member, *, on=None):
    """At-a-glance free quota, keeping reserved visits distinct from used visits."""
    on = on or today()
    root = member.membership
    cycle = root.cycles.filter(starts_on__lte=on, ends_on__gte=on).first()
    rules = accepted_rules(member.benefit_rules)
    current = bool(cycle) and payment_current(member)
    stop = member.billing_state.stopped_on
    current = current and (stop is None or on < stop)
    states = MembershipBenefitState.objects.filter(assignment__purchase=member)
    if root.kind == "unlimited":
        states = states.filter(assignment__kind="unlimited_daily", assignment__appointment_on=on)
        included = root.places
        excluded = CalendarDate.objects.filter(day=on, chol_hamoed=True).exists()
        current = current and not excluded
        label = "Free child visits today"
    else:
        states = (
            states.filter(assignment__kind="subscription_free", assignment__cycle=cycle)
            if cycle
            else states.none()
        )
        included = root.places * rules.subscription_free_visits
        label = "Free child visits this membership month"
    counts = Counter(states.values_list("status", flat=True))
    available = max(0, included - counts["reserved"] - counts["used"]) if current else 0
    return dict(
        label=label,
        included=included,
        reserved=counts["reserved"],
        used=counts["used"],
        available=available,
        can_apply=current,
        per_booking=root.places,
    )
