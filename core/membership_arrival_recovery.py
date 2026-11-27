"""Fresh owner authority for a paid membership's unfinished arrival."""

import copy

from django.core.exceptions import ValidationError
from django.db import transaction

from .calendar import lock_calendar
from .membership_records import (
    MembershipArrivalCheckout,
    MembershipArrivalIntent,
    MembershipArrivalResolution,
    MembershipArrivalState,
)
from .models import AuditEvent, Booking, Session
from .payments import checkout
from .payments.ledger import lock_request
from .permissions import require_actor


def require_owner(actor):
    from .membership_sales import enabled

    enabled()
    checkout.authorize(actor)
    require_actor(actor, "core.view_membershippurchase", owner=True)


def authorize(actor, intent, *, reviewing=False):
    from .membership_funding import member_needs_review
    from .membership_sales import installment_paid

    require_owner(actor)
    if intent.progress.status == "completed":
        raise ValidationError("Arrival is already completed. Open the saved booking.")
    first = intent.purchase.installments.first()
    if not first or not installment_paid(first) or member_needs_review(intent.purchase):
        raise ValidationError(
            "Confirm the existing membership payment and resolve its funding before reviewing arrival."
        )
    if intent.purchase.cancellations.exists():
        raise ValidationError("Review the membership cancellation before completing this arrival.")
    if reviewing and intent.progress.code != "owner_review_requested":
        raise ValidationError("Start a fresh owner review from the arrival status page.")


def locked(intent_id):
    from .membership_reservations import lock_customer

    lock_request(intent_id)
    lock_calendar()
    intent = MembershipArrivalIntent.objects.get(pk=intent_id)
    booking = Booking.objects.select_for_update().get(pk=intent.booking_id)
    Session.objects.select_for_update().get(pk=booking.session_id)
    lock_customer(booking.customer_id)
    return MembershipArrivalIntent.objects.select_related("purchase", "actor", "progress").get(
        pk=intent_id
    )


@transaction.atomic
def begin_review(*, actor, intent_id):
    from .membership_arrival_pending import mark_review

    require_owner(actor)
    intent = locked(intent_id)
    if intent.progress.status == "completed":
        return intent.progress
    authorize(actor, intent)
    state = mark_review(intent, "owner_review_requested")
    AuditEvent.objects.create(
        actor=actor,
        action="membership.arrival_review_started",
        record_type="booking",
        record_id=str(intent.booking.reference),
        changes={"intent_id": str(intent.pk)},
    )
    return state


def marker(actor, intent, data):
    authorize(actor, intent, reviewing=True)
    if str(data.get("pending_review")) != str(intent.pk):
        raise ValidationError("This review belongs to a different unfinished arrival.")
    reason = data.get("pending_reason", "")
    if not isinstance(reason, str) or len(reason.strip()) > 500:
        raise ValidationError("Enter a reason using 500 characters or fewer.")
    return dict(
        intent=str(intent.pk),
        actor=actor.pk,
        original_fingerprint=intent.fingerprint,
        reason=reason.strip(),
    )


def data_for(intent, data):
    selected = data.get("pending_review")
    if selected and str(selected) != str(intent.pk):
        raise ValidationError("This review belongs to a different unfinished arrival.")
    return data | {"pending_review": intent.pk, "apply_available_benefits": True}


def preview(*, actor, intent, data, validate_waivers=True):
    authorize(actor, intent, reviewing=True)
    return checkout.preview(
        actor=actor,
        booking_id=intent.booking_id,
        kind="arrival",
        data=data_for(intent, data),
        validate_waivers=validate_waivers,
        membership_intent=intent,
    ), None


@transaction.atomic
def confirm(*, actor, intent_id, data, request_key, reviewed_hash, confirmed):
    from .membership_arrival import normalized, queue_confirmation
    from .membership_arrival_pending import finish, session_facts, waivers

    require_owner(actor)
    if confirmed is not True:
        raise ValidationError("Confirm the current visit and its selected payment action.")
    key = lock_request(request_key)
    prior = MembershipArrivalResolution.objects.filter(request_key=key).first()
    if prior:
        if (
            prior.intent_id != intent_id
            or prior.actor_id != actor.pk
            or prior.fingerprint != reviewed_hash
        ):
            raise ValidationError("This confirmation already identifies another owner review.")
        return prior.checkout
    intent = locked(intent_id)
    authorize(actor, intent, reviewing=True)
    if not isinstance(data.get("pending_reason"), str) or not data["pending_reason"].strip():
        raise ValidationError("Enter the reason for reviewing this arrival again.")
    result, _ = preview(actor=actor, intent=intent, data=data)
    if result[-1] != reviewed_hash:
        raise ValidationError("The visit or payment changed. Review its current total again.")
    arrival = checkout.confirm(
        actor=actor,
        booking_id=intent.booking_id,
        kind="arrival",
        data=data_for(intent, data),
        request_key=intent.pk,
        reviewed_hash=reviewed_hash,
        confirmed=True,
        membership_intent=intent,
    )
    MembershipArrivalResolution.objects.create(
        intent=intent,
        checkout=arrival,
        request_key=key,
        fingerprint=reviewed_hash,
        reason=data["pending_reason"].strip(),
        actor=actor,
    )
    facts = copy.deepcopy(intent.facts["review"])
    facts.update(
        actor=actor.pk,
        arrival=normalized(arrival.details, intent.purchase_id),
        session=session_facts(arrival.booking),
        waiver_evidence=waivers(arrival.booking),
        original_intent=str(intent.pk),
        original_fingerprint=intent.fingerprint,
    )
    record = MembershipArrivalCheckout.objects.create(
        id=intent.pk,
        purchase=intent.purchase,
        checkout=arrival,
        actor=actor,
        fingerprint=reviewed_hash,
        facts=facts,
    )
    state = MembershipArrivalState.objects.select_for_update().get(intent=intent)
    finish(intent, state, code="owner_re_reviewed")
    AuditEvent.objects.create(
        actor=actor,
        action="membership.arrival_re_reviewed",
        record_type="booking",
        record_id=str(intent.booking.reference),
        changes={"intent_id": str(intent.pk), "reason": data["pending_reason"].strip()},
    )
    queue_confirmation(record)
    return arrival
