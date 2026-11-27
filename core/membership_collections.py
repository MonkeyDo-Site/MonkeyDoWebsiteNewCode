"""One queued installment per accepted claim; no producer or financial POST here."""

import uuid

from django.core.exceptions import ValidationError
from django.db import transaction

from .membership_collection_authority import card_only, enabled, prepare_claim
from .membership_collection_plan import installment_plan
from .membership_records import MembershipCollectionClaim, MembershipInstallment
from .membership_reservations import lock_customer
from .membership_sales import invoice_for
from .models import AuditEvent, Customer, PaymentOperation
from .payments.jobs import enqueue
from .payments.ledger import full_allocation, lock_request, request_operation


@transaction.atomic
def schedule_installment(installment_id):
    enabled()
    item = MembershipInstallment.objects.select_related("purchase").get(pk=installment_id)
    # The customer row precedes the advisory lock, as for accepted purchases:
    # an earlier locked correction must be able to finish its FK checks.
    Customer.objects.select_for_update(no_key=True).get(pk=item.purchase.customer_id)
    lock_customer(item.purchase.customer_id)
    claim = MembershipCollectionClaim.objects.filter(installment=item).first()
    if claim:
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
            return existing
    else:
        plan = installment_plan(item.pk)
        if plan["credit_to_apply"] != "0.00":
            raise ValidationError(
                "Scheduled customer credit requires review. No card payment was requested."
            )
    claim = prepare_claim(item.pk)
    card_only(claim)
    lock_request(claim.payment_key)
    invoice = invoice_for(item, actor=None, tender="card", scheduled_claim=claim)
    operation = request_operation(
        actor=None,
        sale_id=invoice.sale_id,
        request_key=claim.payment_key,
        tender="card",
        allocation=full_allocation(invoice.sale),
        method_id=claim.details["method"],
        purpose="member_installment",
        scheduled_membership_claim=claim,
    )
    enqueue(kind="payment_dispatch", reference=operation.pk, key=uuid.uuid5(claim.pk, "dispatch"))
    AuditEvent.objects.create(
        actor=None,
        action="membership.collection_queued",
        record_type="membership",
        record_id=str(item.purchase_id),
        changes={"installment": item.pk, "claim": str(claim.pk), "operation": str(operation.pk)},
    )
    return operation
