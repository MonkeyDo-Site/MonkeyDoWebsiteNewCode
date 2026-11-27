"""Owner records an actual original-tender return of unused visit receipts."""

import uuid

from django.core.exceptions import ValidationError
from django.db import transaction

from .membership_records import MembershipArrivalReceipt, MembershipArrivalReceiptReturn
from .models import AuditEvent
from .payments.amounts import ZERO, amount
from .payments.ledger import fingerprint, lock_request
from .payments.receipts import receipt_date


def review(*, actor, receipt_id):
    from .membership_arrival_receipts import rows
    from .membership_arrival_recovery import authorize, require_owner

    require_owner(actor)
    source = MembershipArrivalReceipt.objects.select_related(
        "intent__purchase", "intent__progress"
    ).get(pk=receipt_id)
    authorize(actor, source.intent, reviewing=True)
    current = next(r for r in rows(source.intent) if r.pk == source.pk)
    if hasattr(current, "application") or current.available_amount <= ZERO:
        raise ValidationError(
            "This receipt has no unused funds to return. Review its original payment history."
        )
    facts = dict(
        receipt=str(source.pk),
        intent=str(source.intent_id),
        actor=actor.pk,
        amount=str(source.amount),
        available=str(current.available_amount),
        tender=source.tender,
        received_on=str(source.received_on),
        returns=[(str(r.pk), str(r.amount), str(r.completed_on)) for r in current.return_events],
    )
    return dict(
        source=source,
        facts=facts,
        fingerprint=fingerprint(facts),
        available=current.available_amount,
    )


@transaction.atomic
def record(
    *,
    actor,
    receipt_id,
    request_key,
    value,
    completed_on,
    reviewed_hash,
    confirmed=False,
    verified_returned=False,
):
    from .membership_arrival_recovery import begin_review, locked, require_owner
    from .membership_schema import available

    require_owner(actor)
    if not available("core_membershiparrivalreceiptreturn"):
        raise ValidationError("Return recording is not available for this release yet.")
    if confirmed is not True or verified_returned is not True:
        raise ValidationError(
            "Confirm that this amount was actually returned using its original payment method."
        )
    try:
        receipt_id = uuid.UUID(str(receipt_id))
    except (ValueError, TypeError, AttributeError) as error:
        raise ValidationError("Choose an original visit receipt.") from error
    value, day = amount(value), receipt_date(completed_on)
    key = lock_request(request_key)
    prior = MembershipArrivalReceiptReturn.objects.filter(request_key=key).first()
    if prior:
        if (
            prior.receipt_id,
            prior.actor_id,
            prior.amount,
            prior.completed_on,
            prior.fingerprint,
        ) != (receipt_id, actor.pk, value, day, reviewed_hash):
            raise ValidationError(
                "This return confirmation was already used for different details."
            )
        return prior
    source = MembershipArrivalReceipt.objects.get(pk=receipt_id)
    intent = locked(source.intent_id)
    current = review(actor=actor, receipt_id=source.pk)
    if current["fingerprint"] != reviewed_hash:
        raise ValidationError(
            "The unused receipt balance changed. Review it before recording the return."
        )
    if not ZERO < value <= current["available"] or day < source.received_on:
        raise ValidationError(
            "Use a positive amount within the unused balance and an actual return date on or after its receipt date."
        )
    # Stops the original visit continuation. This records no new card authority.
    begin_review(actor=actor, intent_id=intent.pk)
    result = MembershipArrivalReceiptReturn.objects.create(
        receipt=source,
        request_key=key,
        fingerprint=reviewed_hash,
        reviewed_available=current["available"],
        amount=value,
        completed_on=day,
        actor=actor,
    )
    AuditEvent.objects.create(
        actor=actor,
        action="payment.pending_visit_returned",
        record_type="booking",
        record_id=str(intent.booking.reference),
        changes=dict(
            receipt=str(source.pk),
            return_id=str(result.pk),
            amount=str(value),
            tender=source.tender,
            completed_on=str(day),
        ),
    )
    return result


def total_for_purchase(purchase):
    from django.db.models import Sum

    from .membership_schema import available

    if not available("core_membershiparrivalreceiptreturn"):
        return ZERO
    return (
        MembershipArrivalReceiptReturn.objects.filter(receipt__intent__purchase=purchase).aggregate(
            n=Sum("amount")
        )["n"]
        or ZERO
    )
