"""Original received visit tenders survive a conditional membership-card outcome."""

import uuid
from datetime import date
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError

from .membership_records import MembershipArrivalReceipt, MembershipArrivalReceiptApplication
from .payments.amounts import COMPONENTS, ZERO, allocate, amount

VERSION = "pending-visit-receipts-v1"


def manual_parts(plan):
    return {
        part["tender"]: amount(part["amount"])
        for part in plan
        if part["tender"] not in {"card", "credit"}
        and not part.get("advance")
        and amount(part["amount"])
    }


def rows(intent):
    from .membership_schema import available

    if not available("core_membershiparrivalreceipt"):
        return []
    receipts = list(intent.visit_receipts.order_by("tender"))
    can_return = available("core_membershiparrivalreceiptreturn")
    for source in receipts:
        source.return_events = (
            list(source.returns.order_by("created_at", "pk")) if can_return else []
        )
        source.returned_amount = sum((r.amount for r in source.return_events), ZERO)
        source.net_amount = source.amount - source.returned_amount
        source.available_amount = source.net_amount - (
            source.application.operation.amount if hasattr(source, "application") else ZERO
        )
    return receipts


def record(intent):
    """Called inside the original accepted confirmation transaction only."""
    if intent.facts.get("visit_receipt_version") != VERSION:
        return
    review, data = intent.facts["review"]["arrival"], intent.facts["data"]
    for tender, value in manual_parts(review["plan"]).items():
        if tender in {"zelle", "gift_card"} and data.get(tender + "_verified") is not True:
            raise ValidationError("Verify the actual visit funds before recording them.")
        MembershipArrivalReceipt.objects.create(
            id=uuid.uuid5(intent.pk, "visit-receipt:" + tender),
            intent=intent,
            tender=tender,
            amount=value,
            actor=intent.actor,
            received_on=date.fromisoformat(review["received_on"])
            if tender == "zelle"
            else intent.accepted_at.astimezone(ZoneInfo("America/New_York")).date(),
            sender=review["zelle_sender"] if tender == "zelle" else "",
        )


def held(intent):
    return {r.tender: str(r.available_amount) for r in rows(intent) if r.available_amount > ZERO}


def snapshot(intent):
    return [
        {
            "receipt": str(r.pk),
            "tender": r.tender,
            "available": str(r.available_amount),
            "returned": str(r.returned_amount),
            "returns": [str(event.pk) for event in r.return_events],
        }
        for r in rows(intent)
    ]


def validate(intent, plan, *, owner_review=False):
    if intent is None or intent.facts.get("visit_receipt_version") != VERSION:
        return
    receipts = rows(intent)
    original = manual_parts(intent.facts["review"]["arrival"]["plan"])
    expected = {r.tender: r.available_amount for r in receipts if r.available_amount > ZERO}
    actual = manual_parts(plan)
    valid = (
        all(actual.get(k, ZERO) >= value for k, value in expected.items())
        if owner_review
        else actual == expected
        and expected == original
        and not any(r.returned_amount for r in receipts)
    )
    if (
        {r.tender: r.amount for r in receipts} != original
        or not valid
        or any(hasattr(r, "application") for r in receipts)
    ):
        raise ValidationError(
            "Previously received visit funds must be included. Record an actual return before reducing these amounts."
            if owner_review
            else "Previously received visit funds need owner review before changing this arrival. Keep their original receipts; do not record them again."
        )


def proofs_ready(data, plan, intent=None):
    stored = held(intent) if intent else {}
    actual = manual_parts(plan)
    return all(
        actual.get(kind, ZERO) <= amount(stored.get(kind, ZERO))
        or data.get(kind + "_verified") is True
        for kind in ("gift_card", "zelle")
    )


def apply(*, intent, actor, sale, part, key, allocation):
    """Apply the full held source first; return only truly new tender allocation."""
    if intent is None or intent.facts.get("visit_receipt_version") != VERSION:
        return allocation
    from .payments.ledger import record_manual, request_operation

    receipt = next((r for r in rows(intent) if r.tender == part["tender"]), None)
    if receipt is None or not receipt.available_amount:
        return allocation
    if receipt.available_amount > amount(part["amount"]) or hasattr(receipt, "application"):
        raise ValidationError("Review the original visit receipt before applying it.")
    values = allocate(
        receipt.available_amount, [entry[k] for entry in allocation for k in COMPONENTS]
    )
    stored, remaining = [], []
    for position, entry in enumerate(allocation):
        used = {k: values[position * len(COMPONENTS) + i] for i, k in enumerate(COMPONENTS)}
        stored.append({"line": entry["line"], **{k: str(used[k]) for k in COMPONENTS}})
        remaining.append(
            {"line": entry["line"], **{k: str(amount(entry[k]) - used[k]) for k in COMPONENTS}}
        )
    operation = request_operation(
        actor=actor,
        sale_id=sale.pk,
        request_key=uuid.uuid5(key, "visit-receipt:" + str(receipt.pk)),
        tender=receipt.tender,
        allocation=stored,
        purpose="arrival",
        received_on=receipt.received_on,
    )
    MembershipArrivalReceiptApplication.objects.create(receipt=receipt, operation=operation)
    record_manual(actor=actor, operation_id=operation.pk, received=True)
    return remaining


def summary(intent):
    receipts = rows(intent)
    return {
        "receipts": receipts,
        "total": sum((r.net_amount for r in receipts), ZERO),
        "gross": sum((r.amount for r in receipts), ZERO),
        "returned": sum((r.returned_amount for r in receipts), ZERO),
    }
