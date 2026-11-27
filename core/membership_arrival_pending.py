"""Durable accepted membership-first card payment and conditional arrival.

The first payment commits independently. Only its confirmed funding permits a
separate worker transaction to recheck the original visit and request its card
payment. Stale consent never turns into another charge or another purchase.
"""

import copy
import uuid
from datetime import date, timedelta
from datetime import timezone as datetime_timezone

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .availability import NEW_YORK
from .calendar import lock_calendar
from .membership_records import (
    MembershipArrivalCheckout,
    MembershipArrivalEvent,
    MembershipArrivalIntent,
    MembershipArrivalState,
)
from .models import Booking, BookingCapacityHold, DurableJob, OwnerNotice, Session
from .payments import checkout
from .payments.amounts import ZERO
from .payments.jobs import enqueue
from .payments.ledger import lock_request

FIELDS = (
    "children",
    "adults",
    "babies",
    "socks",
    "method",
    "split",
    "waiver_confirmed",
    "waiver_mismatch_accepted",
    "override_capacity",
    "special_admissions",
    "membership_resolution",
    "membership_resolution_reason",
)


def active_for_booking(booking_id):
    from .membership_schema import available

    if not available("core_membershiparrivalintent"):
        return None
    return (
        MembershipArrivalIntent.objects.filter(booking_id=booking_id)
        .exclude(progress__status="completed")
        .select_related("progress", "purchase__membership", "operation", "actor")
        .first()
    )


def check_access(booking, intent=None):
    active = active_for_booking(booking.pk)
    if active and (not isinstance(intent, MembershipArrivalIntent) or intent.pk != active.pk):
        raise ValidationError(
            "A membership purchase and arrival are already in progress. Check their status before another booking action."
        )


def waivers(booking):
    from .waivers.paper import active_customer_waivers

    return sorted(
        (
            dict(
                id=str(item.pk),
                kind="paper" if hasattr(item, "version_code") else "electronic",
                expires=item.valid_until.isoformat(),
            )
            for item in active_customer_waivers(booking)
        ),
        key=lambda item: (item["kind"], item["id"]),
    )


def session_facts(booking):
    play = booking.session
    return dict(
        id=play.pk,
        starts_at=play.starts_at.isoformat(),
        ends_at=play.ends_at.isoformat(),
        kind=play.kind,
        play_mode=play.play_mode,
    )


def create(*, actor, key, booking, member, data, reviewed):
    now = timezone.now().astimezone(datetime_timezone.utc)
    hold_key = uuid.uuid5(key, "arrival-extra-capacity")
    facts = {
        "review": reviewed["facts"],
        "offer": reviewed["offer"],
        "data": {name: data[name] for name in FIELDS if name in data},
        "waivers": reviewed["facts"]["waiver_evidence"],
    }
    operation = member.installments.first().invoice.sale.operations.get(
        kind="receipt", tender="card"
    )
    intent = MembershipArrivalIntent.objects.create(
        id=key,
        purchase=member,
        booking=booking,
        operation=operation,
        actor=actor,
        fingerprint=reviewed["fingerprint"],
        facts=facts,
        hold_key=hold_key,
        accepted_at=now,
        expires_at=now + timedelta(minutes=30),
    )
    MembershipArrivalState.objects.create(intent=intent, booking=booking)
    MembershipArrivalEvent.objects.create(intent=intent, status="waiting", actor=actor)
    delta = {
        name: max(0, data.get(name, getattr(booking, name)) - getattr(booking, name))
        for name in ("children", "adults", "babies")
    }
    if any(delta.values()):
        BookingCapacityHold.objects.create(
            id=hold_key,
            actor=actor,
            customer=booking.customer,
            session=booking.session,
            **delta,
            supervised=booking.supervised,
            expires_at=intent.expires_at,
        )
    return intent


def data_for(intent):
    return intent.facts["data"] | {"apply_available_benefits": True}


def restore_offer(intent):
    offer = copy.deepcopy(intent.facts["offer"])
    for row in offer["cycles"]:
        for name in ("starts_on", "ends_on", "charge_on"):
            if isinstance(row.get(name), str):
                row[name] = date.fromisoformat(row[name])
    return offer


def fresh_preview(intent, *, proposed):
    from .membership_arrival import ProposedMembership, normalized
    from .membership_reservations import payment_current
    from .membership_sales import today

    booking = Booking.objects.select_related("session", "customer").get(pk=intent.booking_id)
    if session_facts(booking) != intent.facts["review"]["session"]:
        raise ValidationError("The session changed. Review the visit before continuing.")
    if (
        timezone.now() >= intent.expires_at
        or booking.session.starts_at.astimezone(NEW_YORK).date() != today()
    ):
        raise ValidationError(
            "The temporary reservation ended. Review the visit before continuing."
        )
    current_waivers = waivers(booking)
    if any(item not in current_waivers for item in intent.facts["waivers"]):
        raise ValidationError("Waiver coverage changed. Review the visit before continuing.")
    delta = {
        name: max(0, data_for(intent).get(name, getattr(booking, name)) - getattr(booking, name))
        for name in ("children", "adults", "babies")
    }
    if any(delta.values()):
        hold = BookingCapacityHold.objects.filter(
            pk=intent.hold_key,
            actor_id=intent.actor_id,
            customer_id=booking.customer_id,
            session_id=booking.session_id,
            expires_at=intent.expires_at,
            **delta,
            supervised=booking.supervised,
        ).first()
        if hold is None:
            raise ValidationError(
                "The reserved attendee amounts changed. Review the visit before continuing."
            )
    if not proposed and not payment_current(intent.purchase):
        raise ValidationError("The membership payment requires review before completing arrival.")
    result = checkout.preview(
        actor=intent.actor,
        booking_id=intent.booking_id,
        kind="arrival",
        data=data_for(intent),
        proposed_membership=ProposedMembership(restore_offer(intent)) if proposed else None,
        membership_intent=intent,
    )
    member_id = 9223372036854775807 if proposed else intent.purchase_id
    compared = normalized(result[4], member_id)
    prior_coverage = intent.facts["review"]["arrival"]["waiver_review"]
    if compared["waiver_review"]["recorded_minors"] >= prior_coverage["recorded_minors"]:
        compared["waiver_review"] = prior_coverage
    if compared != intent.facts["review"]["arrival"]:
        raise ValidationError(
            "The visit, payment source or price changed. Review it before continuing."
        )
    return result


def mark_review(intent, code):
    state = MembershipArrivalState.objects.select_for_update().get(intent=intent)
    if state.status == "completed" or (state.status == "review" and state.code == code):
        return state
    state.status, state.code = "review", code
    state.revision += 1
    state.save(update_fields=["status", "code", "revision", "updated_at"])
    MembershipArrivalEvent.objects.create(intent=intent, status="review", code=code)
    OwnerNotice.objects.get_or_create(
        customer=intent.purchase.customer,
        subject="Membership purchase and arrival need review",
        details={
            "kind": "membership_arrival",
            "booking_id": intent.booking_id,
            "intent_id": str(intent.pk),
            "booking_reference": str(intent.booking.reference),
        },
    )
    return state


def lock_operation(operation):
    if (
        not settings.MEMBERSHIP_SALES_ENABLED
        or operation.kind != "receipt"
        or operation.sale.kind != "membership"
    ):
        return None
    intent = MembershipArrivalIntent.objects.filter(operation_id=operation.pk).first()
    if intent:
        from .membership_reservations import lock_customer

        lock_calendar()
        booking = Booking.objects.select_for_update().get(pk=intent.booking_id)
        Session.objects.select_for_update().get(pk=booking.session_id)
        lock_customer(operation.sale.customer_id)
        return MembershipArrivalIntent.objects.select_related("purchase", "actor").get(pk=intent.pk)
    return None


def allow_dispatch(intent):
    if intent is None:
        return True
    try:
        fresh_preview(intent, proposed=True)
    except (ValidationError, PermissionDenied):
        mark_review(intent, "changed_before_first_charge")
        return False
    return True


def queue_ready(member):
    if not settings.MEMBERSHIP_SALES_ENABLED:
        return
    from .membership_sales import installment_paid

    intent = MembershipArrivalIntent.objects.filter(purchase=member).first()
    first = member.installments.first()
    if intent and first and installment_paid(first) and intent.progress.status != "completed":
        enqueue(
            kind="membership_arrival",
            reference=intent.pk,
            key=f"membership-arrival-funded:{intent.pk}",
        )


def status_data(intent):
    from .customer_credit import applied
    from .membership_sales import installment_paid, membership_status
    from .payments.invoices import received, settled, total

    first = intent.purchase.installments.first()
    sale = first.invoice.sale
    status = membership_status(intent.purchase)
    states = set(sale.operations.values_list("state", flat=True))
    if not settings.MEMBERSHIP_SALES_ENABLED:
        state, message = (
            "review",
            "Membership processing is paused. The accepted payments and visit details are saved for review.",
        )
    elif intent.progress.status == "review" or timezone.now() >= intent.expires_at:
        state, message = (
            "review",
            "Review the membership and visit before completing arrival. The visit card payment has not been requested.",
        )
    elif status == "review":
        state, message = (
            "review",
            "The membership funding needs owner review. The visit card payment has not been requested.",
        )
    elif states & {"unknown", "action"}:
        state, message = (
            "review",
            "The membership payment outcome is not confirmed. Check its existing payment record before another attempt. The visit card payment has not been requested.",
        )
    elif states & {"ready", "sending"}:
        state, message = (
            "processing",
            "Membership payment is processing. The visit card payment has not been requested.",
        )
        if (
            "sending" not in states
            and DurableJob.objects.filter(
                kind="payment_dispatch", reference=str(intent.operation_id), state="blocked"
            ).exists()
        ):
            state, message = (
                "review",
                "The membership payment has not been sent. Review its existing payment record before continuing. The visit card payment has not been requested.",
            )
    elif installment_paid(first):
        state, message = (
            "processing",
            "Membership payment confirmed. Completing the reviewed arrival.",
        )
        if DurableJob.objects.filter(
            kind="membership_arrival", reference=str(intent.pk), state="blocked"
        ).exists():
            state, message = (
                "review",
                "Membership payment confirmed. Arrival needs review before the visit card payment can be requested.",
            )
    else:
        state, message = (
            "declined",
            "The membership payment was declined or cancelled. Review its payment before continuing. The visit card payment has not been requested.",
        )
    job = DurableJob.objects.filter(kind="membership_arrival", reference=str(intent.pk)).first()
    can_continue = bool(
        settings.MEMBERSHIP_SALES_ENABLED
        and status in {"active", "scheduled"}
        and installment_paid(first)
        and timezone.now() < intent.expires_at
        and intent.actor.is_active
        and (intent.progress.status == "review" or job is None or job.state in {"blocked", "done"})
    )
    if can_continue:
        try:
            fresh_preview(intent, proposed=False)
        except (ValidationError, PermissionDenied):
            can_continue = False
    return dict(
        state=state,
        message=message,
        membership_received=str(received(sale)),
        membership_amount=str(total(sale)),
        credit_applied=applied(sale),
        membership_balance=str(max(ZERO, total(sale) - settled(sale))),
        received=str(received(sale)),
        code=intent.progress.code,
        pending_membership=True,
        can_check=True,
        can_continue=can_continue,
    )


@transaction.atomic
def complete(intent_id):
    from .membership_arrival import queue_confirmation
    from .membership_reservations import lock_customer
    from .membership_sales import enabled

    enabled()

    intent = MembershipArrivalIntent.objects.select_related("purchase", "actor").get(pk=intent_id)
    lock_request(intent.pk)
    lock_calendar()
    booking = Booking.objects.select_for_update().get(pk=intent.booking_id)
    Session.objects.select_for_update().get(pk=booking.session_id)
    lock_customer(intent.purchase.customer_id)
    intent = MembershipArrivalIntent.objects.select_related("purchase", "actor").get(pk=intent_id)
    state = MembershipArrivalState.objects.select_for_update().get(intent=intent)
    if state.status == "completed":
        return state
    try:
        with transaction.atomic():
            result = fresh_preview(intent, proposed=False)
            arrival = checkout.confirm(
                actor=intent.actor,
                booking_id=intent.booking_id,
                kind="arrival",
                data=data_for(intent),
                request_key=intent.pk,
                reviewed_hash=result[-1],
                confirmed=True,
                membership_intent=intent,
            )
            record = MembershipArrivalCheckout.objects.create(
                id=intent.pk,
                purchase=intent.purchase,
                checkout=arrival,
                fingerprint=intent.fingerprint,
                facts=intent.facts["review"],
                actor=intent.actor,
            )
            BookingCapacityHold.objects.filter(pk=intent.hold_key).delete()
            state.status, state.code = "completed", ""
            state.revision += 1
            state.save(update_fields=["status", "code", "revision", "updated_at"])
            MembershipArrivalEvent.objects.create(intent=intent, status="completed")
            OwnerNotice.objects.filter(
                details__kind="membership_arrival",
                details__intent_id=str(intent.pk),
                reviewed_at__isnull=True,
            ).update(reviewed_at=timezone.now())
            queue_confirmation(record)
    except (ValidationError, PermissionDenied):
        return mark_review(intent, "visit_review_required")
    return state
