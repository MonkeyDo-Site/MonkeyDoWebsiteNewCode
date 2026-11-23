"""Verified advance receipts and manual refunds; allocations are not new cash."""

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from core.models import AuditEvent, Booking
from core.permissions import require_actor

from .amounts import COMPONENTS, ZERO, allocate, amount
from .ledger import enabled, lock_request, record_manual, request_operation, writes_allowed
from .models import ZelleApplication, ZelleReceipt, ZelleRefund
from .receipts import receipt_date, sender


def unallocated(receipt):
    return (
        receipt.amount
        - (receipt.applications.aggregate(n=Sum("amount"))["n"] or ZERO)
        - (receipt.refunds.aggregate(n=Sum("amount"))["n"] or ZERO)
    )


def facts(booking):
    receipts = list(booking.zelle_receipts.order_by("received_on", "created_at", "pk"))
    gross = sum((r.amount for r in receipts), ZERO)
    refunded = sum((r.amount for r in ZelleRefund.objects.filter(receipt__booking=booking)), ZERO)
    available = sum((unallocated(r) for r in receipts), ZERO)
    return {
        "receipts": receipts,
        "received": gross,
        "refunded": refunded,
        "available": available,
        "refund_due": available if booking.attendance else ZERO,
        "identity": [(str(r.pk), str(unallocated(r))) for r in receipts],
    }


@transaction.atomic
def record_receipt(
    *, actor, booking_id, request_key, value, received_on=None, sender_name="", verified=False
):
    enabled()
    writes_allowed()
    require_actor(actor, "core.collect_payment")
    require_actor(actor, "core.change_booking")
    key = lock_request(request_key)
    booking = Booking.objects.select_for_update().get(pk=booking_id)
    if booking.workflow != "integrated_v1" or booking.attendance:
        raise ValidationError(
            "Record advance Zelle on an upcoming integrated booking. Use remaining payment after arrival."
        )
    value = amount(value)
    day = receipt_date(received_on)
    name = sender(sender_name, required=True)
    if value <= ZERO or verified is not True:
        raise ValidationError(
            "Enter a positive amount and verify the receipt in the business bank account."
        )
    prior = ZelleReceipt.objects.filter(request_key=key).first()
    if prior:
        if (prior.booking_id, prior.amount, prior.received_on, prior.sender, prior.actor_id) != (
            booking.pk,
            value,
            day,
            name,
            actor.pk,
        ):
            raise ValidationError("This receipt request was already used for different details.")
        return prior
    receipt = ZelleReceipt.objects.create(
        request_key=key, booking=booking, amount=value, received_on=day, sender=name, actor=actor
    )
    AuditEvent.objects.create(
        actor=actor,
        action="payment.zelle_received",
        record_type="booking",
        record_id=str(booking.reference),
        changes={"receipt_id": str(receipt.pk), "amount": str(value), "received_on": str(day)},
    )
    return receipt


def plan_with_prepayment(policy, lines, method, split, available):
    from core.pricing import quote_lines

    from .checkout_pricing import tender_plan

    base = quote_lines(lines, policy, card_base=ZERO)
    applied = min(available, amount(base["total"]))
    if method == "zelle" and available < amount(base["total"]):
        raise ValidationError(
            f"Only ${available:.2f} has been recorded through Zelle. Record the verified receipt or another transfer first, or choose the card on file for the remaining balance."
        )
    if not applied:
        return (*tender_plan(policy, lines, method=method, split=split), ZERO)
    if method in {"card", "split"}:
        additional = dict(split or {}) if method == "split" else {}
        additional["zelle"] = str(amount(additional.get("zelle", ZERO)) + applied)
        quote, plan = tender_plan(policy, lines, method="split", split=additional)
        # A separate plan entry preserves the exact already-received portion.
        zelle_part = next(p for p in plan if p["tender"] == "zelle")
        if amount(zelle_part["amount"]) != applied:
            raise ValidationError(
                "Record the new Zelle receipt first, then review the remaining payment."
            )
        zelle_part["advance"] = True
    else:
        quote, plan = tender_plan(policy, lines, method=method)
        original = plan[0]
        flat = [part[k] for part in original["parts"] for k in COMPONENTS]
        allocation = allocate(applied, flat)
        prepaid_parts = [
            {k: allocation[i * len(COMPONENTS) + j] for j, k in enumerate(COMPONENTS)}
            for i in range(len(original["parts"]))
        ]
        remainder = [
            {k: part[k] - prepaid_parts[i][k] for k in COMPONENTS}
            for i, part in enumerate(original["parts"])
        ]
        plan = [
            {"tender": "zelle", "amount": str(applied), "parts": prepaid_parts, "advance": True}
        ]
        left = amount(quote["total"]) - applied
        if left:
            plan.append({"tender": method, "amount": str(left), "parts": remainder})
    return quote, plan, applied


def apply_receipts(*, actor, booking, sale, part, key):
    """Convert unapplied money into invoice allocations once, retaining bank dates."""
    remaining = amount(part["amount"])
    components = [{k: row[k] for k in COMPONENTS} for row in part["parts"]]
    lines = list(sale.lines.all())
    for receipt in booking.zelle_receipts.order_by("received_on", "created_at", "pk"):
        value = min(unallocated(receipt), remaining)
        if value <= ZERO:
            continue
        flat = [row[k] for row in components for k in COMPONENTS]
        values = allocate(value, flat)
        allocation = [
            {
                "line": str(line.pk),
                **{k: str(values[i * len(COMPONENTS) + j]) for j, k in enumerate(COMPONENTS)},
            }
            for i, line in enumerate(lines)
        ]
        op = request_operation(
            actor=actor,
            sale_id=sale.pk,
            request_key=uuid.uuid5(key, "advance:" + str(receipt.pk)),
            tender="zelle",
            allocation=allocation,
            purpose="arrival"
            if booking.attendance == "arrived"
            else "cancellation"
            if booking.attendance == "cancelled"
            else "no_show",
            received_on=receipt.received_on,
        )
        ZelleApplication.objects.create(receipt=receipt, operation=op, amount=value)
        record_manual(actor=actor, operation_id=op.pk, received=True)
        components = [
            {k: row[k] - Decimal(allocation[i][k]) for k in COMPONENTS}
            for i, row in enumerate(components)
        ]
        remaining -= value
    if remaining:
        raise ValidationError("The available Zelle amount changed. Review the balance again.")


@transaction.atomic
def complete_refund(
    *, actor, booking_id, request_key, reviewed_amount, completed_on=None, confirmed=False
):
    enabled()
    writes_allowed()
    require_actor(actor, "core.review_payment", owner=True)
    key = lock_request(request_key)
    booking = Booking.objects.select_for_update().get(pk=booking_id)
    day = receipt_date(completed_on)
    existing = list(ZelleRefund.objects.filter(request_key=key))
    if existing:
        if (
            existing[0].receipt.booking_id != booking.pk
            or existing[0].actor_id != actor.pk
            or not AuditEvent.objects.filter(
                action="payment.zelle_refund_completed",
                changes__request_key=str(key),
                changes__amount=str(amount(reviewed_amount)),
            ).exists()
        ):
            raise ValidationError("This refund request already identifies a different action.")
        return existing[0]
    due = facts(booking)["refund_due"]
    if not confirmed or not booking.attendance or due <= ZERO or due != amount(reviewed_amount):
        raise ValidationError(
            "Review the current refund due and confirm it has actually been returned through Zelle."
        )
    # One durable refund row per original receipt; deterministic keys prevent replay.
    result = None
    for receipt in booking.zelle_receipts.order_by("created_at", "pk"):
        value = unallocated(receipt)
        if value > ZERO:
            result = ZelleRefund.objects.create(
                receipt=receipt,
                request_key=key if result is None else uuid.uuid5(key, str(receipt.pk)),
                amount=value,
                completed_on=day,
                actor=actor,
            )
    AuditEvent.objects.create(
        actor=actor,
        action="payment.zelle_refund_completed",
        record_type="booking",
        record_id=str(booking.reference),
        changes={"amount": str(due), "completed_on": str(day), "request_key": str(key)},
    )
    from .checkout import resolve_if_settled

    resolve_if_settled(booking.pk)
    return result


def refund_notices():
    return [
        {"booking": b, "amount": facts(b)["refund_due"]}
        for b in Booking.objects.filter(zelle_receipts__isnull=False)
        .exclude(attendance="")
        .select_related("customer")
        .distinct()
        if facts(b)["refund_due"] > ZERO
    ]
