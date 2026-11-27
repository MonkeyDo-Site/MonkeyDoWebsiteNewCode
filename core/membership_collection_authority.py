"""A durable system claim remains separate from public or staff permission."""

import uuid
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .availability import NEW_YORK
from .membership_collection_plan import REASONS, installment_plan
from .membership_records import MembershipCollectionClaim, MembershipInstallment, MembershipInvoice
from .membership_reservations import lock_customer
from .membership_sales import enabled as membership_enabled
from .membership_sales import today
from .models import AuditEvent
from .payments.amounts import ZERO, amount
from .payments.ledger import fingerprint, lock_request, writes_allowed


def enabled():
    membership_enabled()
    writes_allowed()
    if not settings.MEMBERSHIP_COLLECTIONS_ENABLED:
        raise PermissionDenied


def claim_key(item):
    return uuid.uuid5(item.purchase.request_key, f"scheduled-installment:{item.number}")


def current_claim(value):
    """Validate the exact persisted scope before financial services may use it."""
    enabled()
    if type(value) is not MembershipCollectionClaim:
        raise PermissionDenied
    try:
        claim = MembershipCollectionClaim.objects.select_related("installment__purchase").get(
            pk=value.pk
        )
    except (MembershipCollectionClaim.DoesNotExist, ValueError, TypeError):
        raise PermissionDenied from None
    body = {key: val for key, val in claim.details.items() if key != "fingerprint"}
    if (
        claim.pk != claim_key(claim.installment)
        or claim.payment_key != uuid.uuid5(claim.pk, "payment")
        or claim.credit_key != uuid.uuid5(claim.pk, "credit")
        or claim.fingerprint != fingerprint(body)
        or claim.details.get("fingerprint") != claim.fingerprint
        or claim.planned_on != today()
        or claim.expires_at <= timezone.now()
        or claim.details.get("installment") != claim.installment_id
        or claim.details.get("mandate") != str(claim.mandate_id)
    ):
        raise PermissionDenied
    return claim


def authorize(value):
    """Authorize a pristine preparation before its invoice exists."""
    claim = current_claim(value)
    plan = installment_plan(claim.installment_id)
    if plan["status"] != "ready_for_scheduling" or plan["fingerprint"] != claim.fingerprint:
        raise ValidationError("The scheduled installment changed and needs review.")
    return claim


def authorize_invoice(value, *, installment_id, tender):
    claim = authorize(value)
    if claim.installment_id != installment_id or tender != "card":
        raise PermissionDenied
    return claim


def prepared_invoice(value, *, before_credit=False):
    """Recheck this claim's invoice and its exact own credit application."""
    claim = current_claim(value)
    try:
        invoice = MembershipInvoice.objects.select_related("sale", "installment__purchase").get(
            installment_id=claim.installment_id
        )
    except MembershipInvoice.DoesNotExist:
        raise PermissionDenied from None
    sale, item = invoice.sale, invoice.installment
    if (
        sale.actor_id is not None
        or sale.created_at < claim.created_at
        or sale.kind != "membership"
        or sale.booking_id is not None
        or sale.customer_id != claim.details["customer"]
        or sale.creation_key != uuid.uuid5(item.purchase.request_key, f"installment:{item.number}")
        or sale.fingerprint
        != fingerprint(
            {"membership": item.purchase_id, "installment": item.number, "quote": item.quote}
        )
        or sale.subtotal != amount(claim.details["principal_due"])
        or sale.processing_fee != amount(item.quote["processing_fee"])
        or sale.total != amount(item.quote["total"])
        or sale.sales_tax != ZERO
        or sale.fee_rate != Decimal(item.quote["rates"]["card_fee_rate"])
        or sale.operations.exclude(request_key=claim.payment_key).exists()
    ):
        raise ValidationError("The scheduled invoice changed and needs payment review.")
    plan = installment_plan(item.pk)
    from .membership_collection_credit import restore_projection

    plan = restore_projection(claim, invoice, plan, before_credit=before_credit)
    # The original no-invoice projection remains the accepted scope. Only the
    # invoice just created under that claim may be omitted from this comparison.
    plan["reasons"] = [reason for reason in plan["reasons"] if reason != "existing_invoice"]
    plan["messages"] = [REASONS[reason] for reason in plan["reasons"]]
    plan["status"] = "review" if plan["reasons"] else "ready_for_scheduling"
    body = {key: val for key, val in plan.items() if key != "fingerprint"}
    if plan["status"] != "ready_for_scheduling" or fingerprint(body) != claim.fingerprint:
        raise ValidationError("The scheduled installment changed and needs review.")
    return claim, invoice


def authorize_operation(value, *, sale_id, request_key, method_id, allocation):
    claim, invoice = prepared_invoice(value)
    lines = list(invoice.sale.lines.all())
    if len(lines) != 1:
        raise PermissionDenied
    expected = [
        dict(
            line=str(lines[0].pk),
            net=claim.details["remaining_principal"],
            fee=claim.details["card_fee"],
            item_tax="0.00",
            fee_tax="0.00",
        )
    ]
    from .payments.ledger import full_allocation

    if (
        str(sale_id) != str(invoice.sale_id)
        or request_key != claim.payment_key
        or str(method_id) != claim.details["method"]
        or allocation != expected
        or full_allocation(invoice.sale) != [expected[0] | {"net": claim.details["principal_due"]}]
    ):
        raise PermissionDenied
    return claim


def authorize_dispatch(operation):
    if (
        operation.actor_id is not None
        or operation.kind != "receipt"
        or operation.tender != "card"
        or operation.purpose != "member_installment"
        or operation.original_id is not None
        or operation.manual_received_on is not None
    ):
        raise PermissionDenied
    try:
        claim = MembershipCollectionClaim.objects.get(
            installment__invoice__sale_id=operation.sale_id
        )
    except MembershipCollectionClaim.DoesNotExist:
        raise PermissionDenied from None
    authorize_operation(
        claim,
        sale_id=operation.sale_id,
        request_key=operation.request_key,
        method_id=operation.method_id,
        allocation=operation.allocation,
    )
    if operation.amount != amount(claim.details["card_total"]):
        raise PermissionDenied
    return claim


@transaction.atomic
def prepare_claim(installment_id):
    enabled()
    item = MembershipInstallment.objects.select_related("purchase").get(pk=installment_id)
    lock_customer(item.purchase.customer_id)
    key = lock_request(claim_key(item))
    existing = MembershipCollectionClaim.objects.filter(pk=key).first()
    if existing:
        return authorize(existing)
    plan = installment_plan(item.pk)
    if plan["status"] != "ready_for_scheduling":
        raise ValidationError("This installment requires review before scheduled collection.")
    expiry = timezone.make_aware(datetime.combine(today() + timedelta(days=1), time.min), NEW_YORK)
    claim = MembershipCollectionClaim.objects.create(
        id=key,
        installment=item,
        mandate_id=uuid.UUID(plan["mandate"]),
        payment_key=uuid.uuid5(key, "payment"),
        credit_key=uuid.uuid5(key, "credit"),
        planned_on=today(),
        expires_at=expiry,
        fingerprint=plan["fingerprint"],
        details=plan,
    )
    AuditEvent.objects.create(
        actor=None,
        action="membership.collection_claimed",
        record_type="membership",
        record_id=str(item.purchase_id),
        changes={"installment": item.pk, "claim": str(claim.pk), "payment_requested": False},
    )
    return claim
