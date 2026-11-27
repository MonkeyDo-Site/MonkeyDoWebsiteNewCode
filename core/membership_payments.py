"""Explicit installment review/collection and accepted membership-card changes.

Opening or refreshing a review is read only. Only confirmation creates ledger
work; an uncertain existing outcome always blocks a replacement collection.
"""

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from .membership_records import (
    MembershipBillingAction,
    MembershipCardMandate,
    MembershipInstallment,
    MembershipInvoice,
    MembershipPurchase,
)
from .membership_reservations import lock_customer
from .membership_sales import authorize, invoice_for, today
from .models import AuditEvent, FinancialLineAdjustment, PaymentMethod
from .payments.amounts import COMPONENTS, ZERO, amount
from .payments.invoices import effective_components
from .payments.jobs import enqueue
from .payments.ledger import (
    RESERVED,
    fingerprint,
    lock_request,
    record_manual,
    request_operation,
    used_components,
    writes_allowed,
)
from .payments.methods import queue_disposal
from .payments.receipts import receipt_date
from .pricing import money


def member_record(member_id):
    return MembershipPurchase.objects.select_related(
        "membership", "customer", "billing_state__mandate__method"
    ).get(pk=member_id)


def available_cards(member):
    available = Q(reusable=True)
    if member.billing_state.mandate:
        available |= Q(pk=member.billing_state.mandate.method_id)
    return PaymentMethod.objects.filter(
        available,
        customer_id=member.customer_id,
        state="active",
        environment="sandbox",
        provider_method__isnull=False,
    ).order_by("last_four", "pk")


def payment_review(*, actor, member_id, installment_id, tender, received_on=None):
    authorize(actor, collect=True)
    member = member_record(member_id)
    installment = MembershipInstallment.objects.select_related("cycle", "invoice__sale").get(
        pk=installment_id, purchase=member
    )
    if tender not in {"card", "cash", "check", "zelle", "gift_card"}:
        raise ValidationError("Choose a supported membership payment method.")
    if member.purpose == "complimentary":
        raise ValidationError("This complimentary membership requires no payment.")
    if installment.due_on > today():
        raise ValidationError(
            "This installment is not due yet. Its scheduled date has not changed."
        )
    stopped = member.billing_state.stopped_on
    if stopped and installment.cycle.starts_on >= stopped:
        raise ValidationError("This installment belongs to the cancelled part of the membership.")
    if received_on is not None and tender != "zelle":
        raise ValidationError("An earlier receipt date is available for Zelle only.")
    when = receipt_date(received_on) if tender != "card" else None
    try:
        sale = installment.invoice.sale
    except MembershipInvoice.DoesNotExist:
        sale = None
    operations = []
    taken = {key: ZERO for key in COMPONENTS}
    if sale is not None:
        operations = list(sale.operations.order_by("requested_at", "pk"))
        if any(op.state in {"ready", "sending", "unknown", "action"} for op in operations):
            raise ValidationError(
                "Check the existing payment outcome before another attempt. No new charge has been requested."
            )
        if any(op.kind != "receipt" and op.state == "succeeded" for op in operations):
            raise ValidationError(
                "This installment has a recorded refund or correction. Ask the owner to review it before collecting again."
            )
        components = effective_components(sale)
        if len(components) != 1:
            raise ValidationError("Review this combined membership invoice before collecting.")
        values = next(iter(components.values()))
        used = used_components(
            op for op in operations if op.kind == "receipt" and op.state in RESERVED
        )
        taken = next(iter(used.values()), taken)
        net = values["net"]
        rate = sale.fee_rate
        if values["item_tax"] or values["fee_tax"]:
            raise ValidationError("Historical membership tax requires owner reconciliation.")
    else:
        net = amount(installment.quote["subtotal"])
        rate = Decimal(installment.quote["rates"]["card_fee_rate"])
    remaining_net = net - taken["net"]
    if remaining_net <= ZERO:
        raise ValidationError("This installment has no unpaid membership amount to collect.")
    fee = money(remaining_net * rate) if tender == "card" else ZERO
    mandate = member.billing_state.mandate
    if tender == "card" and (
        not mandate or mandate.method.state != "active" or not mandate.method.provider_method
    ):
        raise ValidationError("Save and authorize a membership card before requesting this charge.")
    data = {
        "membership": member.pk,
        "installment": installment.pk,
        "number": installment.number,
        "billing_revision": member.billing_state.revision,
        "invoice": str(sale.pk) if sale else None,
        "operations": [{"id": str(op.pk), "state": op.state, "kind": op.kind} for op in operations],
        "tender": tender,
        "net": str(remaining_net),
        "fee": str(fee),
        "total": str(remaining_net + fee),
        "target_fee": str(taken["fee"] + fee),
        "method": str(mandate.method_id) if tender == "card" else None,
        "received_on": when.isoformat() if when else None,
    }
    return data | {"fingerprint": fingerprint(data)}


def previous_action(key, identity):
    prior = MembershipBillingAction.objects.filter(pk=key).first()
    if prior and prior.fingerprint != fingerprint(identity):
        raise ValidationError(
            "This confirmation key already identifies a different membership action."
        )
    return prior


@transaction.atomic
def collect_installment(
    *,
    actor,
    member_id,
    installment_id,
    tender,
    reviewed,
    request_key,
    confirmed=False,
    received_on=None,
    verified_received=False,
):
    authorize(actor, collect=True)
    writes_allowed()
    member = member_record(member_id)
    lock_customer(member.customer_id)
    key = lock_request(request_key)
    identity = dict(
        kind="payment",
        membership=member_id,
        installment=installment_id,
        tender=tender,
        reviewed=reviewed,
        received_on=received_on.isoformat() if received_on else None,
    )
    prior = previous_action(key, identity)
    if prior:
        return prior
    if confirmed is not True:
        raise ValidationError("Confirm this payment after reviewing the current installment.")
    if tender != "card" and verified_received is not True:
        raise ValidationError("Verify the actual payment was received before recording it.")
    data = payment_review(
        actor=actor,
        member_id=member_id,
        installment_id=installment_id,
        tender=tender,
        received_on=received_on,
    )
    if data["fingerprint"] != reviewed:
        raise ValidationError(
            "The membership payment changed. Review the current amount before confirming."
        )
    installment = MembershipInstallment.objects.get(pk=installment_id, purchase_id=member_id)
    invoice = invoice_for(
        installment,
        actor=actor,
        tender=(member.membership.expected_method if installment.number == 1 else "card"),
    )
    sale = invoice.sale
    line = sale.lines.get()
    values = effective_components(sale)[str(line.pk)]
    delta = amount(data["target_fee"]) - values["fee"]
    if delta:
        FinancialLineAdjustment.objects.create(
            request_key=uuid.uuid5(key, "tender-fee"),
            line=line,
            reason="tender_change",
            fee=delta,
            actor=actor,
        )
    allocation = [
        {
            "line": str(line.pk),
            "net": data["net"],
            "fee": data["fee"],
            "item_tax": "0.00",
            "fee_tax": "0.00",
        }
    ]
    operation = request_operation(
        actor=actor,
        sale_id=sale.pk,
        request_key=uuid.uuid5(key, "payment"),
        tender=tender,
        allocation=allocation,
        method_id=data["method"],
        purpose="member_purchase" if installment.number == 1 else "member_installment",
        received_on=received_on if tender == "zelle" else None,
    )
    action = MembershipBillingAction.objects.create(
        id=key,
        purchase=member,
        kind="payment",
        fingerprint=fingerprint(identity),
        details=data,
        operation=operation,
        actor=actor,
    )
    if tender == "card":
        enqueue(kind="payment_dispatch", reference=operation.pk, key=f"dispatch:{operation.pk}")
    else:
        record_manual(actor=actor, operation_id=operation.pk, received=True)
    AuditEvent.objects.create(
        actor=actor,
        action="membership.installment_requested",
        record_type="membership",
        record_id=str(member.pk),
        changes={"installment": installment.pk, "operation": str(operation.pk), "tender": tender},
    )
    return action


def card_update_review(*, actor, member_id):
    authorize(actor, collect=True)
    member = member_record(member_id)
    if member.purpose == "complimentary":
        raise ValidationError("This complimentary membership has no scheduled card payments.")
    text = (
        f"The customer authorizes secure card storage for the remaining accepted payments of membership #{member.membership_number}, "
        "including applicable card processing fees. The purchased term and installment dates stay unchanged. "
        "Updating the card does not retry or collect any payment. Earlier uncertain transactions must be checked before another attempt."
    )
    data = dict(
        operation="card_update",
        origin={"prior_id": member.pk},
        expected_method="card",
        customer=member.customer_id,
        customer_revision=member.customer.revision,
        billing_revision=member.billing_state.revision,
        original_terms=member.terms_text,
        terms=text,
    )
    return data | {"fingerprint": fingerprint(data)}


@transaction.atomic
def change_card(
    *,
    actor,
    member_id,
    method_id,
    revision,
    request_key,
    accepted=False,
    card_authorization_id=None,
    reviewed=None,
):
    authorize(actor, collect=True)
    writes_allowed()
    member = member_record(member_id)
    lock_customer(member.customer_id)
    key = lock_request(request_key)
    identity = dict(
        kind="card_update", membership=member_id, method=str(method_id), revision=revision
    )
    if card_authorization_id:
        identity["card_authorization"] = str(card_authorization_id)
    prior = previous_action(key, identity)
    if prior:
        return prior
    if accepted is not True:
        raise ValidationError(
            "The customer must authorize this card for the remaining membership payments."
        )
    # Reload the mutable projection after taking the customer lock.
    billing = member.billing_state.__class__.objects.select_for_update().get(purchase=member)
    if billing.revision != revision:
        raise ValidationError(
            "The membership billing details changed. Reload before saving a card."
        )
    member.billing_state = billing
    if member.purpose == "complimentary":
        raise ValidationError("This complimentary membership has no scheduled card payments.")
    current = card_update_review(actor=actor, member_id=member_id)
    if reviewed is not None and reviewed != current["fingerprint"]:
        raise ValidationError("The membership card review changed. Reload before confirming.")
    method = None
    if card_authorization_id:
        from .membership_card_setup import reviewed_source

        method = reviewed_source(
            actor=actor,
            authorization_id=card_authorization_id,
            customer=member.customer,
            request_key=key,
            reviewed=current["fingerprint"],
        )
        if str(method.pk) != str(method_id):
            raise ValidationError("Use the card authorized for this membership update.")
        method = (
            PaymentMethod.objects.select_for_update()
            .filter(
                pk=method.pk,
                customer=member.customer,
                state="active",
                environment="sandbox",
                provider_method__isnull=False,
            )
            .first()
        )
    else:
        method = available_cards(member).select_for_update().filter(pk=method_id).first()
    if method is None:
        raise ValidationError("Choose an available card belonging to this customer.")
    previous = billing.mandate.method if billing.mandate else None
    text = (
        f"The customer authorizes {method.brand} ending in {method.last_four} for the remaining "
        f"accepted payments of membership #{member.membership_number}, including applicable card processing fees. "
        "The fixed purchased term and installment dates are unchanged. Updating this card does not retry or collect any payment. "
        "Any earlier uncertain transaction must be checked before another attempt."
    )
    mandate = MembershipCardMandate.objects.create(
        purchase=member, method=method, text=text, actor=actor
    )
    billing.mandate = mandate
    billing.revision += 1
    billing.save(update_fields=["mandate", "revision"])
    action = MembershipBillingAction.objects.create(
        id=key,
        purchase=member,
        kind="card_update",
        fingerprint=fingerprint(identity),
        details=identity | {"text": text},
        mandate=mandate,
        actor=actor,
    )
    if previous and previous.pk != method.pk:
        queue_disposal(previous)
    if card_authorization_id:
        from .membership_card_setup import replace_future_card

        replace_future_card(method, actor)
    AuditEvent.objects.create(
        actor=actor,
        action="membership.card_changed",
        record_type="membership",
        record_id=str(member.pk),
        changes={"last_four": method.last_four, "billing_revision": billing.revision},
    )
    return action
