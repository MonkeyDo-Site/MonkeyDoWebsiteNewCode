"""One queued installment per accepted claim; no producer or financial POST here."""

import uuid
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction

from .customer_credit_records import CustomerCreditApplication
from .membership_collection_authority import enabled, prepare_claim
from .membership_collection_credit import apply_scheduled_credit
from .membership_records import MembershipCollectionClaim, MembershipInstallment, MembershipInvoice
from .membership_reservations import lock_customer
from .membership_sales import invoice_for
from .models import AuditEvent, Customer, PaymentOperation
from .payments.amounts import ZERO, amount
from .payments.jobs import enqueue
from .payments.ledger import lock_request, request_operation


@dataclass(frozen=True)
class ScheduledCollection:
    claim: MembershipCollectionClaim
    invoice: MembershipInvoice
    operation: PaymentOperation | None
    credit_application: CustomerCreditApplication | None


@transaction.atomic
def schedule_installment(installment_id):
    """Queue one exact card remainder, or apply full credit without a card job."""
    enabled()
    item = MembershipInstallment.objects.select_related("purchase").get(pk=installment_id)
    # The customer row precedes the advisory lock, as for accepted purchases:
    # an earlier locked correction must be able to finish its FK checks.
    Customer.objects.select_for_update(no_key=True).get(pk=item.purchase.customer_id)
    lock_customer(item.purchase.customer_id)
    claim = MembershipCollectionClaim.objects.filter(installment=item).first()
    if claim:
        credit = CustomerCreditApplication.objects.filter(scheduled_claim=claim).first()
        existing = PaymentOperation.objects.filter(
            request_key=claim.payment_key,
            sale__membership_invoice__installment=item,
            actor__isnull=True,
            purpose="member_installment",
            kind="receipt",
            tender="card",
        ).first()
        if existing:
            # Existing paid, declined, cancelled or uncertain outcomes are read
            # back, never treated as permission for a replacement collection.
            return ScheduledCollection(claim, item.invoice, existing, credit)
        if credit:
            if amount(claim.details["card_total"]) == ZERO:
                return ScheduledCollection(claim, item.invoice, None, credit)
            raise ValidationError("This scheduled allocation needs review before any card request.")
    claim = prepare_claim(item.pk)
    lock_request(claim.payment_key)
    invoice = invoice_for(item, actor=None, tender="card", scheduled_claim=claim)
    credit = apply_scheduled_credit(claim) if amount(claim.details["credit_to_apply"]) else None
    operation = None
    if amount(claim.details["card_total"]):
        line = invoice.sale.lines.get()
        operation = request_operation(
            actor=None,
            sale_id=invoice.sale_id,
            request_key=claim.payment_key,
            tender="card",
            allocation=[
                dict(
                    line=str(line.pk),
                    net=claim.details["remaining_principal"],
                    fee=claim.details["card_fee"],
                    item_tax="0.00",
                    fee_tax="0.00",
                )
            ],
            method_id=claim.details["method"],
            purpose="member_installment",
            scheduled_membership_claim=claim,
        )
        enqueue(
            kind="payment_dispatch", reference=operation.pk, key=uuid.uuid5(claim.pk, "dispatch")
        )
    AuditEvent.objects.create(
        actor=None,
        action="membership.collection_queued",
        record_type="membership",
        record_id=str(item.purchase_id),
        changes={
            "installment": item.pk,
            "claim": str(claim.pk),
            "operation": str(operation.pk) if operation else None,
            "credit_applied": str(credit.amount) if credit else "0.00",
        },
    )
    return ScheduledCollection(claim, invoice, operation, credit)
