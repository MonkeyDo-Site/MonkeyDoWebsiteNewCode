"""Owner cancellation and refund authority backed by actual original receipts."""

import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .availability import NEW_YORK
from .membership_calendar import boundary
from .membership_calendar_changes import cycle_on, cycles_for, root_for
from .membership_payments import member_record
from .membership_records import (
    MembershipCancellation,
    MembershipRefundAttempt,
    MembershipRefundPlan,
)
from .membership_reservations import lock_customer
from .membership_sales import authorize, today
from .models import AuditEvent, FinancialLineAdjustment, PaymentEvent, PaymentOperation
from .payments.amounts import COMPONENTS, ZERO, amount
from .payments.ledger import RESERVED, fingerprint, lock_request, used_components, writes_allowed
from .permissions import require_actor
from .pricing import money


def owner(actor):
    authorize(actor, collect=True)
    require_actor(actor, "core.review_payment", owner=True)


def stop_date(member, timing, on):
    root = root_for(member)
    if on > root.ends_on:
        raise ValidationError(
            "This membership term already ended. Use an owner payment correction instead."
        )
    if timing == "immediate":
        return on
    if timing != "end_cycle":
        raise ValidationError("Choose immediate or end-of-current-cycle cancellation.")
    if on < root.starts_on:
        return root.starts_on
    cycle = cycle_on(member, on)
    if cycle is None:
        raise ValidationError("Review the current membership calendar before cancellation.")
    return cycle.ends_on + timedelta(days=1)


def commitment_end(member):
    root = root_for(member)
    origin = getattr(member, "origin", None)
    if origin and origin.operation == "renewal" and origin.minimum_months == 1:
        return root.starts_on
    return boundary(root.starts_on, min(3, root.months))[1]


def plan_paid(plan):
    return sum(
        (
            op.amount
            for op in PaymentOperation.objects.filter(
                membership_refund_attempt__plan=plan, state="succeeded"
            )
        ),
        ZERO,
    )


def plan_pending(plan):
    return plan.attempts.filter(
        operation__state__in=["ready", "sending", "unknown", "action"]
    ).exists()


def remaining_allocation(plan):
    used = used_components(
        attempt.operation
        for attempt in plan.attempts.select_related("operation").filter(
            operation__state="succeeded"
        )
    )
    return [
        {
            "line": row["line"],
            **{
                key: str(max(ZERO, amount(row[key]) - used.get(row["line"], {}).get(key, ZERO)))
                for key in COMPONENTS
            },
        }
        for row in plan.allocation
    ]


def held_components(original, *, exclude_plan=None):
    result = {}
    for plan in original.membership_refund_plans.exclude(pk=exclude_plan).prefetch_related(
        "attempts__operation"
    ):
        consumed = used_components(
            attempt.operation
            for attempt in plan.attempts.all()
            if attempt.operation.state in RESERVED
        )
        for row in plan.allocation:
            line = str(row["line"])
            target = result.setdefault(line, {key: ZERO for key in COMPONENTS})
            for key in COMPONENTS:
                target[key] += max(ZERO, amount(row[key]) - consumed.get(line, {}).get(key, ZERO))
    return result


def protect_refund(original, allocation, *, plan_id=None):
    """Keep money promised by a cancellation from being returned twice elsewhere."""
    if plan_id is not None:
        try:
            plan = MembershipRefundPlan.objects.get(pk=plan_id, original=original)
        except (MembershipRefundPlan.DoesNotExist, ValueError, TypeError):
            raise ValidationError(
                "Use the approved refund for this original membership receipt."
            ) from None
        if plan_pending(plan) or plan_paid(plan) >= plan.amount:
            raise ValidationError("Check the existing refund outcome before another attempt.")
        available = {row["line"]: row for row in remaining_allocation(plan)}
        if any(
            row["line"] not in available
            or any(amount(row[key]) > amount(available[row["line"]][key]) for key in COMPONENTS)
            for row in allocation
        ):
            raise ValidationError("Use the remaining original-source membership refund allocation.")
    used = used_components(original.adjustments.filter(state__in=RESERVED))
    held = held_components(original, exclude_plan=plan_id)
    limits = {row["line"]: row for row in original.allocation}
    for row in allocation:
        line = row["line"]
        for key in COMPONENTS:
            if amount(row[key]) + used.get(line, {}).get(key, ZERO) + held.get(line, {}).get(
                key, ZERO
            ) > amount(limits.get(line, {}).get(key, ZERO)):
                raise ValidationError(
                    "These funds are already returned, pending or reserved for the membership cancellation."
                )


def affected(member, stopped_on):
    start = timezone.make_aware(datetime.combine(stopped_on, time.min), NEW_YORK)
    return (
        member.benefit_assignments.filter(
            current__status="reserved",
            booking__attendance="",
            booking__session__starts_at__gte=start,
        )
        .values("booking_id")
        .distinct()
    )


def unrecorded_provider_return(original):
    """A verified external return is money already moved, never a reason to POST again."""
    observations = list(
        original.observations.filter(provider_status__in=["external_credit", "voided", "returned"])
    )
    recorded = list(original.adjustments.filter(state="succeeded"))
    if not observations:
        return original.events.filter(code="external_correction_review").exists() and (
            not hasattr(original, "followup") or original.followup.resolved_at is None
        )
    for observation in observations:
        if observation.provider_status == "external_credit":
            covered = any(
                op.kind == "refund"
                and op.provider_reference == observation.provider_reference
                and op.amount == observation.amount
                for op in recorded
            )
        else:
            covered = sum((op.amount for op in recorded), ZERO) >= observation.amount
        if not covered:
            return True
    return False


def review(*, actor, member_id, timing="end_cycle", refund_amount=None):
    owner(actor)
    member = member_record(member_id)
    if member.cancellations.exists():
        raise ValidationError(
            "This membership already has a cancellation recorded. Review its refund and history below."
        )
    on = today()
    stop = stop_date(member, timing, on)
    installments = list(member.installments.select_related("cycle", "invoice__sale"))
    if any(
        item.invoice.sale.credit_applications.exists()
        for item in installments
        if hasattr(item, "invoice")
    ):
        raise ValidationError(
            "This membership includes applied customer credit. Review its credit return before cancelling. No cancellation or refund has been recorded."
        )
    operations = list(
        PaymentOperation.objects.filter(sale__membership_invoice__installment__purchase=member)
        .select_related("sale", "method")
        .order_by("requested_at", "pk")
    )
    if any(
        op.state in {"sending", "unknown", "action"}
        or (op.kind != "receipt" and op.state == "ready")
        for op in operations
    ):
        raise ValidationError(
            "Check the existing payment or refund outcome before cancelling. No cancellation or new refund has been recorded."
        )
    if any(
        unrecorded_provider_return(op)
        for op in operations
        if op.kind == "receipt" and op.tender == "card"
    ):
        raise ValidationError(
            "Banquest has reported a return that still needs recording. Reconcile the existing payment before cancelling or requesting another refund."
        )
    sources, paid, refunded, fees, suggestion = [], ZERO, ZERO, ZERO, ZERO
    by_sale = {item.invoice.sale_id: item for item in installments if hasattr(item, "invoice")}
    root = root_for(member)
    for op in reversed(operations):
        if op.state != "succeeded":
            continue
        if op.kind != "receipt":
            refunded += op.amount
            continue
        paid += op.amount
        used = used_components(op.adjustments.filter(state__in=RESERVED))
        held = held_components(op)
        allocation = []
        for row in op.allocation:
            if amount(row["item_tax"]) or amount(row["fee_tax"]):
                raise ValidationError(
                    "Historical membership tax needs owner correction review before cancellation refunds."
                )
            fees += amount(row["fee"]) - used.get(row["line"], {}).get("fee", ZERO)
            net = max(
                ZERO,
                amount(row["net"])
                - used.get(row["line"], {}).get("net", ZERO)
                - held.get(row["line"], {}).get("net", ZERO),
            )
            if net:
                allocation.append(
                    dict(
                        line=row["line"], net=str(net), fee="0.00", item_tax="0.00", fee_tax="0.00"
                    )
                )
        available = sum((amount(row["net"]) for row in allocation), ZERO)
        if not available:
            continue
        item = by_sale[op.sale_id]
        cycles = cycles_for(member) if root.billing == "prepaid" else [item.cycle]
        unused = sum(
            (
                Decimal(max(0, (cycle.ends_on - max(stop, cycle.starts_on)).days + 1))
                / Decimal((cycle.ends_on - cycle.starts_on).days + 1)
                for cycle in cycles
            ),
            ZERO,
        ) / len(cycles)
        suggestion += available * unused
        sources.append(
            dict(
                original=str(op.pk),
                installment=item.pk,
                number=item.number,
                tender=op.tender,
                last_four=op.method.last_four if op.method else "",
                available=str(available),
                allocation=allocation,
            )
        )
    maximum = sum((amount(source["available"]) for source in sources), ZERO)
    suggested = min(maximum, money(suggestion))
    requested = suggested if refund_amount is None else amount(refund_amount)
    if requested < ZERO or requested > maximum:
        raise ValidationError(
            "The refund cannot exceed actual available membership funds. Original processing fees are retained."
        )
    plans, remaining = [], requested
    for source in sources:
        chosen = min(remaining, amount(source["available"]))
        if not chosen:
            continue
        left, allocation = chosen, []
        for row in source["allocation"]:
            value = min(left, amount(row["net"]))
            if value:
                allocation.append(row | {"net": str(value)})
                left -= value
        plans.append(source | {"amount": str(chosen), "allocation": allocation})
        remaining -= chosen
    data = dict(
        membership=member.pk,
        customer_revision=member.customer.revision,
        billing_revision=member.billing_state.revision,
        on=on.isoformat(),
        timing=timing,
        stopped_on=stop.isoformat(),
        requires_early_override=member.purpose != "complimentary" and stop < commitment_end(member),
        money_received=str(paid),
        money_refunded=str(refunded),
        original_fees=str(fees),
        maximum_refund=str(maximum),
        suggested_refund=str(suggested),
        refund_amount=str(requested),
        sources=sources,
        plans=plans,
        operations=[
            dict(id=str(op.pk), state=op.state, kind=op.kind, amount=str(op.amount))
            for op in operations
        ],
        affected_bookings=list(affected(member, stop).order_by("booking_id")[:20]),
        affected_booking_count=affected(member, stop).count(),
        installments=[
            dict(
                number=item.number,
                due_on=item.due_on.isoformat(),
                starts_on=item.cycle.starts_on.isoformat(),
                ends_on=item.cycle.ends_on.isoformat(),
                cancelled=item.cycle.starts_on >= stop,
                quote=item.quote,
            )
            for item in installments
        ],
    )
    return data | {"fingerprint": fingerprint(data)}


@transaction.atomic
def cancel(
    *,
    actor,
    member_id,
    timing,
    refund_amount,
    reviewed,
    request_key,
    reason,
    early_override=False,
    send_confirmation=None,
    refund_now=False,
    manual_refunds_confirmed=False,
):
    owner(actor)
    writes_allowed()
    key = lock_request(request_key)
    identity = dict(
        membership=member_id,
        timing=timing,
        refund_amount=str(amount(refund_amount)),
        reviewed=reviewed,
        reason=reason,
        early_override=early_override,
        send_confirmation=send_confirmation,
        refund_now=refund_now,
        manual_refunds_confirmed=manual_refunds_confirmed,
    )
    prior = MembershipCancellation.objects.filter(pk=key).first()
    if prior:
        if prior.actor_id != actor.pk or prior.fingerprint != fingerprint(identity):
            raise ValidationError("This cancellation key already identifies another action.")
        return prior
    if any(
        type(value) is not bool
        for value in (early_override, send_confirmation, refund_now, manual_refunds_confirmed)
    ):
        raise ValidationError("Review the cancellation, refund and email choices.")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
        raise ValidationError("Record a reason for this membership cancellation.")
    member = member_record(member_id)
    lock_customer(member.customer_id)
    member.billing_state = member.billing_state.__class__.objects.select_for_update().get(
        purchase=member
    )
    current = review(actor=actor, member_id=member_id, timing=timing, refund_amount=refund_amount)
    if current["fingerprint"] != reviewed:
        raise ValidationError(
            "The membership, payment or cancellation review changed. Review it again."
        )
    if current["requires_early_override"] and early_override is not True:
        raise ValidationError(
            "The owner must explicitly approve cancellation during the initial commitment."
        )
    if send_confirmation and not member.customer.email:
        raise ValidationError("Add a customer email or choose No before cancelling.")
    if (
        refund_now
        and any(plan["tender"] != "card" for plan in current["plans"])
        and manual_refunds_confirmed is not True
    ):
        raise ValidationError(
            "Confirm the non-card refund was actually returned, or record it as due."
        )
    record = MembershipCancellation.objects.create(
        id=key,
        purchase=member,
        stopped_on=date.fromisoformat(current["stopped_on"]),
        timing=timing,
        early_override=early_override,
        reason=reason.strip(),
        refund_amount=amount(refund_amount),
        fingerprint=fingerprint(identity),
        snapshot=current,
        send_confirmation=send_confirmation,
        actor=actor,
    )
    for values in current["plans"]:
        MembershipRefundPlan.objects.create(
            id=uuid.uuid5(key, values["original"]),
            cancellation=record,
            original_id=values["original"],
            allocation=values["allocation"],
            amount=values["amount"],
        )
    for op in PaymentOperation.objects.select_for_update(of=("self",)).filter(
        sale__membership_invoice__installment__purchase=member, kind="receipt", state="ready"
    ):
        op.state = "cancelled"
        op.result_code = "membership_cancelled"
        op.completed_at = timezone.now()
        op.save(update_fields=["state", "result_code", "completed_at"])
        PaymentEvent.objects.create(
            operation=op,
            state="cancelled",
            source="staff",
            code="membership_cancelled",
            actor=actor,
        )
    billing = member.billing_state
    billing.stopped_on = record.stopped_on
    billing.revision += 1
    billing.save(update_fields=["stopped_on", "revision"])
    from .communications.models import MessageDelivery, MessageEvent

    for message in MessageDelivery.objects.select_for_update().filter(
        membership=member,
        kind__in=["membership_confirmation", "membership_renewal", "membership_addition"],
        state="queued",
    ):
        message.state = "cancelled"
        message.code = "membership_cancelled"
        message.save(update_fields=["state", "code"])
        MessageEvent.objects.create(
            delivery=message, state="cancelled", code="membership_cancelled", actor=actor
        )
    if refund_now:
        for plan in record.refund_plans.all():
            request_refund(
                actor=actor,
                plan_id=plan.pk,
                request_key=uuid.uuid5(key, f"refund:{plan.pk}"),
                confirmed=True,
                manual_returned=manual_refunds_confirmed,
            )
    from .membership_paid_visit_cancellation import cancellation_updated

    cancellation_updated(record)
    queue_cancellation(record)
    AuditEvent.objects.create(
        actor=actor,
        action="membership.cancelled",
        record_type="membership",
        record_id=str(member.pk),
        changes={
            "cancellation": str(key),
            "stopped_on": current["stopped_on"],
            "refund_due": str(record.refund_amount),
            "early_override": early_override,
            "reason": reason.strip(),
        },
    )
    return record


@transaction.atomic
def request_refund(
    *,
    actor,
    plan_id,
    request_key,
    confirmed=False,
    manual_returned=False,
    received_on=None,
    refund_amount=None,
    completed_provider_reference="",
):
    owner(actor)
    writes_allowed()
    if type(manual_returned) is not bool:
        raise ValidationError("Confirm whether the manual refund was actually returned.")
    key = lock_request(request_key)
    plan = MembershipRefundPlan.objects.select_related("cancellation__purchase", "original").get(
        pk=plan_id
    )
    lock_customer(plan.cancellation.purchase.customer_id)
    identity = fingerprint(
        dict(
            plan=str(plan.pk),
            manual_returned=manual_returned,
            received_on=received_on.isoformat() if received_on else None,
            refund_amount=str(amount(refund_amount)) if refund_amount is not None else None,
            completed_provider_reference=str(completed_provider_reference),
        )
    )
    prior = MembershipRefundAttempt.objects.filter(pk=key).first()
    if prior:
        if prior.plan_id != plan.pk or prior.actor_id != actor.pk or prior.fingerprint != identity:
            raise ValidationError("This refund key already identifies another action.")
        return prior
    if confirmed is not True or (plan.original.tender != "card" and manual_returned is not True):
        raise ValidationError(
            "Explicitly request this card refund or confirm the non-card refund was actually returned."
        )
    if plan_pending(plan) or plan_paid(plan) >= plan.amount:
        raise ValidationError("Check the existing refund outcome before another attempt.")
    if completed_provider_reference and plan.original.tender != "card":
        raise ValidationError("A Banquest refund reference applies only to a card receipt.")
    if not completed_provider_reference and unrecorded_provider_return(plan.original):
        raise ValidationError(
            "Banquest has already reported a return. Record the completed refund using its transaction reference before requesting another return."
        )
    available = remaining_allocation(plan)
    balance = sum((amount(row["net"]) for row in available), ZERO)
    requested = balance if refund_amount is None else amount(refund_amount)
    if not ZERO < requested <= balance:
        raise ValidationError(
            "The refund must be positive and cannot exceed the remaining amount due."
        )
    if (
        plan.original.tender != "card"
        and received_on
        and plan.original.manual_received_on
        and received_on < plan.original.manual_received_on
    ):
        raise ValidationError("The refund date cannot precede the original receipt date.")
    left, allocation = requested, []
    for row in available:
        value = min(left, amount(row["net"]))
        if value:
            allocation.append(row | {"net": str(value)})
            left -= value
    from .payments.ledger import record_manual, request_operation

    if completed_provider_reference:
        from .payments.corrections import record_correction

        operation = record_correction(
            actor=actor,
            original_id=plan.original_id,
            request_key=uuid.uuid5(key, "payment"),
            kind="refund",
            allocation=allocation,
            provider_reference=completed_provider_reference,
            confirmed=True,
            membership_refund_plan_id=plan.pk,
        )
    else:
        operation = request_operation(
            actor=actor,
            sale_id=plan.original.sale_id,
            request_key=uuid.uuid5(key, "payment"),
            tender=plan.original.tender,
            kind="refund",
            original_id=plan.original_id,
            method_id=plan.original.method_id,
            allocation=allocation,
            purpose="correction",
            received_on=received_on,
            membership_refund_plan_id=plan.pk,
        )
    attempt = MembershipRefundAttempt.objects.create(
        id=key, plan=plan, operation=operation, fingerprint=identity, actor=actor
    )
    if completed_provider_reference:
        refund_updated(operation)
    elif operation.tender == "card":
        from .payments.jobs import enqueue

        enqueue(kind="payment_dispatch", reference=operation.pk, key=f"dispatch:{operation.pk}")
    else:
        record_manual(actor=actor, operation_id=operation.pk, received=True)
    return attempt


def refund_updated(operation):
    """Reduce the paid membership obligation only with a real completed return."""
    if operation.kind != "refund" or operation.state != "succeeded":
        return
    attempt = (
        MembershipRefundAttempt.objects.select_related("plan__cancellation")
        .filter(operation=operation)
        .first()
    )
    if not attempt:
        return
    for row in operation.allocation:
        FinancialLineAdjustment.objects.get_or_create(
            request_key=uuid.uuid5(operation.pk, "membership-refund"),
            line_id=row["line"],
            defaults=dict(
                reason="membership_refund",
                net=-amount(row["net"]),
                fee=ZERO,
                item_tax=ZERO,
                fee_tax=ZERO,
                actor=attempt.actor,
            ),
        )
    if not unrecorded_provider_return(attempt.plan.original):
        from .models import OwnerNotice, PaymentFollowup

        PaymentFollowup.objects.filter(
            operation=attempt.plan.original, plan="owner_review", resolved_at__isnull=True
        ).update(resolved_at=timezone.now())
        OwnerNotice.objects.filter(
            details__kind="payment_correction",
            details__operation_id=str(attempt.plan.original_id),
            reviewed_at__isnull=True,
        ).update(reviewed_at=timezone.now(), reviewed_by=attempt.actor)
    if settings.BOOKING_EMAIL_ENABLED:
        queue_cancellation(attempt.plan.cancellation, initial=False)


@transaction.atomic
def queue_cancellation(record, *, initial=True):
    if not record.send_confirmation:
        return
    from .communications.models import MessageDelivery, MessageEvent
    from .communications.services import enqueue
    from .date_display import display_date

    member = record.purchase
    queued = list(
        MessageDelivery.objects.select_for_update().filter(
            membership=member, kind="membership_cancellation", state="queued"
        )
    )
    if not initial and not queued:
        return
    if not member.customer.email:
        return queued[0] if queued else None
    root = root_for(member)
    end = (
        record.stopped_on if record.timing == "immediate" else record.stopped_on - timedelta(days=1)
    )
    text = [
        f"Dear Family {member.customer.last_name},",
        "",
        f"Your {root.places} {root.get_kind_display()} Membership{'s' if root.places != 1 else ''} {'ended' if record.timing == 'immediate' or end < today() else 'will end'} on {display_date(end, 'F j, Y')}."
        if root.starts_on <= date.fromisoformat(record.snapshot["on"])
        else f"Your {root.get_kind_display()} Membership has been cancelled before its start date.",
    ]
    from .membership_reservations import payment_current

    if root.starts_on <= today() < record.stopped_on and payment_current(member):
        text += [
            "You may continue using your remaining eligible membership benefits through that date."
        ]
    returned = sum((plan_paid(plan) for plan in record.refund_plans.all()), ZERO)
    if record.refund_amount:
        if returned:
            text += [f"A refund of ${returned:.2f} has been processed."]
        if returned < record.refund_amount:
            text += [
                f"A refund of ${record.refund_amount - returned:.2f} is due. It has not yet been confirmed as returned."
            ]
    text += [
        "",
        "Thank you for making Monkey Do part of your family's adventures. We welcome you at any time!",
        "",
        "The Monkey Do team",
    ]
    body = "\n".join(text)
    for message in queued:
        if message.text_body == body and message.recipient == member.customer.email:
            return message
    for message in queued:
        message.state = "cancelled"
        message.code = "membership_refund_updated"
        message.save(update_fields=["state", "code"])
        MessageEvent.objects.create(
            delivery=message, state="cancelled", code="membership_refund_updated"
        )
    return enqueue(
        key=f"membership-cancellation:{record.pk}:{member.customer.revision}:{fingerprint(body)[:16]}",
        kind="membership_cancellation",
        recipient=member.customer.email,
        subject="Your Monkey Do membership cancellation",
        text=body,
        customer=member.customer,
        membership=member,
        actor=record.actor,
    )


def notices():
    from django.db.models import DecimalField, Exists, F, OuterRef, Q, Sum, Value
    from django.db.models.functions import Coalesce

    from .membership_records import MembershipBenefitAssignment

    currency = DecimalField(max_digits=14, decimal_places=2)
    plans = (
        MembershipRefundPlan.objects.annotate(
            returned=Coalesce(
                Sum(
                    "attempts__operation__amount", filter=Q(attempts__operation__state="succeeded")
                ),
                Value(ZERO),
                output_field=currency,
            )
        )
        .filter(returned__lt=F("amount"))
        .select_related(
            "cancellation__purchase__customer",
            "cancellation__purchase__membership",
            "original__method",
        )
        .order_by("cancellation__created_at", "pk")
    )
    refunds = list(plans[:20])
    for plan in refunds:
        plan.remaining = plan.amount - plan.returned
        plan.pending = plan_pending(plan)
    affected_rows = MembershipBenefitAssignment.objects.filter(
        purchase_id=OuterRef("purchase_id"),
        current__status="reserved",
        booking__attendance="",
        booking__session__starts_at__date__gte=OuterRef("stopped_on"),
    )
    cancellations = list(
        MembershipCancellation.objects.filter(Exists(affected_rows))
        .select_related("purchase__customer", "purchase__membership")
        .order_by("created_at")[:20]
    )
    for record in cancellations:
        record.affected_count = affected(record.purchase, record.stopped_on).count()
    return dict(refunds=refunds, affected=cancellations)
