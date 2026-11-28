"""Explicit, backed credit funding for a staff-assisted initial purchase."""

from django.core.exceptions import PermissionDenied, ValidationError

from .payments.amounts import ZERO, amount


def review(*, actor, customer, value, comped):
    chosen = ZERO if value is None else amount(value)
    if chosen < ZERO:
        raise ValidationError("Enter a nonnegative customer credit amount.")
    if not chosen:
        return None
    if actor is None:
        raise PermissionDenied
    from .membership_sales import authorize

    authorize(actor, collect=True)
    if comped:
        raise ValidationError("No customer credit is needed for a complimentary membership.")
    from .customer_credit import available_issues

    sources = available_issues(customer.pk)
    available = sum((source.remaining for source in sources), ZERO)
    if chosen > available:
        raise ValidationError("The selected credit exceeds the customer's available balance.")
    return dict(
        amount=str(chosen),
        available=str(available),
        sources=[dict(id=str(source.pk), remaining=str(source.remaining)) for source in sources],
    )


def apply(*, actor, member, plan):
    from .customer_credit import apply as apply_credit
    from .customer_credit import review as review_credit

    first = member.installments.first()
    values = dict(
        actor=actor,
        member_id=member.pk,
        installment_id=first.pk,
        value=plan["amount"],
        remaining_tender=member.membership.expected_method,
    )
    current = review_credit(**values)
    if current["issues"] != plan["sources"]:
        raise ValidationError("The credit sources changed. Review the purchase again.")
    import uuid

    return apply_credit(
        **values,
        request_key=uuid.uuid5(member.request_key, "initial-customer-credit"),
        reviewed=current["fingerprint"],
        confirmed=True,
    )
