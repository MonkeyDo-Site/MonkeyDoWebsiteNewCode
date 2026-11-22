"""Explicit collection of only a reviewed unpaid balance, never a full-order retry."""

import uuid

from django.core.exceptions import ValidationError
from django.db import transaction

from core.models import AuditEvent, Booking
from core.permissions import require_actor

from .amounts import COMPONENTS, ZERO
from .checkout import authorize, resolve_if_settled
from .invoices import effective_components, noncard_components, remove_unpaid_card_fee
from .jobs import enqueue
from .ledger import (
    RESERVED,
    fingerprint,
    lock_request,
    record_manual,
    request_operation,
    used_components,
)
from .models import BookingCheckout


def preview(
    *,
    actor,
    booking_id,
    method,
    context="follow_up",
    received_on=None,
    zelle_sender="",
    retry_declined=False,
):
    from .receipts import receipt_date, sender

    authorize(actor)
    if retry_declined:
        require_actor(actor, "core.collect_payment", owner=True)
        if method != "card":
            raise ValidationError("Retry uses the reviewed card on this booking.")
    if method not in {"card", "cash", "check", "zelle", "gift_card"} or context not in {
        "arrival",
        "follow_up",
    }:
        raise ValidationError("Choose the actual remaining-payment method and context.")
    booking = Booking.objects.select_related("customer", "session").get(
        pk=booking_id, workflow="integrated_v1"
    )
    if not booking.attendance:
        raise ValidationError(
            "Complete the reviewed arrival or fee action before collecting a remaining balance."
        )
    checkout = booking.checkouts.select_related("sale").order_by("-created_at").first()
    if checkout is None or checkout.sale is None:
        raise ValidationError("There is no reviewed balance to collect.")
    sale = checkout.sale
    if (
        retry_declined
        and not sale.operations.filter(kind="receipt", tender="card", state="declined").exists()
    ):
        raise ValidationError("There is no declined card payment to retry for this balance.")
    if sale.operations.filter(state__in=["ready", "sending", "unknown", "action"]).exists():
        raise ValidationError("Resolve the pending or uncertain payment before another attempt.")
    if (
        sale.operations.exclude(kind="receipt").exists()
        or sale.operations.filter(
            events__code="external_correction_review", followup__resolved_at__isnull=True
        ).exists()
    ):
        raise ValidationError(
            "An owner must review this corrected/refunded invoice before further collection."
        )
    desired = effective_components(sale) if method == "card" else noncard_components(sale)
    used = used_components(sale.operations.filter(kind="receipt", state__in=RESERVED))
    allocation = []
    for key, values in desired.items():
        remaining = {part: values[part] - used.get(key, {}).get(part, ZERO) for part in COMPONENTS}
        if any(value < ZERO for value in remaining.values()):
            raise ValidationError(
                "Owner review is needed to reconcile the previously received amounts."
            )
        allocation.append({"line": key, **{part: str(value) for part, value in remaining.items()}})
    value = sum(
        (
            sum((values[part] - used.get(key, {}).get(part, ZERO) for part in COMPONENTS), ZERO)
            for key, values in desired.items()
        ),
        ZERO,
    )
    if value <= ZERO:
        raise ValidationError("This reviewed balance is already settled.")
    method_id = None
    last_four = ""
    if method == "card":
        try:
            agreement = booking.card_agreement
        except Booking.card_agreement.RelatedObjectDoesNotExist:
            raise ValidationError(
                "Add a reviewed card for this booking before charging the remainder."
            ) from None
        if agreement.method.state != "active":
            raise ValidationError("Replace the saved card before collecting this balance.")
        method_id = agreement.method_id
        last_four = agreement.method.last_four
    purpose = (
        ("cancellation" if booking.attendance == "cancelled" else "no_show")
        if booking.attendance != "arrived"
        else context
    )
    received_on = receipt_date(received_on) if method != "card" else None
    zelle_sender = (
        sender(zelle_sender or booking.zelle_sender, required=True) if method == "zelle" else ""
    )
    facts = {
        "received_on": received_on.isoformat() if received_on else None,
        "zelle_sender": zelle_sender,
        "booking": booking.pk,
        "version": booking.edit_version,
        "sale": str(sale.pk),
        "method": method,
        "method_id": str(method_id) if method_id else None,
        "amount": str(value),
        "allocation": allocation,
        "purpose": purpose,
    }
    return booking, sale, facts, fingerprint(facts), last_four


@transaction.atomic
def confirm(
    *,
    actor,
    booking_id,
    method,
    context,
    request_key,
    reviewed_hash,
    confirmed,
    received_on=None,
    zelle_sender="",
    retry_declined=False,
):
    authorize(actor)
    if retry_declined:
        require_actor(actor, "core.collect_payment", owner=True)
    if confirmed is not True:
        raise ValidationError("Explicitly confirm the reviewed remaining payment.")
    key = lock_request(request_key)
    previous = BookingCheckout.objects.filter(request_key=key).first()
    if previous:
        if (
            previous.booking_id != booking_id
            or previous.actor_id != actor.pk
            or previous.kind != "payment"
            or previous.fingerprint != reviewed_hash
        ):
            raise ValidationError("This payment confirmation already identifies another action.")
        return previous
    Booking.objects.select_for_update().get(pk=booking_id)
    booking, sale, facts, digest, _ = preview(
        actor=actor,
        booking_id=booking_id,
        method=method,
        context=context,
        received_on=received_on,
        zelle_sender=zelle_sender,
        retry_declined=retry_declined,
    )
    if digest != reviewed_hash:
        raise ValidationError("The remaining balance or saved card changed. Review it again.")
    if method != "card":
        remove_unpaid_card_fee(actor=actor, sale_id=sale.pk, request_key=key)
    checkout = BookingCheckout.objects.create(
        request_key=key,
        fingerprint=digest,
        booking=booking,
        sale=sale,
        kind="payment",
        booking_version=booking.edit_version,
        details=facts,
        actor=actor,
    )
    operation = request_operation(
        actor=actor,
        sale_id=sale.pk,
        request_key=uuid.uuid5(key, "remainder"),
        tender=method,
        allocation=facts["allocation"],
        method_id=facts["method_id"],
        purpose=facts["purpose"],
        received_on=received_on if method != "card" else None,
    )
    if method == "card":
        enqueue(
            kind="payment_dispatch", reference=operation.pk, key="dispatch:" + str(operation.pk)
        )
    else:
        record_manual(actor=actor, operation_id=operation.pk, received=True)
    AuditEvent.objects.create(
        actor=actor,
        action="payment.remaining_balance_confirmed",
        record_type="booking",
        record_id=str(booking.reference),
        changes={"operation_id": str(operation.pk), "amount": facts["amount"], "tender": method},
    )
    resolve_if_settled(booking.pk)
    return checkout
