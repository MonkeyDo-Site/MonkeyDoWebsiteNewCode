"""Release unused original visit funds without inventing a membership refund.

Known membership receipts/returns remain on their own invoice. The owner must
cancel the membership immediately and finish the chosen original-card refunds
before cancelling only the reserved membership amount that was never collected.
"""

import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction

from .membership_paid_visit_records import (
    MembershipPaidVisitCancellation,
    MembershipPaidVisitRelease,
)
from .payments.amounts import ZERO, amount
from .payments.ledger import fingerprint, lock_request, lock_sale


def available():
    with connection.cursor() as cursor:
        return "core_membershippaidvisitcancellation" in connection.introspection.table_names(
            cursor
        )


def decision(intent_id):
    if not available():
        return None
    return (
        MembershipPaidVisitCancellation.objects.select_related("cancellation")
        .filter(release_id=intent_id)
        .first()
    )


def cancellation_updated(record):
    """A reserved source needs persistent attention, even before a worker runs."""
    from .membership_paid_visit_pending import active, mark_review
    from .membership_paid_visit_pending import available as intent_available

    if intent_available():
        intent = active().filter(purchase_id=record.purchase_id).first()
        if intent:
            mark_review(intent.pk)


def check_return_source(operation, plan_ids, sale_id):
    from .membership_paid_visit_manual import is_manual_receipt

    attempt = getattr(operation, "membership_refund_attempt", None)
    original = operation.original
    if (
        operation.kind != "refund"
        or attempt is None
        or attempt.plan_id not in plan_ids
        or original is None
        or attempt.plan.original_id != original.pk
        or original.sale_id != sale_id
        or original.kind != "receipt"
        or original.state != "succeeded"
        or operation.tender != original.tender
        or (operation.tender != "card" and not is_manual_receipt(original))
        or operation.method_id != original.method_id
    ):
        raise ValidationError(
            "A separate payment correction needs owner reconciliation before this release."
        )


def review(*, actor, intent):
    from .membership_cancellations import owner, plan_paid, plan_pending, unrecorded_provider_return
    from .membership_sales import today
    from .payments.invoices import effective_components, received, total
    from .permissions import require_actor

    owner(actor)
    require_actor(actor, "core.change_booking", owner=True)
    if not available():
        raise ValidationError("Complete the reviewed cancellation-source upgrade first.")
    if MembershipPaidVisitRelease.objects.filter(intent=intent).exists():
        raise ValidationError("This visit reservation was already completed or stopped.")
    from .membership_paid_visit_new_card import require_known_storage

    require_known_storage(intent)
    record = intent.purchase.cancellations.first()
    if not record:
        raise ValidationError(
            "Record an immediate membership cancellation before releasing these reserved visit funds."
        )
    if record.stopped_on > today():
        raise ValidationError(
            "This membership cancellation is not effective yet. Keep the visit funds reserved until it is effective."
        )
    member = intent.purchase
    if member.billing_state.stopped_on != record.stopped_on:
        raise ValidationError("Review the recorded cancellation and membership dates.")
    if member.benefit_assignments.exists() or member.visit_conversions.exists():
        raise ValidationError(
            "This membership has visit benefits or converted funds that need separate owner review."
        )
    sale = member.installments.first().invoice.sale
    operations = list(sale.operations.select_related("original").order_by("pk"))
    if any(op.state not in {"succeeded", "declined", "cancelled"} for op in operations):
        raise ValidationError(
            "Confirm the existing card payment and chosen refunds before releasing the original visit funds."
        )
    if sale.credit_applications.exists():
        raise ValidationError(
            "Applied credit needs its separate return review before releasing this visit."
        )
    receipts = [op for op in operations if op.kind == "receipt" and op.state == "succeeded"]
    from .membership_paid_visit_manual import cancellation_adjustments_valid, expected_new_payment

    if not receipts or sum((op.amount for op in receipts), ZERO) != expected_new_payment(intent):
        raise ValidationError(
            "Review the actual new membership payment before releasing this source."
        )
    if any(unrecorded_provider_return(op) for op in receipts):
        raise ValidationError(
            "Record the already completed provider return before releasing these visit funds."
        )
    plans = list(record.refund_plans.prefetch_related("attempts__operation").order_by("pk"))
    if any(plan_pending(plan) or plan_paid(plan) != plan.amount for plan in plans):
        raise ValidationError(
            "Record all chosen membership refunds as completed before releasing the original visit funds."
        )
    if sum((plan.amount for plan in plans), ZERO) != record.refund_amount:
        raise ValidationError("The recorded cancellation refund plans need review.")
    returns = [op for op in operations if op.kind != "receipt" and op.state == "succeeded"]
    plan_ids = {plan.pk for plan in plans}
    for op in returns:
        check_return_source(op, plan_ids, sale.pk)
    values = effective_components(sale)
    if len(values) != 1 or any(part["item_tax"] or part["fee_tax"] for part in values.values()):
        raise ValidationError("Historical membership tax needs separate owner review.")
    line_id, components = next(iter(values.items()))
    if not cancellation_adjustments_valid(intent, sale):
        raise ValidationError(
            "Review other membership invoice corrections before releasing this source."
        )
    paid = sum((op.amount for op in receipts), ZERO)
    returned = sum((op.amount for op in returns), ZERO)
    held = received(sale)
    fee = sum((amount(part["fee"]) for op in receipts for part in op.allocation), ZERO)
    if (
        held != paid - returned
        or returned != record.refund_amount
        or fee != components["fee"]
        or held < fee
    ):
        raise ValidationError("The actual refund and retained fee need reconciliation.")
    uncollected = total(sale) - held
    if uncollected <= ZERO or uncollected != amount(intent.offer["paid_visit"]["applied"]):
        raise ValidationError(
            "The uncollected membership amount no longer matches the reserved original visit funds."
        )
    source = intent.source_sale
    data = dict(
        intent=str(intent.pk),
        purchase=intent.purchase_id,
        actor=actor.pk,
        on=today().isoformat(),
        offer=intent.fingerprint,
        cancellation=str(record.pk),
        cancellation_fingerprint=record.fingerprint,
        stopped_on=record.stopped_on.isoformat(),
        billing_revision=member.billing_state.revision,
        membership_sale=str(sale.pk),
        line=line_id,
        membership_total=str(total(sale)),
        received=str(paid),
        returned=str(returned),
        retained=str(held),
        retained_fee=str(fee),
        retained_principal=str(held - fee),
        uncollected=str(uncollected),
        refund_amount=str(record.refund_amount),
        operations=[
            dict(id=str(op.pk), kind=op.kind, state=op.state, amount=str(op.amount))
            for op in operations
        ],
        plans=[
            dict(id=str(plan.pk), amount=str(plan.amount), paid=str(plan_paid(plan)))
            for plan in plans
        ],
        source=str(source.pk),
        source_total=str(total(source)),
        source_received=str(received(source)),
        source_returned=str(
            sum(
                (
                    op.amount
                    for op in source.operations.filter(state="succeeded").exclude(kind="receipt")
                ),
                ZERO,
            )
        ),
        source_operations=[
            dict(id=str(op.pk), kind=op.kind, state=op.state, amount=str(op.amount))
            for op in source.operations.order_by("pk")
        ],
        booking=intent.booking_id,
        booking_version=intent.booking.edit_version,
    )
    return data | dict(fingerprint=fingerprint(data))


@transaction.atomic
def release(*, actor, intent_id, request_key, reviewed, reason, confirmed=False):
    from .membership_cancellations import owner
    from .membership_paid_visit_pending import locked, resolve_notices
    from .models import AuditEvent, FinancialLineAdjustment
    from .payments.ledger import writes_allowed
    from .permissions import require_actor

    owner(actor)
    require_actor(actor, "core.change_booking", owner=True)
    writes_allowed()
    if confirmed is not True:
        raise ValidationError(
            "Confirm the reviewed release and cancellation of the uncollected membership amount."
        )
    if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 500:
        raise ValidationError(
            "Enter a short owner reason for releasing these reserved visit funds."
        )
    if not available():
        raise ValidationError("Complete the reviewed cancellation-source upgrade first.")
    key = lock_request(request_key)
    prior = MembershipPaidVisitCancellation.objects.filter(request_key=key).first()
    if prior:
        if (
            str(prior.release_id) != str(intent_id)
            or prior.actor_id != actor.pk
            or prior.reason != reason.strip()
            or prior.facts.get("reviewed_hash") != reviewed
        ):
            raise ValidationError(
                "This source-release identity belongs to another reviewed action."
            )
        return prior
    intent = locked(intent_id)
    lock_sale(intent.purchase.installments.first().invoice.sale_id)
    facts = review(actor=actor, intent=intent)
    if facts["fingerprint"] != reviewed:
        raise ValidationError(
            "The cancellation, payment or source changed. Review the release again."
        )
    facts["reviewed_hash"] = reviewed
    facts["adjustment_key"] = str(uuid.uuid5(key, "cancel-uncollected-membership"))
    frozen = MembershipPaidVisitCancellation.objects.create(
        release_id=intent.pk,
        cancellation_id=uuid.UUID(facts["cancellation"]),
        request_key=key,
        facts=facts,
        reason=reason.strip(),
        actor=actor,
        fingerprint=fingerprint(dict(facts=facts, reason=reason.strip())),
    )
    MembershipPaidVisitRelease.objects.create(
        intent=intent, request_key=key, kind="stopped", reason=reason.strip(), actor=actor
    )
    FinancialLineAdjustment.objects.create(
        request_key=facts["adjustment_key"],
        line_id=facts["line"],
        reason="membership_uncollected",
        net=-amount(facts["uncollected"]),
        actor=actor,
    )
    resolve_notices(intent, actor)
    AuditEvent.objects.create(
        actor=actor,
        action="membership.paid_visit_cancelled_release",
        record_type="membership",
        record_id=str(intent.purchase_id),
        changes=dict(
            intent=str(intent.pk),
            cancellation=facts["cancellation"],
            uncollected=facts["uncollected"],
            returned=facts["returned"],
            retained=facts["retained"],
            reason=reason.strip(),
        ),
    )
    return frozen


def controls(*, actor, pending):
    if not pending or not available() or not actor.is_superuser:
        return None
    intent = pending["intent"]
    saved = decision(intent.pk)
    if saved:
        return dict(saved=saved, facts=saved.facts, record=saved.cancellation)
    if pending["stopped"]:
        return None
    record = intent.purchase.cancellations.first()
    if not record:
        return None
    from .membership_cancellations import plan_paid
    from .payments.invoices import received

    sale = intent.purchase.installments.first().invoice.sale
    basics = dict(
        received=str(
            sum(
                (op.amount for op in sale.operations.filter(kind="receipt", state="succeeded")),
                ZERO,
            )
        ),
        returned=str(
            sum(
                (
                    op.amount
                    for op in sale.operations.filter(state="succeeded").exclude(kind="receipt")
                ),
                ZERO,
            )
        ),
        retained=str(received(sale)),
        uncollected=intent.offer["paid_visit"]["applied"],
        refund_due=str(
            sum((max(ZERO, p.amount - plan_paid(p)) for p in record.refund_plans.all()), ZERO)
        ),
    )
    try:
        facts = review(actor=actor, intent=intent)
    except (ValidationError, PermissionDenied) as exc:
        return dict(
            record=record,
            facts=basics,
            error=" ".join(exc.messages)
            if isinstance(exc, ValidationError)
            else "Owner review is required.",
        )
    return dict(record=record, facts=facts, reviewed=facts["fingerprint"], key=uuid.uuid4())
