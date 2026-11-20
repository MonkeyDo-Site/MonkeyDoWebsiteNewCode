"""Owner import of an already completed correction. Never sends a financial POST."""

import uuid
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.db import transaction

from core.models import AuditEvent
from core.permissions import require_actor

from .amounts import COMPONENTS, ZERO, amount
from .gateway import Gateway, reference
from .ledger import (
    checked_allocation,
    enabled,
    lock_request,
    lock_sale,
    record_result,
    request_operation,
)
from .models import PaymentOperation
from .operations import observe, verify_transaction


@transaction.atomic
def record_correction(
    *,
    actor,
    original_id,
    kind,
    allocation,
    request_key,
    provider_reference="",
    received_on=None,
    confirmed=False,
):
    enabled()
    require_actor(actor, "core.review_payment", owner=True)
    require_actor(actor, "core.collect_payment", owner=True)
    if confirmed is not True or kind not in {"refund", "void"}:
        raise ValidationError(
            "Explicitly confirm the correction already completed outside this website."
        )
    key = lock_request(request_key)
    original_sale = PaymentOperation.objects.only("sale_id").get(
        pk=original_id, state="succeeded", kind="receipt"
    )
    lock_sale(original_sale.sale_id)
    original = (
        PaymentOperation.objects.select_for_update(of=("self",))
        .select_related("sale")
        .get(
            pk=original_id,
            state="succeeded",
            kind="receipt",
        )
    )
    if kind == "void" and original.tender != "card":
        raise ValidationError("Only a card transaction can have a provider void.")
    cleaned = checked_allocation(original.sale, allocation)
    value = sum((amount(row[component]) for row in cleaned for component in COMPONENTS), ZERO)
    existing = PaymentOperation.objects.filter(request_key=key).first()
    if existing:
        if (
            existing.original_id != original.pk
            or existing.kind != kind
            or existing.allocation != cleaned
            or existing.provider_reference != str(provider_reference)
        ):
            raise ValidationError("This correction key already identifies a different action.")
        return existing
    evidence = None
    if original.tender == "card":
        provider_reference = reference(provider_reference)
        lock_request(
            uuid.uuid5(
                uuid.NAMESPACE_URL, "monkeydo:sandbox:correction:" + provider_reference + ":" + kind
            )
        )
        if PaymentOperation.objects.filter(
            tender="card", kind=kind, provider_reference=provider_reference
        ).exists():
            raise ValidationError(
                "This provider correction has already been recorded. Open the existing record."
            )
        evidence = Gateway().transaction(provider_reference)
        candidate = SimpleNamespace(pk=uuid.uuid4(), amount=value, kind=kind, original=original)
        verify_transaction(candidate, evidence)
    operation = request_operation(
        actor=actor,
        sale_id=original.sale_id,
        request_key=key,
        tender=original.tender,
        kind=kind,
        allocation=cleaned,
        original_id=original.pk,
        method_id=original.method_id,
        purpose="correction",
        received_on=received_on if original.tender != "card" else None,
    )
    when = None
    if evidence is not None:
        _, when = observe(operation, evidence)
    result = record_result(
        operation_id=operation.pk,
        state="succeeded",
        source="owner_dashboard",
        provider_reference=provider_reference,
        occurred_at=when,
        actor=actor,
        code="external_correction_verified" if evidence is not None else "manual_refund_confirmed",
    )
    AuditEvent.objects.create(
        actor=actor,
        action="payment.external_correction_recorded",
        record_type="payment",
        record_id=str(result.pk),
        changes={"original_id": str(original.pk), "amount": str(value), "kind": kind},
    )
    return result
