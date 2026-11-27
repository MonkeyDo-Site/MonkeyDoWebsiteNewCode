"""Effective unpaid invoice components; adjustments never count as cash receipts."""

from django.core.exceptions import ValidationError
from django.db import transaction

from core.models import AuditEvent
from core.permissions import require_actor
from core.pricing import money

from .amounts import COMPONENTS, ZERO, allocate
from .models import FinancialLineAdjustment


def effective_components(sale):
    result = {}
    for line in sale.lines.prefetch_related("adjustments"):
        values = {
            key: getattr(line, key)
            + sum((getattr(delta, key) for delta in line.adjustments.all()), ZERO)
            for key in COMPONENTS
        }
        if any(value < ZERO for value in values.values()):
            raise ValidationError("Invoice adjustments require owner reconciliation.")
        result[str(line.pk)] = values
    return result


def total(sale):
    return sum(
        (value for parts in effective_components(sale).values() for value in parts.values()), ZERO
    )


def received(sale):
    value = ZERO
    for op in sale.operations.filter(state="succeeded").prefetch_related("postings"):
        sign = 1 if op.kind == "receipt" else -1
        value += sign * sum(
            (getattr(posting, key) for posting in op.postings.all() for key in COMPONENTS), ZERO
        )
    return value


def settled(sale):
    """Funding assigned to this invoice; converted money is not assigned twice."""
    from core.customer_credit import applied, transferred

    return received(sale) + applied(sale) - transferred(sale)


def noncard_components(sale):
    from .ledger import RESERVED, used_components

    if sale.operations.filter(
        tender="card", state__in=["ready", "sending", "unknown", "action"]
    ).exists():
        raise ValidationError("Reconcile the uncertain card outcome before changing its tender.")
    used = used_components(sale.operations.filter(kind="receipt", state__in=RESERVED))
    current = effective_components(sale)
    lines = list(sale.lines.all())
    retained_fees = [used.get(str(line.pk), {}).get("fee", ZERO) for line in lines]
    taxable_base = sum((current[str(line.pk)]["net"] for line in lines if line.taxable), ZERO)
    taxable_fee = sum((fee for line, fee in zip(lines, retained_fees) if line.taxable), ZERO)
    target_tax = money((taxable_base + taxable_fee) * sale.tax_rate)
    weights = []
    for line, fee in zip(lines, retained_fees):
        weights.extend(
            [current[str(line.pk)]["net"] if line.taxable else ZERO, fee if line.taxable else ZERO]
        )
    taxes = allocate(target_tax, weights)
    result = {}
    for position, line in enumerate(lines):
        values = current[str(line.pk)]
        taken = used.get(str(line.pk), {})
        desired = {
            "net": values["net"],
            "fee": retained_fees[position],
            "item_tax": taxes[2 * position],
            "fee_tax": taxes[2 * position + 1],
        }
        if any(desired[component] < taken.get(component, ZERO) for component in COMPONENTS):
            raise ValidationError("The original received tax or fee requires owner reconciliation.")
        result[str(line.pk)] = desired
    return result


@transaction.atomic
def remove_unpaid_card_fee(*, actor, sale_id, request_key):
    """After a definitive failed card portion, changing to noncard removes only unused fees."""
    from .ledger import enabled, lock_request, lock_sale

    enabled()
    require_actor(actor, "core.collect_payment")
    key = lock_request(request_key)
    sale = lock_sale(sale_id)
    if FinancialLineAdjustment.objects.filter(request_key=key, line__sale=sale).exists():
        return sale
    if FinancialLineAdjustment.objects.filter(request_key=key).exists():
        raise ValidationError("This adjustment request already belongs to another invoice.")
    if sale.operations.filter(
        tender="card", state__in=["ready", "sending", "unknown", "action"]
    ).exists():
        raise ValidationError("Reconcile the uncertain card outcome before changing its tender.")
    current = effective_components(sale)
    desired = noncard_components(sale)
    for line in sale.lines.all():
        delta = {
            component: desired[str(line.pk)][component] - current[str(line.pk)][component]
            for component in COMPONENTS
        }
        if any(delta.values()):
            FinancialLineAdjustment.objects.create(
                request_key=key, line=line, reason="tender_change", **delta, actor=actor
            )
    AuditEvent.objects.create(
        actor=actor,
        action="payment.unpaid_card_fee_removed",
        record_type="sale",
        record_id=str(sale.pk),
        changes={"adjustment_key": str(key)},
    )
    return sale
