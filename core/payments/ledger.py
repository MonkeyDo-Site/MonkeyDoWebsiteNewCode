"""Trusted payment services; browser totals, arbitrary tokens and legacy quotes cannot charge."""

import hashlib
import json
import re
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.utils import timezone

from core.models import AuditEvent, Booking, BookingQuote, Customer
from core.permissions import require_actor

from .amounts import COMPONENTS, ZERO, allocate, amount
from .models import (
    BookingCardAgreement,
    FinancialLine,
    FinancialPosting,
    FinancialSale,
    PaymentEvent,
    PaymentFollowup,
    PaymentMethod,
    PaymentOperation,
)

CATEGORIES = {
    "Child admissions — Unlimited membership": "member_unlimited_visit",
    "Child admissions — Subscription free visits": "member_subscription_free",
    "Child admissions — Subscription additional visits": "member_subscription_additional",
    "Supervised child admissions — Subscription discount": "member_subscription_supervised",
    "Child admissions": "open_child",
    "Owner-priced admissions": "owner_priced_admissions",
    "Supervised child admissions": "supervised_child",
    "Required baby admission": "minimum_baby",
    "Required adult admission": "minimum_adult",
    "Additional adults": "additional_adult",
    "Grip socks — pick up upon arrival": "socks",
    "Partial cancellation fee": "partial_cancellation",
    "Cancellation fee": "cancellation_fee",
}
RESERVED = ("ready", "sending", "unknown", "succeeded", "action")


def writes_allowed():
    if settings.RECOVERY_HOLD:
        raise ValidationError(
            "Recovery review is active. New financial or card actions are paused."
        )


def enabled():
    if not settings.PAYMENT_SANDBOX_ENABLED or settings.APP_ENV not in {
        "test",
        "development",
        "staging",
    }:
        raise ValidationError("Sandbox payment integration is not enabled.")


def fingerprint(data):
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def lock_request(key):
    try:
        key = uuid.UUID(str(key))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("A valid payment request identity is required.") from None
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(%s, %s)",
                [73218, int.from_bytes(key.bytes[:4], signed=True)],
            )
    return key


def lock_sale(sale_id):
    """Serialize allocations without UPDATE permission on an immutable sale.

    Call inside the surrounding transaction. Booking actions already lock the
    booking, so use that same order before taking the per-sale advisory lock.
    Sales without a booking still get the same allocation/reversal protection.
    """
    sale = FinancialSale.objects.get(pk=sale_id)
    if sale.kind == "membership":
        from core.membership_reservations import lock_customer

        lock_customer(sale.customer_id)
    if sale.booking_id:
        Booking.objects.select_for_update().get(pk=sale.booking_id)
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(%s, %s)",
                [73219, int.from_bytes(sale.pk.bytes[:4], signed=True)],
            )
    return sale


def audit(actor, action, operation):
    AuditEvent.objects.create(
        actor=actor,
        action=action,
        record_type="payment",
        record_id=str(operation.pk),
        changes={
            "state": operation.state,
            "amount": str(operation.amount),
            "sale_id": str(operation.sale_id),
        },
    )


@transaction.atomic
def accept_booking_sale(*, actor, booking_id, quote_id, creation_key, kind="visit"):
    enabled()
    require_actor(actor, "core.collect_payment")
    creation_key = lock_request(creation_key)
    # Customer lock also serializes reuse of a request key for this customer.
    booking = Booking.objects.select_for_update().get(pk=booking_id)
    Customer.objects.select_for_update().get(pk=booking.customer_id)
    if booking.workflow != "integrated_v1":
        raise ValidationError("Earlier test bookings cannot generate payment operations.")
    quote = BookingQuote.objects.get(pk=quote_id, booking=booking)
    if quote.pk != booking.quotes.first().pk:
        raise ValidationError("Review the current booking price before collection.")
    data = quote.snapshot
    if kind not in {"visit", "cancellation"} or data.get("sale_kind", "visit") != kind:
        raise ValidationError("The saved price does not match this payment purpose.")
    identity = fingerprint(
        {"booking": booking.pk, "quote": quote.pk, "customer": booking.customer_id, "kind": kind}
    )
    prior = FinancialSale.objects.filter(creation_key=creation_key).first()
    if prior:
        if prior.fingerprint != identity:
            raise ValidationError("This payment request key has already been used.")
        return prior
    prior = FinancialSale.objects.filter(quote=quote, kind=kind).first()
    if prior:
        return prior
    # One order revision may be replaced only before any operation reserves money.
    if PaymentOperation.objects.filter(sale__booking=booking, state__in=RESERVED).exists():
        raise ValidationError(
            "Resolve earlier payment operations before accepting a revised price."
        )
    subtotal, fee, tax, total = [
        amount(data[k]) for k in ("subtotal", "processing_fee", "sales_tax", "total")
    ]
    if total != subtotal + fee + tax or not data.get("test_mode"):
        raise ValidationError("The accepted price does not reconcile to sandbox amounts.")
    lines = data["lines"]
    if not lines or sum((amount(x["amount"]) for x in lines), ZERO) != subtotal:
        raise ValidationError("The accepted price lines do not reconcile.")
    taxable_fee_parts = allocate(
        amount(data["taxable_processing_fee"]),
        [x["amount"] if x["taxable"] else ZERO for x in lines],
    )
    nontaxable_fee_parts = allocate(
        fee - amount(data["taxable_processing_fee"]),
        [x["amount"] if not x["taxable"] else ZERO for x in lines],
    )
    fee_parts = [a + b for a, b in zip(taxable_fee_parts, nontaxable_fee_parts)]
    # Tax is allocated from the combined rounded charge, never independently
    # rerounded into components that could sum to a different customer total.
    tax_weights = []
    for line, taxable_fee in zip(lines, taxable_fee_parts):
        tax_weights.extend([amount(line["amount"]) if line["taxable"] else ZERO, taxable_fee])
    taxes = allocate(tax, tax_weights)
    sale = FinancialSale.objects.create(
        creation_key=creation_key,
        fingerprint=identity,
        customer=booking.customer,
        kind=kind,
        customer_label=booking.customer.last_name,
        booking=booking,
        quote=quote,
        booking_version=booking.edit_version,
        subtotal=subtotal,
        processing_fee=fee,
        sales_tax=tax,
        total=total,
        tax_rate=data["rates"]["tax_rate"],
        fee_rate=data["rates"]["card_fee_rate"],
        policy_id_at_sale=quote.policy_id,
        service_at=booking.session.starts_at,
        actor=actor,
    )
    for position, (line, line_fee) in enumerate(zip(lines, fee_parts)):
        if line["label"] not in CATEGORIES:
            raise ValidationError("The financial product category must be explicitly mapped.")
        FinancialLine.objects.create(
            sale=sale,
            position=position,
            category=CATEGORIES[line["label"]],
            description=line["label"],
            quantity=line["quantity"],
            unit_price=amount(line["unit_price"]),
            net=amount(line["amount"]),
            taxable=line["taxable"],
            fee=line_fee,
            item_tax=taxes[2 * position],
            fee_tax=taxes[2 * position + 1],
        )
    AuditEvent.objects.create(
        actor=actor,
        action="payment.sale_accepted",
        record_type="sale",
        record_id=str(sale.pk),
        changes={"booking_id": booking.pk, "quote_id": quote.pk, "total": str(total)},
    )
    return sale


def full_allocation(sale):
    from .invoices import effective_components

    return [
        {"line": key, **{component: str(value) for component, value in values.items()}}
        for key, values in effective_components(sale).items()
    ]


def checked_allocation(sale, allocation):
    from .invoices import effective_components

    lines = effective_components(sale)
    cleaned, seen = [], set()
    if not isinstance(allocation, list) or not allocation or len(allocation) > len(lines):
        raise ValidationError("A bounded financial line allocation is required.")
    for part in allocation:
        if not isinstance(part, dict) or set(part) != {"line", *COMPONENTS}:
            raise ValidationError("Invalid financial allocation fields.")
        key = str(part["line"])
        if key not in lines or key in seen:
            raise ValidationError("Payment allocation does not belong to this sale.")
        seen.add(key)
        values = {k: amount(part[k]) for k in COMPONENTS}
        if any(values[k] > lines[key][k] for k in COMPONENTS):
            raise ValidationError("Allocation exceeds the accepted financial line.")
        cleaned.append({"line": key, **{k: str(v) for k, v in values.items()}})
    return cleaned


def used_components(operations):
    totals = {}
    for operation in operations:
        for part in operation.allocation:
            entry = totals.setdefault(part["line"], {k: ZERO for k in COMPONENTS})
            for key in COMPONENTS:
                entry[key] += amount(part[key])
    return totals


@transaction.atomic
def request_operation(
    *,
    actor,
    sale_id,
    request_key,
    tender,
    allocation,
    method_id=None,
    original_id=None,
    kind="receipt",
    purpose="arrival",
    received_on=None,
    public_membership_authority=None,
    scheduled_membership_claim=None,
    membership_refund_plan_id=None,
):
    enabled()
    if membership_refund_plan_id is not None and kind != "refund":
        raise PermissionDenied
    public = actor is None and public_membership_authority is not None
    scheduled = scheduled_membership_claim is not None
    if scheduled:
        from core.membership_collection_authority import current_claim

        if (
            actor is not None
            or public_membership_authority is not None
            or kind != "receipt"
            or tender != "card"
            or purpose != "member_installment"
            or original_id is not None
            or received_on is not None
        ):
            raise PermissionDenied
        current_claim(scheduled_membership_claim)
    elif public:
        from core.membership_public_authority import verified_scope

        verified_scope(public_membership_authority)
        if kind != "receipt" or tender != "card" or purpose != "member_purchase":
            raise PermissionDenied
    else:
        require_actor(actor, "core.collect_payment", owner=kind != "receipt")
    request_key = lock_request(request_key)
    sale = lock_sale(sale_id)
    if (
        tender not in dict(PaymentOperation._meta.get_field("tender").choices)
        or kind not in PaymentOperation.Kind.values
    ):
        raise ValidationError("Choose a supported payment operation.")
    if purpose not in {
        "arrival",
        "cancellation",
        "no_show",
        "follow_up",
        "correction",
        "member_purchase",
        "member_installment",
    }:
        raise ValidationError("Choose a supported payment purpose.")
    if kind == "receipt":
        writes_allowed()
    if kind != "receipt":
        purpose = "correction"
    member_source = False
    if kind == "receipt" and sale.kind == "visit":
        from core.customer_credit import held_on

        if held_on(sale):
            raise ValidationError(
                "A customer-credit source needs owner review before new collection."
            )
    if kind == "receipt" and (sale.kind == "membership" or purpose.startswith("member_")):
        from core.membership_records import MembershipInvoice
        from core.membership_sales import authorize

        if not scheduled:
            authorize(actor, collect=True, authority=public_membership_authority)
        invoice = (
            MembershipInvoice.objects.select_related(
                "installment__purchase__billing_state__mandate"
            )
            .filter(sale=sale)
            .first()
        )
        if not invoice or purpose != (
            "member_purchase" if invoice.installment.number == 1 else "member_installment"
        ):
            raise ValidationError("Use the accepted membership installment before collecting.")
        from core.customer_credit import held_on

        if held_on(sale):
            raise ValidationError(
                "A customer-credit source needs owner review before new collection."
            )
        if public:
            from core.membership_public_authority import check_purchase

            check_purchase(public_membership_authority, invoice.installment.purchase)
            if invoice.installment.number != 1 or request_key != uuid.uuid5(
                invoice.installment.purchase.request_key, "first-payment"
            ):
                raise PermissionDenied
        mandate = invoice.installment.purchase.billing_state.mandate
        stopped = invoice.installment.purchase.billing_state.stopped_on
        if stopped and invoice.installment.cycle.starts_on >= stopped:
            raise ValidationError(
                "This installment belongs to the cancelled part of the membership."
            )
        if tender == "card" and (not mandate or str(mandate.method_id) != str(method_id)):
            raise ValidationError("Use the currently accepted membership payment method.")
        member_source = True
    if purpose == "correction":
        require_actor(actor, "core.collect_payment", owner=True)
    if tender != "card":
        from .receipts import receipt_date

        received_on = receipt_date(received_on)
    elif received_on is not None:
        raise ValidationError("Card dates come from verified provider evidence.")
    if sale.booking_id:
        booking = Booking.objects.select_for_update().get(pk=sale.booking_id)
        if booking.workflow != "integrated_v1" or (
            kind == "receipt"
            and sale.kind == "visit"
            and sale.quote_id != booking.quotes.first().pk
        ):
            raise ValidationError("Review the current integrated booking before collection.")
    cleaned = checked_allocation(sale, allocation)
    if scheduled:
        from core.membership_collection_authority import authorize_operation

        if not member_source:
            raise PermissionDenied
        authorize_operation(
            scheduled_membership_claim,
            sale_id=sale.pk,
            request_key=request_key,
            method_id=method_id,
            allocation=cleaned,
        )
    if public and (not member_source or cleaned != full_allocation(sale)):
        raise PermissionDenied
    value = sum((amount(part[k]) for part in cleaned for k in COMPONENTS), ZERO)
    if not ZERO < value <= Decimal("20000000.00"):
        raise ValidationError("Payment amount is outside the supported range.")
    if tender != "card" and any(amount(p["fee"]) or amount(p["fee_tax"]) for p in cleaned):
        raise ValidationError("A non-card payment cannot collect a card processing fee.")
    identity = fingerprint(
        {
            "sale": str(sale.pk),
            "kind": kind,
            "purpose": purpose,
            "tender": tender,
            "allocation": cleaned,
            "method": str(method_id) if method_id else None,
            "original": str(original_id) if original_id else None,
            "received_on": received_on.isoformat() if received_on else None,
        }
    )
    prior = PaymentOperation.objects.filter(request_key=request_key).first()
    if prior:
        if prior.fingerprint != identity:
            raise ValidationError("This payment request key has already been used.")
        return prior
    method = None
    if tender == "card":
        method = PaymentMethod.objects.select_for_update().get(
            pk=method_id, customer_id=sale.customer_id, environment="sandbox"
        )
        if kind == "receipt" and (method.state != "active" or not method.provider_method):
            raise ValidationError("This saved payment method is not available for charging.")
        if kind == "receipt" and sale.booking_id:
            agreement = BookingCardAgreement.objects.filter(booking_id=sale.booking_id).first()
            if (agreement and agreement.method_id != method.pk) or (
                not agreement and settings.BOOKING_COMPLETION_ENABLED
            ):
                raise ValidationError("Use the currently reviewed card agreement for this booking.")
        if (
            not method.reusable
            and not member_source
            and method.booking_id != sale.booking_id
            and not method.agreements.filter(
                booking_id=sale.booking_id, resolved_at__isnull=True
            ).exists()
        ):
            raise ValidationError("This saved payment method belongs to another booking.")
    original = None
    if kind == "receipt":
        if original_id:
            raise ValidationError("A receipt cannot be a refund of another operation.")
        used = used_components(sale.operations.filter(kind="receipt", state__in=RESERVED))
        from core.customer_credit import applied_components

        for line, values in applied_components(sale).items():
            target = used.setdefault(line, {key: ZERO for key in COMPONENTS})
            for component in COMPONENTS:
                target[component] += values[component]
        from .invoices import effective_components

        limits = effective_components(sale)
    else:
        original = PaymentOperation.objects.select_for_update().get(
            pk=original_id, sale=sale, kind="receipt", state="succeeded", tender=tender
        )
        if tender == "card" and original.method_id != method_id:
            raise ValidationError("A refund must use the original payment source.")
        used = used_components(original.adjustments.filter(state__in=RESERVED))
        limits = {p["line"]: {k: amount(p[k]) for k in COMPONENTS} for p in original.allocation}
        if kind == "void" and cleaned != original.allocation:
            raise ValidationError("A void must reverse the whole original payment.")
        from core.customer_credit import protect_source

        protect_source(original, cleaned)
        if sale.kind == "membership" or membership_refund_plan_id is not None:
            from core.membership_cancellations import protect_refund

            protect_refund(original, cleaned, plan_id=membership_refund_plan_id)
    for part in cleaned:
        for key in COMPONENTS:
            if amount(part[key]) + used.get(part["line"], {}).get(key, ZERO) > limits.get(
                part["line"], {}
            ).get(key, ZERO):
                raise ValidationError(
                    "This amount is already paid, reserved or reversed; reconcile it first."
                )
    operation = PaymentOperation.objects.create(
        request_key=request_key,
        fingerprint=identity,
        sale=sale,
        original=original,
        method=method,
        kind=kind,
        purpose=purpose,
        brand=method.brand if method else "",
        last_four=method.last_four if method else "",
        tender=tender,
        amount=value,
        manual_received_on=received_on,
        allocation=cleaned,
        actor=actor,
    )
    PaymentEvent.objects.create(
        operation=operation, state="ready", source="worker" if scheduled else "staff", actor=actor
    )
    audit(actor, "payment.requested", operation)
    return operation


@transaction.atomic
def record_result(
    *, operation_id, state, source, provider_reference="", code="", occurred_at=None, actor=None
):
    enabled()
    candidate = PaymentOperation.objects.select_related("sale").get(pk=operation_id)
    from core.membership_arrival import lock_payment

    lock_payment(candidate)
    if candidate.sale.kind == "membership":
        from core.membership_reservations import lock_customer

        lock_customer(candidate.sale.customer_id)
    operation = PaymentOperation.objects.select_for_update().get(pk=operation_id)
    if source not in {
        "provider",
        "staff",
        "worker",
        "reconcile",
        "webhook",
        "owner_dashboard",
    } or not re.fullmatch(r"[a-z0-9_]{0,40}", code):
        raise ValidationError("Invalid safe payment result classification.")
    if provider_reference and not re.fullmatch(r"[1-9][0-9]{0,19}", provider_reference):
        raise ValidationError("Invalid provider transaction reference.")
    if occurred_at is not None and timezone.is_naive(occurred_at):
        raise ValidationError("Use a timezone-aware payment timestamp.")
    if operation.state in {"succeeded", "declined", "cancelled"}:
        if operation.state != state or (
            provider_reference and operation.provider_reference != provider_reference
        ):
            raise ValidationError("The payment already has a different final result; reconcile it.")
        return operation
    if state not in {"succeeded", "declined", "unknown", "action"}:
        raise ValidationError("Invalid payment result.")
    if operation.tender == "card" and state == "succeeded" and not provider_reference:
        raise ValidationError("A successful card operation needs its provider reference.")
    if state == "succeeded":
        when = occurred_at
        for part in operation.allocation:
            FinancialPosting.objects.create(
                operation=operation,
                line_id=part["line"],
                occurred_at=when,
                **{k: amount(part[k]) for k in COMPONENTS},
            )
    operation.state = state
    operation.provider_reference = provider_reference or operation.provider_reference
    operation.result_code = code
    operation.completed_at = timezone.now() if state in {"succeeded", "declined"} else None
    operation.reconciliation_required = state in {"unknown", "action"}
    operation.save(
        update_fields=[
            "state",
            "provider_reference",
            "result_code",
            "completed_at",
            "reconciliation_required",
        ]
    )
    PaymentEvent.objects.create(
        operation=operation, state=state, source=source, code=code, actor=actor
    )
    audit(actor, "payment.result_recorded", operation)
    if state in {"unknown", "action", "declined"}:
        PaymentFollowup.objects.get_or_create(
            operation=operation, defaults={"plan": "owner_review"}
        )
    if state == "succeeded" and operation.sale.booking_id:
        from .checkout import resolve_if_settled

        resolve_if_settled(operation.sale.booking_id)
        from core.membership_arrival import payment_updated as combined_payment_updated

        combined_payment_updated(operation)
    if state == "succeeded" and operation.sale.kind == "membership":
        from core.membership_sales import payment_updated

        payment_updated(operation)
    if state in {"unknown", "action", "declined"} and settings.BOOKING_EMAIL_ENABLED:
        from core.communications.content import owner_payment_issue
        from core.communications.models import MessageDelivery
        from core.communications.services import enqueue

        key = f"payment-issue:{operation.pk}"
        if not MessageDelivery.objects.filter(dedupe_key=key).exists():
            enqueue(
                key=key,
                kind="payment_issue",
                recipient=settings.BOOKING_REPLY_TO,
                subject="MonkeyDo payment requires review",
                text=owner_payment_issue(operation),
                customer=operation.sale.customer,
                booking=operation.sale.booking,
            )
    return operation


@transaction.atomic
def record_manual(*, actor, operation_id, received):
    enabled()
    operation = PaymentOperation.objects.select_for_update().get(pk=operation_id)
    require_actor(actor, "core.collect_payment", owner=operation.kind != "receipt")
    writes_allowed()
    if operation.tender == "card" or received is not True:
        raise ValidationError("Explicit actual receipt is required for a non-card tender.")
    return record_result(operation_id=operation.pk, state="succeeded", source="staff", actor=actor)
