"""Read the accepted schedule and backed credit before preparing collection work.

This projection performs no provider I/O, records no funding and grants no worker
authority. A collection producer must revalidate it under the financial locks.
"""

from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError

from .customer_credit import available_issues, held_balance
from .membership_funding import member_needs_review
from .membership_records import MembershipInstallment
from .membership_reservations import payment_current
from .membership_sales import enabled, installment_paid, today
from .payments.amounts import ZERO, amount
from .payments.ledger import fingerprint
from .pricing import money

REASONS = {
    "initial_purchase": "The first payment belongs to the explicit purchase checkout.",
    "not_monthly": "This membership has no scheduled monthly card collection.",
    "not_due": "This installment is not due yet.",
    "past_due_review": "An earlier uncollected date needs explicit payment review.",
    "term_ended": "Review unpaid installments after the purchased term ends.",
    "cancelled_cycle": "This installment belongs to the cancelled part of the membership.",
    "funding_review": "A payment or credit source needs owner reconciliation.",
    "previous_unpaid": "Resolve earlier installments before automatic collection.",
    "parent_review": "The earlier membership needs review before collecting this renewal.",
    "existing_invoice": "An invoice or payment review already exists for this installment.",
    "card_unavailable": "The accepted membership card is unavailable.",
    "held_credit": "Customer credit needs source reconciliation before collection.",
    "quote_review": "The accepted installment price needs owner review.",
}


def installment_plan(installment_id, *, on=None):
    enabled()
    on = today() if on is None else on
    if type(on) is not date:
        raise ValidationError("Use a New York calendar date for installment planning.")
    item = MembershipInstallment.objects.select_related(
        "purchase__membership",
        "purchase__customer",
        "purchase__billing_state__mandate__method",
        "purchase__origin__prior__membership",
        "purchase__origin__prior__billing_state",
        "cycle",
        "invoice__sale",
    ).get(pk=installment_id)
    member, root = item.purchase, item.purchase.membership
    billing, reasons = member.billing_state, []

    def block(code):
        reasons.append(code)

    paid = installment_paid(item)
    if item.number == 1:
        block("initial_purchase")
    if root.billing != "monthly" or member.purpose == "complimentary":
        block("not_monthly")
    if item.due_on > on:
        block("not_due")
    elif item.due_on < on and not paid:
        # No automatic backfill of a missed date is enabled by this projection.
        block("past_due_review")
    if on > root.ends_on and not paid:
        block("term_ended")
    if billing.stopped_on and item.cycle.starts_on >= billing.stopped_on:
        block("cancelled_cycle")
    if member_needs_review(member):
        block("funding_review")
    previous = member.installments.filter(number__lt=item.number).select_related("invoice__sale")
    if any(not installment_paid(prior) for prior in previous):
        block("previous_unpaid")
    origin = getattr(member, "origin", None)
    if origin and origin.operation == "renewal" and not payment_current(origin.prior, on=on):
        block("parent_review")
    if hasattr(item, "invoice") and not paid:
        block("existing_invoice")
    mandate = billing.mandate
    method = mandate.method if mandate else None
    held = held_balance(member.customer_id)
    if held:
        block("held_credit")
    issues = available_issues(member.customer_id)
    available = sum((issue.remaining for issue in issues), ZERO)
    principal = credit = fee = remaining = ZERO
    try:
        net = amount(item.quote["subtotal"])
        rate = Decimal(item.quote["rates"]["card_fee_rate"])
        if (
            net <= ZERO
            or not rate.is_finite()
            or not ZERO <= rate <= Decimal("1")
            or amount(item.quote["sales_tax"]) != ZERO
            or amount(item.quote["processing_fee"]) != money(net * rate)
            or amount(item.quote["total"]) != net + money(net * rate)
        ):
            raise ValueError
        if not paid:
            principal = net
            credit = min(principal, available)
            remaining = principal - credit
            fee = money(remaining * rate)
    except (ValidationError, ValueError, TypeError, KeyError, InvalidOperation):
        block("quote_review")
    if not method or (
        method.customer_id != member.customer_id
        or method.environment != "sandbox"
        or (remaining > ZERO and (method.state != "active" or not method.provider_method))
    ):
        block("card_unavailable")
    data = dict(
        membership=member.pk,
        membership_number=root.membership_number,
        customer=member.customer_id,
        installment=item.pk,
        number=item.number,
        due_on=item.due_on.isoformat(),
        planned_on=on.isoformat(),
        billing_revision=billing.revision,
        mandate=str(mandate.pk) if mandate else None,
        method=str(method.pk) if method else None,
        quote_fingerprint=fingerprint(item.quote),
        principal_due=str(principal),
        credit_available=str(available),
        held_credit=str(held),
        credit_to_apply=str(credit),
        remaining_principal=str(remaining),
        card_fee=str(fee),
        card_total=str(remaining + fee),
        credit_sources=[dict(id=str(issue.pk), remaining=str(issue.remaining)) for issue in issues],
        status="paid" if paid else "review" if reasons else "ready_for_scheduling",
        reasons=reasons,
        messages=[REASONS[code] for code in reasons],
    )
    return data | {"fingerprint": fingerprint(data)}


def review_due(*, limit=20, include_overdue=False):
    enabled()
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValidationError("Use a limit between 1 and 100.")
    if type(include_overdue) is not bool:
        raise ValidationError("Choose whether to include overdue installments.")
    on = today()
    items = MembershipInstallment.objects.filter(
        number__gt=1,
        purchase__membership__billing="monthly",
        **({"due_on__lte": on} if include_overdue else {"due_on": on}),
    ).order_by("due_on", "purchase_id", "number")
    rows = [installment_plan(pk, on=on) for pk in items.values_list("pk", flat=True)[:limit]]
    return dict(
        read_only=True,
        date=on.isoformat(),
        rows=rows,
        ready=sum(row["status"] == "ready_for_scheduling" for row in rows),
        review=sum(row["status"] == "review" for row in rows),
        paid=sum(row["status"] == "paid" for row in rows),
    )
