"""Record a known received remainder, then apply the original funds separately."""

import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction

from .membership_paid_visit_records import MembershipPaidVisitManualPayment
from .payments.amounts import ZERO, amount
from .payments.ledger import fingerprint, lock_request, lock_sale
from .payments.receipts import receipt_date, sender

TENDERS = {"cash": "Cash", "check": "Check", "zelle": "Zelle", "gift_card": "Gift card"}


def available():
    with connection.cursor() as cursor:
        return "core_membershippaidvisitmanualpayment" in connection.introspection.table_names(
            cursor
        )


def plan(intent):
    if not available():
        return None
    return MembershipPaidVisitManualPayment.objects.filter(intent=intent).first()


def current_operation(intent):
    record = plan(intent)
    return record.operation if record else None


def expected_new_payment(intent):
    from .membership_paid_visit_split import plan as split_plan

    split = split_plan(intent)
    if split:
        return amount(split.facts["new_payment"])
    record = plan(intent)
    return (
        amount(record.facts["net"]) if record else amount(intent.offer["paid_visit"]["new_payment"])
    )


def require_funded(intent):
    from .membership_paid_visit_split import plan as split_plan
    from .membership_paid_visit_split import require_funded as split_funded

    if split_plan(intent):
        return split_funded(intent)
    record = plan(intent)
    if not record:
        return False
    from .payments.invoices import effective_components, received, total

    sale = intent.purchase.installments.first().invoice.sale
    operation = record.operation
    accepted = {str(op.pk) for op in sale.operations.filter(state__in=["declined", "cancelled"])}
    accepted.add(str(operation.pk))
    if (
        operation.state != "succeeded"
        or operation.kind != "receipt"
        or operation.amount != amount(record.facts["net"])
        or received(sale) != operation.amount
        or sale.operations.exclude(pk__in=accepted).exists()
        or total(sale) != amount(record.facts["member_total_after"])
        or len(effective_components(sale)) != 1
    ):
        raise ValidationError(
            "Review the recorded membership payment before applying the original visit funds."
        )
    adjustments = list(sale.lines.get().adjustments.all())
    if amount(record.facts["fee_removed"]):
        if len(adjustments) != 1:
            raise ValidationError("Review other membership corrections before applying this visit.")
        adj = adjustments[0]
        if (
            adj.reason != "tender_change"
            or str(adj.request_key) != record.facts["fee_key"]
            or adj.actor_id != record.actor_id
            or adj.net
            or adj.item_tax
            or adj.fee_tax
            or adj.fee != -amount(record.facts["fee_removed"])
        ):
            raise ValidationError("Review the exact unused card-fee adjustment.")
    elif adjustments:
        raise ValidationError("Review other membership corrections before applying this visit.")
    return True


def is_funded(intent):
    from .membership_paid_visit_split import plan as split_plan

    record = plan(intent)
    if record or split_plan(intent):
        try:
            return require_funded(intent)
        except ValidationError:
            return False
    from .membership_paid_visit_recovery import current_operation as card_operation

    operation = card_operation(intent)
    return bool(operation and operation.state == "succeeded")


def review(*, actor, intent_id):
    from .membership_paid_visit_recovery import source_review
    from .payments.invoices import effective_components, total

    if not available():
        raise ValidationError("Complete the reviewed received-payment upgrade first.")
    intent, data = source_review(actor=actor, intent_id=intent_id)
    if plan(intent):
        raise ValidationError(
            "This replacement payment is already recorded. Open its existing receipt."
        )
    sale = intent.purchase.installments.first().invoice.sale
    values = effective_components(sale)
    if (
        len(values) != 1
        or sale.credit_applications.exists()
        or sale.lines.get().adjustments.exists()
    ):
        raise ValidationError("Review other membership credit or invoice corrections first.")
    line, components = next(iter(values.items()))
    fee = components["fee"]
    net = amount(data["amount"]) - fee
    if (
        components["item_tax"]
        or components["fee_tax"]
        or net <= ZERO
        or fee != amount(intent.purchase.installments.first().quote["processing_fee"])
        or components["net"] - net != amount(intent.offer["paid_visit"]["applied"])
    ):
        raise ValidationError("The accepted remainder and reserved original funds need review.")
    data.update(
        membership_sale=str(sale.pk),
        line=line,
        net=str(net),
        fee_removed=str(fee),
        member_total_before=str(total(sale)),
        member_total_after=str(total(sale) - fee),
        billing_revision=intent.purchase.billing_state.revision,
        booking_version=intent.booking.edit_version,
        customer=intent.purchase.customer_id,
    )
    return data | {"fingerprint": fingerprint(data)}


def receipt_facts(*, tender, received_on, sender_name):
    if tender not in TENDERS:
        raise ValidationError(
            "Choose received cash, check, Zelle or a verified physical gift card."
        )
    if tender != "zelle" and (received_on is not None or sender_name):
        raise ValidationError(
            "An earlier receipt date and bank sender are available for Zelle only."
        )
    return dict(
        tender=tender,
        received_on=receipt_date(received_on).isoformat(),
        sender=sender(sender_name, required=tender == "zelle"),
        date_input=received_on.isoformat() if received_on else None,
    )


@transaction.atomic
def record(
    *,
    actor,
    intent_id,
    request_key,
    reviewed,
    tender,
    confirmed=False,
    verified_received=False,
    received_on=None,
    sender_name="",
):
    from .membership_paid_visit_pending import locked
    from .membership_sales import authorize
    from .models import AuditEvent, FinancialLineAdjustment
    from .payments.ledger import record_manual, request_operation, writes_allowed
    from .permissions import require_actor

    authorize(actor, collect=True)
    require_actor(actor, "core.change_booking")
    writes_allowed()
    if confirmed is not True or verified_received is not True:
        raise ValidationError(
            "Verify that this exact payment was actually received before recording it."
        )
    if not available():
        raise ValidationError("Complete the reviewed received-payment upgrade first.")
    receipt = receipt_facts(tender=tender, received_on=received_on, sender_name=sender_name)
    key = lock_request(request_key)
    prior = MembershipPaidVisitManualPayment.objects.filter(pk=key).first()
    if prior:
        if (
            str(prior.intent_id) != str(intent_id)
            or prior.actor_id != actor.pk
            or prior.facts["reviewed_hash"] != reviewed
            or any(
                prior.facts[k] != v
                for k, v in receipt.items()
                if k != "received_on" or receipt["date_input"] is not None
            )
        ):
            raise ValidationError("This received-payment identity belongs to another confirmation.")
        return prior
    intent = locked(intent_id)
    sale = intent.purchase.installments.first().invoice.sale
    lock_sale(sale.pk)
    data = review(actor=actor, intent_id=intent.pk)
    if data["fingerprint"] != reviewed:
        raise ValidationError(
            "The payment or original funds changed. Review the received amount again."
        )
    facts = (
        data
        | receipt
        | dict(
            reviewed_hash=reviewed,
            verified_received=True,
            fee_key=str(uuid.uuid5(key, "unused-card-fee")),
            receipt_key=str(uuid.uuid5(key, "received-membership-remainder")),
        )
    )
    facts["original_allocation"] = data["allocation"]
    facts["allocation"] = [
        dict(line=data["line"], net=data["net"], fee="0.00", item_tax="0.00", fee_tax="0.00")
    ]
    authority = MembershipPaidVisitManualPayment.objects.create(
        id=key,
        intent=intent,
        previous_id=uuid.UUID(data["previous"]),
        operation_id=uuid.UUID(facts["receipt_key"]),
        actor=actor,
        facts=facts,
        fingerprint=fingerprint(facts),
    )
    if amount(data["fee_removed"]):
        FinancialLineAdjustment.objects.create(
            request_key=facts["fee_key"],
            line_id=data["line"],
            reason="tender_change",
            fee=-amount(data["fee_removed"]),
            actor=actor,
        )
    operation = request_operation(
        actor=actor,
        sale_id=sale.pk,
        request_key=authority.operation_id,
        tender=tender,
        allocation=facts["allocation"],
        purpose="member_purchase",
        received_on=receipt_date(received_on),
        paid_visit_manual=authority,
    )
    record_manual(actor=actor, operation_id=operation.pk, received=True)
    AuditEvent.objects.create(
        actor=actor,
        action="membership.paid_visit_payment_received",
        record_type="membership",
        record_id=str(intent.purchase_id),
        changes=dict(
            intent=str(intent.pk),
            operation=str(operation.pk),
            tender=tender,
            amount=data["net"],
            unused_card_fee_removed=data["fee_removed"],
        ),
    )
    return authority


def authorize_receipt(record, *, invoice, actor, request_key, tender, method_id, allocation):
    if not isinstance(record, MembershipPaidVisitManualPayment) or not available():
        raise PermissionDenied
    stored = MembershipPaidVisitManualPayment.objects.select_related("intent", "previous").get(
        pk=record.pk
    )
    if (
        invoice.installment.purchase_id != stored.intent.purchase_id
        or invoice.installment.number != 1
        or actor is None
        or actor.pk != stored.actor_id
        or method_id is not None
        or request_key != stored.operation_id
        or tender != stored.facts["tender"]
        or allocation != stored.facts["allocation"]
        or stored.previous.state not in {"declined", "cancelled"}
        or fingerprint(stored.facts) != stored.fingerprint
    ):
        raise ValidationError("Use only this exact verified membership receipt authority.")
    from .membership_paid_visit_new_card import require_known_storage
    from .membership_paid_visit_records import MembershipPaidVisitRelease

    require_known_storage(stored.intent)
    if MembershipPaidVisitRelease.objects.filter(intent=stored.intent).exists():
        raise ValidationError("This paid-visit application has already ended.")


def controls(*, actor, pending):
    if not pending or pending["stopped"]:
        return None
    intent = pending["intent"]
    saved = plan(intent)
    if saved:
        return dict(saved=saved, facts=saved.facts, operation=saved.operation)
    try:
        data = review(actor=actor, intent_id=intent.pk)
    except (ValidationError, PermissionDenied):
        return None
    return dict(key=uuid.uuid4(), reviewed=data["fingerprint"], facts=data, tenders=TENDERS.items())


def is_manual_receipt(operation):
    from .membership_paid_visit_split import available as split_available
    from .membership_paid_visit_split_records import MembershipPaidVisitSplit

    if (
        split_available()
        and MembershipPaidVisitSplit.objects.filter(operation_id=operation.request_key).exists()
    ):
        return True
    return bool(
        available()
        and MembershipPaidVisitManualPayment.objects.filter(
            operation_id=operation.request_key
        ).exists()
    )


def cancellation_adjustments_valid(intent, sale):
    other = sale.lines.get().adjustments.exclude(reason="membership_refund")
    manual = plan(intent)
    from .membership_paid_visit_split import plan as split_plan

    manual = manual or split_plan(intent)
    if manual:
        other = other.exclude(
            request_key=manual.facts["fee_key"],
            reason="tender_change",
            actor_id=manual.actor_id,
            net=ZERO,
            item_tax=ZERO,
            fee_tax=ZERO,
            fee=-amount(manual.facts["fee_removed"]),
        )
    return not other.exists()
