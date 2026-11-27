"""Owner-only changes to unused backed credit, with bounded restoration."""

import uuid

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import DecimalField, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from .customer_credit import available_issues, balance, held_balance, source_on_hold
from .customer_credit_records import CustomerCreditCorrection, CustomerCreditCorrectionAllocation
from .membership_reservations import lock_customer
from .membership_sales import authorize
from .models import AuditEvent, Customer
from .payments.amounts import ZERO, amount
from .payments.ledger import fingerprint, lock_request, writes_allowed
from .permissions import require_actor


def owner(actor):
    authorize(actor, collect=True)
    require_actor(actor, "core.review_payment", owner=True)


def restorables(customer_id):
    currency = DecimalField(max_digits=14, decimal_places=2)
    removed = (
        CustomerCreditCorrectionAllocation.objects.filter(correction_id=OuterRef("pk"))
        .order_by()
        .values("correction_id")
        .annotate(total=Sum("amount"))
        .values("total")
    )
    restored = (
        CustomerCreditCorrectionAllocation.objects.filter(correction__original_id=OuterRef("pk"))
        .order_by()
        .values("correction__original_id")
        .annotate(total=Sum("amount"))
        .values("total")
    )
    return (
        CustomerCreditCorrection.objects.filter(customer_id=customer_id, kind="remove")
        .annotate(
            unrestored=Coalesce(
                Subquery(removed, output_field=currency), Value(ZERO), output_field=currency
            )
            - Coalesce(
                Subquery(restored, output_field=currency), Value(ZERO), output_field=currency
            )
        )
        .filter(unrestored__gt=0)
        .order_by("-created_at", "-pk")
    )


def restoration_sources(customer_id, original_id):
    try:
        key = uuid.UUID(str(original_id))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Choose a previous removal for this customer.") from None
    original = CustomerCreditCorrection.objects.filter(
        pk=key, customer_id=customer_id, kind="remove"
    ).first()
    if original is None:
        raise ValidationError("Choose a previous removal for this customer.")
    sources = []
    for row in original.allocations.select_related("issue__original").order_by(
        "issue__created_at", "issue_id"
    ):
        restored = (
            CustomerCreditCorrectionAllocation.objects.filter(
                correction__original=original, issue=row.issue
            ).aggregate(total=Sum("amount"))["total"]
            or ZERO
        )
        left = row.amount - restored
        if left:
            sources.append(
                dict(
                    issue=str(row.issue_id),
                    available=str(left),
                    held=source_on_hold(row.issue.original),
                )
            )
    return original, sources


def review(*, actor, customer_id, kind, value, original_id=None):
    owner(actor)
    customer = Customer.objects.get(pk=customer_id)
    chosen = amount(value)
    if chosen <= ZERO or kind not in {"remove", "restore"}:
        raise ValidationError("Choose removal or restoration and a positive exact amount.")
    original = None
    if kind == "remove":
        if original_id is not None:
            raise ValidationError("A new removal cannot restore an earlier correction.")
        sources = [
            dict(issue=str(issue.pk), available=str(issue.remaining), held=False)
            for issue in available_issues(customer_id)
        ]
    else:
        original, sources = restoration_sources(customer_id, original_id)
    maximum = sum((amount(source["available"]) for source in sources), ZERO)
    if chosen > maximum:
        raise ValidationError(
            "The amount exceeds available unused credit."
            if kind == "remove"
            else "The amount exceeds what remains unrestored from that removal."
        )
    left = chosen
    plans = []
    for source in sources:
        part = min(left, amount(source["available"]))
        if part:
            plans.append(source | dict(amount=str(part)))
            left -= part
        if not left:
            break
    before, held = balance(customer_id), held_balance(customer_id)
    restored_available = sum((amount(plan["amount"]) for plan in plans if not plan["held"]), ZERO)
    restored_held = chosen - restored_available
    data = dict(
        customer=customer_id,
        customer_revision=customer.revision,
        kind=kind,
        amount=str(chosen),
        original=str(original.pk) if original else None,
        maximum=str(maximum),
        before_available=str(before),
        after_available=str(before - chosen if kind == "remove" else before + restored_available),
        before_held=str(held),
        after_held=str(held if kind == "remove" else held + restored_held),
        sources=sources,
        plans=plans,
    )
    return data | dict(fingerprint=fingerprint(data))


@transaction.atomic
def correct(
    *,
    actor,
    customer_id,
    kind,
    value,
    reviewed,
    request_key,
    reason,
    original_id=None,
    confirmed=False,
):
    owner(actor)
    writes_allowed()
    key = lock_request(request_key)
    cleaned_reason = reason.strip() if isinstance(reason, str) else ""
    if not cleaned_reason or len(cleaned_reason) > 500:
        raise ValidationError("Record a reason for this credit correction.")
    original_key = None
    if original_id is not None:
        try:
            original_key = str(uuid.UUID(str(original_id)))
        except (ValueError, TypeError, AttributeError):
            raise ValidationError("Choose a valid original removal.") from None
    identity = fingerprint(
        dict(
            customer=customer_id,
            kind=kind,
            value=str(amount(value)),
            original=original_key,
            reviewed=reviewed,
            reason=cleaned_reason,
        )
    )
    previous = CustomerCreditCorrection.objects.filter(pk=key).first()
    if previous:
        if previous.actor_id != actor.pk or previous.fingerprint != identity:
            raise ValidationError("This correction key already identifies a different action.")
        return previous
    if confirmed is not True:
        raise ValidationError("Confirm the reviewed credit correction.")
    lock_customer(customer_id)
    data = review(
        actor=actor, customer_id=customer_id, kind=kind, value=value, original_id=original_key
    )
    if data["fingerprint"] != reviewed:
        raise ValidationError("The customer credit changed. Review the current correction again.")
    record = CustomerCreditCorrection.objects.create(
        id=key,
        customer_id=customer_id,
        kind=kind,
        original_id=original_key,
        amount=amount(data["amount"]),
        reason=cleaned_reason,
        fingerprint=identity,
        details=data,
        actor=actor,
    )
    for plan in data["plans"]:
        CustomerCreditCorrectionAllocation.objects.create(
            correction=record, issue_id=plan["issue"], amount=plan["amount"]
        )
    AuditEvent.objects.create(
        actor=actor,
        action="customer.credit_removed" if kind == "remove" else "customer.credit_restored",
        record_type="customer",
        record_id=str(customer_id),
        changes=dict(
            correction=str(key),
            amount=data["amount"],
            reason=cleaned_reason,
            original=original_key,
            before_available=data["before_available"],
            after_available=data["after_available"],
            before_held=data["before_held"],
            after_held=data["after_held"],
        ),
    )
    return record
