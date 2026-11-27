"""Spend backed customer funds once; cash receipts and credit stay distinct."""

from decimal import Decimal
from itertools import islice

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import DecimalField, F, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from .customer_credit_records import (
    CustomerCreditAllocation,
    CustomerCreditApplication,
    CustomerCreditCorrectionAllocation,
    CustomerCreditIssue,
)
from .membership_payments import member_record
from .membership_reservations import lock_customer
from .membership_sales import authorize, invoice_for, today
from .models import AuditEvent, FinancialLineAdjustment, PaymentEvent
from .payments.amounts import COMPONENTS, ZERO, amount
from .payments.ledger import RESERVED, fingerprint, lock_request, used_components, writes_allowed
from .pricing import money


def issue_balances():
    currency = DecimalField(max_digits=14, decimal_places=2)

    def summed(query):
        return Coalesce(
            Subquery(
                query.order_by().values("issue_id").annotate(total=Sum("amount")).values("total"),
                output_field=currency,
            ),
            Value(ZERO),
            output_field=currency,
        )

    return (
        CustomerCreditIssue.objects.annotate(
            spent=summed(CustomerCreditAllocation.objects.filter(issue_id=OuterRef("pk"))),
            removed=summed(
                CustomerCreditCorrectionAllocation.objects.filter(
                    issue_id=OuterRef("pk"), correction__kind="remove"
                )
            ),
            restored=summed(
                CustomerCreditCorrectionAllocation.objects.filter(
                    issue_id=OuterRef("pk"), correction__kind="restore"
                )
            ),
        )
        .annotate(remaining=F("amount") - F("spent") - F("removed") + F("restored"))
        .select_related("original__sale")
        .order_by("created_at", "pk")
    )


def unspent_issues(customer_id):
    return issue_balances().filter(customer_id=customer_id, remaining__gt=0)


def source_on_hold(original):
    if original.tender != "card":
        return False
    from .membership_cancellations import unrecorded_provider_return

    return unrecorded_provider_return(original)


def available_issues(customer_id):
    return [issue for issue in unspent_issues(customer_id) if not source_on_hold(issue.original)]


def held_balance(customer_id):
    return sum(
        (
            issue.remaining
            for issue in unspent_issues(customer_id)
            if source_on_hold(issue.original)
        ),
        ZERO,
    )


def held_on(sale):
    originals = {}
    for allocation in CustomerCreditAllocation.objects.filter(
        application__sale=sale
    ).select_related("issue__original"):
        originals[allocation.issue.original_id] = allocation.issue.original
    return any(source_on_hold(original) for original in originals.values())


def hold_notices():
    issues = (
        CustomerCreditIssue.objects.filter(original__events__code="external_correction_review")
        .select_related("original", "customer")
        .distinct()
        .order_by("created_at", "pk")
    )
    return list(
        islice((issue for issue in issues.iterator() if source_on_hold(issue.original)), 20)
    )


def balance(customer_id):
    return sum((issue.remaining for issue in available_issues(customer_id)), ZERO)


def expiry_notices():
    from django.db.models import Q

    candidates = (
        issue_balances()
        .filter(
            Q(conversion__purchase__membership__ends_on__lt=today())
            | Q(conversion__purchase__billing_state__stopped_on__lte=today()),
            remaining__gt=0,
        )
        .select_related("customer", "original", "conversion__purchase__membership")
        .order_by("created_at", "pk")
    )
    return list(
        islice((issue for issue in candidates.iterator() if not source_on_hold(issue.original)), 20)
    )


def applied_components(sale):
    return used_components(CustomerCreditAllocation.objects.filter(application__sale=sale))


def transferred_components(original):
    return used_components(original.credit_issues.all())


def applied(sale):
    return (
        CustomerCreditAllocation.objects.filter(application__sale=sale).aggregate(
            value=Sum("amount")
        )["value"]
        or ZERO
    )


def transferred(sale):
    return (
        CustomerCreditIssue.objects.filter(original__sale=sale).aggregate(value=Sum("amount"))[
            "value"
        ]
        or ZERO
    )


def protect_source(original, allocation):
    issued = transferred_components(original)
    reversed_parts = used_components(original.adjustments.filter(state__in=RESERVED))
    limits = {row["line"]: row for row in original.allocation}
    for row in allocation:
        for component in COMPONENTS:
            if amount(row[component]) + issued.get(row["line"], {}).get(
                component, ZERO
            ) + reversed_parts.get(row["line"], {}).get(component, ZERO) > amount(
                limits.get(row["line"], {}).get(component, ZERO)
            ):
                raise ValidationError(
                    "These original funds were converted to customer credit or already returned. They cannot also be refunded."
                )


def review(*, actor, member_id, installment_id, value=None):
    authorize(actor, collect=True)
    member = member_record(member_id)
    item = (
        member.installments.select_related("cycle", "invoice__sale")
        .filter(pk=installment_id)
        .first()
    )
    if item is None or member.purpose == "complimentary":
        raise ValidationError("Choose an unpaid installment of this membership.")
    if item.due_on > today() or (
        member.billing_state.stopped_on and item.cycle.starts_on >= member.billing_state.stopped_on
    ):
        raise ValidationError(
            "Use an installment that is due and remains part of the accepted membership."
        )
    from .membership_funding import member_needs_review

    if member_needs_review(member):
        raise ValidationError(
            "A membership payment or credit source needs owner reconciliation before another allocation or payment."
        )
    sale = item.invoice.sale if hasattr(item, "invoice") else None
    operations = list(sale.operations.order_by("requested_at", "pk")) if sale else []
    if any(
        op.state in {"sending", "unknown", "action"} or op.kind != "receipt" for op in operations
    ):
        raise ValidationError(
            "Reconcile the existing payment or correction before applying credit."
        )
    from .payments.invoices import effective_components

    if sale:
        current = effective_components(sale)
        if len(current) != 1:
            raise ValidationError("Review the combined invoice before applying customer credit.")
        components = next(iter(current.values()))
        paid = next(
            iter(used_components(op for op in operations if op.state == "succeeded").values()),
            {key: ZERO for key in COMPONENTS},
        )
        credit = next(iter(applied_components(sale).values()), {key: ZERO for key in COMPONENTS})
    else:
        components = dict(
            net=amount(item.quote["subtotal"]),
            fee=amount(item.quote["processing_fee"]),
            item_tax=ZERO,
            fee_tax=ZERO,
        )
        paid = credit = {key: ZERO for key in COMPONENTS}
    if components["item_tax"] or components["fee_tax"]:
        raise ValidationError(
            "Historical membership tax needs owner review before applying credit."
        )
    outstanding = components["net"] - paid["net"] - credit["net"]
    available = balance(member.customer_id)
    chosen = min(outstanding, available) if value is None else amount(value)
    if not ZERO < chosen <= min(outstanding, available):
        raise ValidationError(
            "Apply a positive amount within the available credit and unpaid membership amount."
        )
    rate = sale.fee_rate if sale else Decimal(item.quote["rates"]["card_fee_rate"])
    remaining_fee = money((outstanding - chosen) * rate)
    data = dict(
        membership=member.pk,
        installment=item.pk,
        number=item.number,
        billing_revision=member.billing_state.revision,
        customer_revision=member.customer.revision,
        invoice=str(sale.pk) if sale else None,
        available=str(available),
        amount=str(chosen),
        unpaid_net=str(outstanding),
        remaining_net=str(outstanding - chosen),
        target_fee=str(paid["fee"] + remaining_fee),
        remaining_card_fee=str(remaining_fee),
        remaining_card_total=str(outstanding - chosen + remaining_fee),
        operations=[dict(id=str(op.pk), state=op.state) for op in operations],
        credit_applications=list(
            sale.credit_applications.order_by("pk").values_list("id", flat=True)
        )
        if sale
        else [],
        issues=[
            dict(id=str(issue.pk), remaining=str(issue.remaining))
            for issue in available_issues(member.customer_id)
        ],
    )
    data["credit_applications"] = [str(key) for key in data["credit_applications"]]
    return data | dict(fingerprint=fingerprint(data))


@transaction.atomic
def apply(*, actor, member_id, installment_id, reviewed, request_key, value=None, confirmed=False):
    authorize(actor, collect=True)
    writes_allowed()
    key = lock_request(request_key)
    member = member_record(member_id)
    lock_customer(member.customer_id)
    identity = fingerprint(
        dict(
            member=member_id,
            installment=installment_id,
            reviewed=reviewed,
            value=str(amount(value)) if value is not None else None,
        )
    )
    prior = CustomerCreditApplication.objects.filter(pk=key).first()
    if prior:
        if prior.actor_id != actor.pk or prior.fingerprint != identity:
            raise ValidationError("This credit confirmation already identifies a different action.")
        return prior
    if confirmed is not True:
        raise ValidationError("Confirm the reviewed customer credit application.")
    data = review(actor=actor, member_id=member_id, installment_id=installment_id, value=value)
    if data["fingerprint"] != reviewed:
        raise ValidationError("The credit or payment changed. Review the current amounts again.")
    item = member.installments.get(pk=installment_id)
    invoice = invoice_for(
        item, actor=actor, tender=member.membership.expected_method if item.number == 1 else "card"
    )
    sale, line = invoice.sale, invoice.sale.lines.get()
    for op in sale.operations.select_for_update().filter(state="ready", kind="receipt"):
        op.state, op.result_code = "cancelled", "credit_before_dispatch"
        op.save(update_fields=["state", "result_code"])
        PaymentEvent.objects.create(
            operation=op,
            state="cancelled",
            source="staff",
            actor=actor,
            code="credit_before_dispatch",
        )
    from .payments.invoices import effective_components

    current = effective_components(sale)[str(line.pk)]
    fee_delta = amount(data["target_fee"]) - current["fee"]
    if fee_delta:
        FinancialLineAdjustment.objects.create(
            request_key=key, line=line, reason="credit_application", fee=fee_delta, actor=actor
        )
    application = CustomerCreditApplication.objects.create(
        id=key,
        customer=member.customer,
        sale=sale,
        amount=amount(data["amount"]),
        fingerprint=identity,
        details=data,
        actor=actor,
    )
    left = application.amount
    for issue in available_issues(member.customer_id):
        chosen = min(left, issue.remaining)
        if chosen:
            CustomerCreditAllocation.objects.create(
                application=application,
                issue=issue,
                amount=chosen,
                allocation=[
                    dict(
                        line=str(line.pk),
                        net=str(chosen),
                        fee="0.00",
                        item_tax="0.00",
                        fee_tax="0.00",
                    )
                ],
            )
            left -= chosen
        if not left:
            break
    if left:
        raise ValidationError("The customer credit changed; no application was recorded.")
    AuditEvent.objects.create(
        actor=actor,
        action="customer.credit_applied",
        record_type="membership",
        record_id=str(member.pk),
        changes=dict(application=str(key), amount=data["amount"], installment=item.pk),
    )
    # It is a payment allocation, not a successful-installment customer receipt.
    if item.number == 1:
        from .membership_sales import installment_paid, queue_confirmation

        if installment_paid(item):
            queue_confirmation(member)
    return application
