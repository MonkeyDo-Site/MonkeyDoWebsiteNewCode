"""Original received visit tenders survive a conditional membership-card outcome."""

import uuid
from datetime import date
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError

from .membership_records import MembershipArrivalReceipt, MembershipArrivalReceiptApplication
from .payments.amounts import ZERO, amount

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
    return list(intent.visit_receipts.order_by("tender"))


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


def validate(intent, plan):
    if intent is None or intent.facts.get("visit_receipt_version") != VERSION:
        return
    receipts = rows(intent)
    expected = manual_parts(intent.facts["review"]["arrival"]["plan"])
    if (
        {r.tender: r.amount for r in receipts} != expected
        or manual_parts(plan) != expected
        or any(hasattr(r, "application") for r in receipts)
    ):
        raise ValidationError(
            "Previously received visit funds need owner review before changing this arrival. Keep their original receipts; do not record them again."
        )


def apply(*, intent, actor, sale, part, key, allocation):
    """Apply one already-received tender with its original date and source link."""
    if intent is None or intent.facts.get("visit_receipt_version") != VERSION:
        return False
    from .payments.ledger import record_manual, request_operation

    receipt = intent.visit_receipts.get(tender=part["tender"])
    if receipt.amount != amount(part["amount"]) or hasattr(receipt, "application"):
        raise ValidationError("Review the original visit receipt before applying it.")
    operation = request_operation(
        actor=actor,
        sale_id=sale.pk,
        request_key=uuid.uuid5(key, "visit-receipt:" + str(receipt.pk)),
        tender=receipt.tender,
        allocation=allocation,
        purpose="arrival",
        received_on=receipt.received_on,
    )
    MembershipArrivalReceiptApplication.objects.create(receipt=receipt, operation=operation)
    record_manual(actor=actor, operation_id=operation.pk, received=True)
    return True


def summary(intent):
    receipts = rows(intent)
    return {"receipts": receipts, "total": sum((r.amount for r in receipts), ZERO)}
