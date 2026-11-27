"""Apply an existing verified booking transfer once, retaining its original source."""

import uuid

from django.core.exceptions import ValidationError

from .models import Booking
from .payments.amounts import ZERO, amount
from .payments.zelle import facts, unallocated
from .permissions import require_actor


def applied(member):
    from django.db.models import Sum

    from .membership_schema import available

    if not available("core_membershipbankallocation"):
        return ZERO
    return member.bank_allocations.aggregate(value=Sum("amount"))["value"] or ZERO


def assigned_from_booking(booking):
    from django.db.models import Sum

    from .membership_records import MembershipBankAllocation
    from .membership_schema import available

    if not available("core_membershipbankallocation"):
        return ZERO
    return (
        MembershipBankAllocation.objects.filter(receipt__booking=booking).aggregate(
            value=Sum("amount")
        )["value"]
        or ZERO
    )


def review(*, actor, customer, booking_id, value, comped=False):
    value = amount(value)
    if not value:
        return None
    require_actor(actor, "core.collect_payment")
    require_actor(actor, "core.change_booking")
    booking = Booking.objects.filter(pk=booking_id, customer=customer).first()
    if (
        comped
        or booking is None
        or booking.workflow != "integrated_v1"
        or booking.attendance
        or booking.setup_pending
    ):
        raise ValidationError("Use this customer's upcoming booking to apply its recorded Zelle.")
    available = facts(booking)
    if value > available["available"]:
        raise ValidationError(
            "Recorded Zelle changed or is insufficient. Review its available balance."
        )
    left, sources = value, []
    for receipt in available["receipts"]:
        remaining = unallocated(receipt)
        taken = min(left, remaining)
        sources.append(
            dict(
                id=str(receipt.pk),
                remaining=str(remaining),
                amount=str(taken),
                received_on=receipt.received_on.isoformat(),
                sender=receipt.sender,
            )
        )
        left -= taken
    return dict(
        version="membership-booking-zelle-v1",
        booking=booking.pk,
        amount=str(value),
        sources=sources,
    )


def preview_facts(proposed, prepaid):
    if proposed is None:
        return prepaid
    plan = (proposed.offer.get("first_payment_plan") or {}).get("recorded_zelle")
    if not plan:
        return prepaid
    expected = [(row["id"], row["remaining"]) for row in plan["sources"]]
    if prepaid["identity"] != expected:
        raise ValidationError("The recorded Zelle sources changed. Review the combined payment.")
    return prepaid | dict(
        available=prepaid["available"] - amount(plan["amount"]),
        identity=[
            (row["id"], str(amount(row["remaining"]) - amount(row["amount"])))
            for row in plan["sources"]
        ],
    )


def apply(*, actor, member, invoice, plan, booking):
    from .membership_records import MembershipBankAllocation
    from .payments.ledger import record_manual, request_operation
    from .payments.models import ZelleApplication, ZelleReceipt

    if (
        booking is None
        or booking.pk != plan["booking"]
        or booking.customer_id != member.customer_id
        or member.actor_id != actor.pk
        or member.confirmation_mode != "combined"
        or invoice.installment.number != 1
        or invoice.installment.purchase_id != member.pk
        or invoice.installment.quote["initial_split"].get("recorded_zelle") != plan
    ):
        raise ValidationError(
            "Apply recorded Zelle only within its accepted combined membership and arrival."
        )
    current = review(
        actor=actor, customer=member.customer, booking_id=booking.pk, value=plan["amount"]
    )
    if current != plan:
        raise ValidationError("The recorded Zelle changed. No payment was applied.")
    line = invoice.sale.lines.get()
    for source in plan["sources"]:
        value = amount(source["amount"])
        if not value:
            continue
        receipt = ZelleReceipt.objects.get(pk=source["id"], booking=booking)
        if unallocated(receipt) < value:
            raise ValidationError("The recorded Zelle was already applied or returned.")
        operation = request_operation(
            actor=actor,
            sale_id=invoice.sale_id,
            request_key=uuid.uuid5(member.request_key, "recorded-bank:" + str(receipt.pk)),
            tender="zelle",
            allocation=[
                dict(line=str(line.pk), net=str(value), fee="0.00", item_tax="0.00", fee_tax="0.00")
            ],
            purpose="member_purchase",
            received_on=receipt.received_on,
        )
        MembershipBankAllocation.objects.create(
            operation=operation, purchase=member, receipt=receipt, amount=value
        )
        ZelleApplication.objects.create(receipt=receipt, operation=operation, amount=value)
        record_manual(actor=actor, operation_id=operation.pk, received=True)
