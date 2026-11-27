"""One reviewed first installment, with actual receipts and one card remainder."""

import uuid
from datetime import date

from django.core.exceptions import ValidationError

from .payments.amounts import ZERO, amount
from .payments.ledger import fingerprint
from .payments.receipts import receipt_date, sender
from .pricing import money

MANUAL = {"cash": "Cash", "check": "Check", "zelle": "Zelle", "gift_card": "Gift card"}


def review(*, principal, credit, split, policy, sender_name="", received_on=None, recorded=None):
    if not isinstance(split, dict) or set(split) - set(MANUAL):
        raise ValidationError(
            "Enter supported first-payment amounts for cash, check, Zelle or a physical gift card."
        )
    values = {kind: amount(split.get(kind, ZERO)) for kind in MANUAL}
    remaining = principal - credit - (amount(recorded["amount"]) if recorded else ZERO)
    if remaining < ZERO:
        raise ValidationError("Recorded Zelle and credit exceed the initial membership principal.")
    manual = sum(values.values(), ZERO)
    if manual > remaining:
        raise ValidationError(
            f"The received amounts exceed the ${remaining:.2f} membership balance after credit. Adjust the amounts applied."
        )
    net = remaining - manual
    fee = money(net * policy.card_fee_rate)
    parts = []
    for kind, value in values.items():
        if value:
            part = dict(
                tender=kind,
                amount=str(value),
                net=str(value),
                fee="0.00",
                received_on=receipt_date(received_on if kind == "zelle" else None).isoformat(),
            )
            if kind == "zelle":
                part["sender"] = sender(sender_name, required=True)
            parts.append(part)
    if net + fee:
        parts.append(dict(tender="card", net=str(net), fee=str(fee), amount=str(net + fee)))
    result = dict(
        version="membership-first-split-v1",
        parts=parts,
        manual_total=str(manual),
        card_total=str(net + fee),
        card_net=str(net),
        credit_amount=str(credit),
    )
    if recorded:
        result["recorded_zelle"] = recorded
    return result


def verify(plan, *, verified_received=False, gift_card_verified=False, zelle_verified=False):
    kinds = {part["tender"] for part in plan["parts"]}
    if kinds & {"cash", "check"} and verified_received is not True:
        raise ValidationError(
            "Confirm that the entered membership cash/check amounts were actually received."
        )
    if "gift_card" in kinds and gift_card_verified is not True:
        raise ValidationError(
            "Present and verify the physical gift card for its membership amount."
        )
    if "zelle" in kinds and zelle_verified is not True:
        raise ValidationError(
            "Verify the membership Zelle transfer in the bank account. These funds must not already be recorded elsewhere."
        )


def apply_credit(*, actor, member, sale, plan):
    """Purchase holds the customer lock; the accepted invoice already has its exact fee."""
    from .customer_credit import available_issues
    from .customer_credit_records import CustomerCreditAllocation, CustomerCreditApplication
    from .membership_sales import authorize
    from .models import AuditEvent

    authorize(actor, collect=True)
    if (
        member.actor_id != actor.pk
        or sale.membership_invoice.installment.purchase_id != member.pk
        or amount(plan["amount"])
        != amount(sale.membership_invoice.installment.quote["initial_split"]["credit_amount"])
    ):
        raise ValidationError("Use the credit accepted for this first split payment.")

    sources = available_issues(member.customer_id)
    if plan["sources"] != [
        dict(id=str(source.pk), remaining=str(source.remaining)) for source in sources
    ]:
        raise ValidationError("The credit sources changed. Review the split purchase again.")
    details = dict(membership=member.pk, installment=1, first_split=True, **plan)
    record = CustomerCreditApplication.objects.create(
        id=uuid.uuid5(member.request_key, "initial-customer-credit"),
        customer_id=member.customer_id,
        sale=sale,
        actor=actor,
        amount=amount(plan["amount"]),
        details=details,
        fingerprint=fingerprint(details),
    )
    line = sale.lines.get()
    left = record.amount
    for source in sources:
        used = min(left, source.remaining)
        if used:
            CustomerCreditAllocation.objects.create(
                application=record,
                issue=source,
                amount=used,
                allocation=[
                    dict(
                        line=str(line.pk),
                        net=str(used),
                        fee="0.00",
                        item_tax="0.00",
                        fee_tax="0.00",
                    )
                ],
            )
            left -= used
        if not left:
            break
    if left:
        raise ValidationError("The credit balance changed; no purchase was recorded.")
    AuditEvent.objects.create(
        actor=actor,
        action="customer.credit_applied",
        record_type="membership",
        record_id=str(member.pk),
        changes=dict(application=str(record.pk), amount=str(record.amount), first_split=True),
    )
    return record


def record(*, actor, member, invoice, plan, method):
    from .membership_sales import authorize
    from .payments.jobs import enqueue
    from .payments.ledger import record_manual, request_operation

    authorize(actor, collect=True)
    if (
        member.actor_id != actor.pk
        or invoice.installment.purchase_id != member.pk
        or plan != invoice.installment.quote.get("initial_split")
    ):
        raise ValidationError("Use this membership's accepted first-payment split.")

    line = invoice.sale.lines.get()
    for part in plan["parts"]:
        card = part["tender"] == "card"
        if card and method is None:
            raise ValidationError("Choose the accepted card for the membership remainder.")
        operation = request_operation(
            actor=actor,
            sale_id=invoice.sale_id,
            request_key=uuid.uuid5(
                member.request_key, "first-payment" if card else "first-payment:" + part["tender"]
            ),
            tender=part["tender"],
            allocation=[
                dict(
                    line=str(line.pk),
                    net=part["net"],
                    fee=part["fee"],
                    item_tax="0.00",
                    fee_tax="0.00",
                )
            ],
            method_id=method.pk if card else None,
            purpose="member_purchase",
            received_on=date.fromisoformat(part["received_on"]) if not card else None,
        )
        if card:
            enqueue(kind="payment_dispatch", reference=operation.pk, key=f"dispatch:{operation.pk}")
        else:
            record_manual(actor=actor, operation_id=operation.pk, received=True)
