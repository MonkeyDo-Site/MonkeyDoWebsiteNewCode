"""Stop only a pending visit; preserve purchase, cancellation and booking history."""

import uuid

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .membership_arrival_recovery import authorize, locked, require_owner
from .membership_records import (
    MembershipArrivalClosure,
    MembershipArrivalEvent,
    MembershipArrivalState,
)
from .models import AuditEvent, BookingCapacityHold, OwnerNotice
from .payments.amounts import ZERO
from .payments.ledger import fingerprint, lock_request


def cancellation_for(intent):
    return intent.purchase.cancellations.order_by("created_at", "pk").first()


def authorize_cancelled(actor, intent, *, reviewing=False):
    from .membership_arrival_funds import authorize as authorize_visit_funds
    from .models import PaymentOperation

    authorize_visit_funds(actor, intent, reviewing=reviewing)
    record = cancellation_for(intent)
    if not record:
        raise ValidationError(
            "Review the existing membership cancellation before stopping arrival."
        )
    if PaymentOperation.objects.filter(
        sale__membership_invoice__installment__purchase=intent.purchase,
        kind="receipt",
        state__in=("ready", "sending", "unknown", "action"),
    ).exists():
        raise ValidationError("Reconcile the existing membership receipts before stopping arrival.")
    return record


@transaction.atomic
def begin_cancelled_review(*, actor, intent_id):
    from .membership_arrival_pending import mark_review

    require_owner(actor)
    intent = locked(intent_id)
    authorize_cancelled(actor, intent)
    if intent.progress.code == "owner_review_requested":
        return intent.progress
    state = mark_review(intent, "owner_review_requested")
    AuditEvent.objects.create(
        actor=actor,
        action="membership.arrival_close_review_started",
        record_type="booking",
        record_id=str(intent.booking.reference),
        changes={"intent_id": str(intent.pk)},
    )
    return state


def cancellation_snapshot(record):
    from .membership_cancellations import plan_paid, plan_pending

    plans = list(record.refund_plans.order_by("created_at", "pk"))
    rows = [
        dict(
            plan=str(plan.pk),
            amount=str(plan.amount),
            paid=str(plan_paid(plan)),
            pending=plan_pending(plan),
            attempts=[
                (str(a.operation_id), a.operation.state)
                for a in plan.attempts.select_related("operation").order_by(
                    "operation__requested_at", "pk"
                )
            ],
        )
        for plan in plans
    ]
    return dict(
        id=str(record.pk),
        stopped_on=record.stopped_on.isoformat(),
        timing=record.timing,
        fingerprint=record.fingerprint,
        refund_amount=str(record.refund_amount),
        refund_paid=str(sum((plan_paid(plan) for plan in plans), ZERO)),
        refund_due=str(sum((max(ZERO, plan.amount - plan_paid(plan)) for plan in plans), ZERO)),
        refund_plans=rows,
    )


def review(*, actor, intent):
    from .customer_credit import applied
    from .membership_arrival_receipts import rows, snapshot
    from .payments.invoices import received, total
    from .payments.zelle import facts as bank_facts

    cancellation = cancellation_for(intent)
    if cancellation:
        authorize_cancelled(actor, intent, reviewing=True)
    else:
        authorize(actor, intent, reviewing=True)
    booking = intent.booking
    if booking.attendance or hasattr(intent, "closure"):
        raise ValidationError("This arrival has already ended. Open the saved booking.")
    sources = rows(intent)
    if any(hasattr(r, "application") or r.available_amount != ZERO for r in sources):
        raise ValidationError(
            "Return and record all unused visit funds before stopping this arrival. Keep their original receipts."
        )
    sale = intent.purchase.installments.first().invoice.sale
    if (
        not cancellation
        and sale.operations.filter(state__in=("ready", "sending", "unknown", "action")).exists()
    ):
        raise ValidationError("Reconcile the existing membership payment before stopping arrival.")
    bank = bank_facts(booking)
    hold = BookingCapacityHold.objects.filter(pk=intent.hold_key).first()
    facts = dict(
        intent=str(intent.pk),
        purchase=intent.purchase_id,
        original_fingerprint=intent.fingerprint,
        actor=actor.pk,
        booking=booking.pk,
        booking_version=booking.edit_version,
        session=booking.session_id,
        review_revision=intent.progress.revision,
        booking_counts={k: getattr(booking, k) for k in ("children", "adults", "babies", "socks")},
        membership_sale=str(sale.pk),
        membership_received=str(received(sale)),
        membership_credit=str(applied(sale)),
        membership_total=str(total(sale)),
        visit_receipts=snapshot(intent),
        bank_available=str(bank["available"]),
        bank_identity=bank["identity"],
        extra_hold=dict(
            children=hold.children,
            adults=hold.adults,
            babies=hold.babies,
            expires_at=hold.expires_at.isoformat(),
        )
        if hold
        else None,
    )
    if cancellation:
        facts["cancellation"] = cancellation_snapshot(cancellation)
    return facts, fingerprint(facts)


@transaction.atomic
def stop(*, actor, intent_id, request_key, reviewed_hash, reason, confirmed=False):
    from .membership_sales import queue_confirmation
    from .membership_schema import available

    require_owner(actor)
    if not available("core_membershiparrivalclosure"):
        raise ValidationError("Stopping this arrival is not available for this release yet.")
    if confirmed is not True:
        raise ValidationError(
            "Confirm that the original booking will be kept and membership records stay separate."
        )
    if not isinstance(reason, str) or not 0 < len(reason.strip()) <= 500:
        raise ValidationError("Enter a reason using 500 characters or fewer.")
    try:
        intent_id = uuid.UUID(str(intent_id))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Choose the original unfinished arrival.") from None
    reason = reason.strip()
    key = lock_request(request_key)
    prior = MembershipArrivalClosure.objects.filter(request_key=key).first()
    if prior:
        if (
            prior.intent_id,
            prior.actor_id,
            prior.reason,
            prior.facts.get("reviewed_hash"),
        ) != (intent_id, actor.pk, reason, reviewed_hash):
            raise ValidationError(
                "This confirmation already identifies a different stopped arrival."
            )
        return prior
    intent = locked(intent_id)
    facts, current_hash = review(actor=actor, intent=intent)
    if reviewed_hash != current_hash:
        raise ValidationError("The booking or received funds changed. Review this arrival again.")
    facts["reviewed_hash"] = current_hash
    result = MembershipArrivalClosure.objects.create(
        intent=intent,
        cancellation=cancellation_for(intent),
        request_key=key,
        reason=reason,
        facts=facts,
        actor=actor,
        fingerprint=fingerprint(dict(facts=facts, reason=reason)),
    )
    BookingCapacityHold.objects.filter(pk=intent.hold_key).delete()
    state = MembershipArrivalState.objects.select_for_update().get(intent=intent)
    state.status, state.code = "stopped", "owner_stopped_arrival"
    state.revision += 1
    state.save(update_fields=["status", "code", "revision", "updated_at"])
    MembershipArrivalEvent.objects.create(
        intent=intent, status="stopped", code=state.code, actor=actor
    )
    OwnerNotice.objects.filter(
        details__kind="membership_arrival",
        details__intent_id=str(intent.pk),
        reviewed_at__isnull=True,
    ).update(reviewed_at=timezone.now())
    AuditEvent.objects.create(
        actor=actor,
        action="membership.arrival_stopped",
        record_type="booking",
        record_id=str(intent.booking.reference),
        changes=dict(intent=str(intent.pk), purchase=intent.purchase_id, reason=reason),
    )
    if result.cancellation_id is None:
        queue_confirmation(intent.purchase)
    return result
