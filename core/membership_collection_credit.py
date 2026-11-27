"""Exact system credit allocation backed by an accepted scheduled claim."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from .customer_credit import available_issues, issue_balances, source_on_hold
from .customer_credit_records import CustomerCreditAllocation, CustomerCreditApplication
from .models import AuditEvent, Customer, FinancialLineAdjustment
from .payments.amounts import ZERO, amount
from .pricing import money


def sources(claim):
    left, result = amount(claim.details["credit_to_apply"]), {}
    for row in claim.details["credit_sources"]:
        used = min(left, amount(row["remaining"]))
        if used:
            result[row["id"]] = used
            left -= used
        if not left:
            break
    if left:
        raise PermissionDenied
    return result


def restore_projection(claim, invoice, plan, *, before_credit):
    """Compare live funds to the accepted plan before our own allocation only."""
    sale = invoice.sale
    lines = list(sale.lines.all())
    if len(lines) != 1:
        raise PermissionDenied
    line = lines[0]
    application = sale.credit_applications.filter(scheduled_claim=claim).first()
    credit = amount(claim.details["credit_to_apply"])
    adjustments = list(FinancialLineAdjustment.objects.filter(line__sale=sale))
    if before_credit:
        if sale.credit_applications.exists() or adjustments or sale.operations.exists():
            raise ValidationError(
                "The scheduled invoice is no longer ready for its credit allocation."
            )
        return plan
    if sale.credit_applications.exclude(pk=application.pk if application else None).exists():
        raise ValidationError("Another customer credit application requires payment review.")
    if credit:
        if (
            not application
            or application.actor_id is not None
            or application.pk != claim.credit_key
            or application.customer_id != sale.customer_id
            or application.amount != credit
            or application.fingerprint != claim.fingerprint
            or application.details != claim.details
        ):
            raise ValidationError(
                "The scheduled credit application does not match its accepted scope."
            )
        expected = sources(claim)
        restored = {}
        for row in application.allocations.select_related("issue__original__sale"):
            key = str(row.issue_id)
            if (
                row.amount != expected.get(key)
                or row.allocation
                != [
                    dict(
                        line=str(line.pk),
                        net=str(row.amount),
                        fee="0.00",
                        item_tax="0.00",
                        fee_tax="0.00",
                    )
                ]
                or source_on_hold(row.issue.original)
            ):
                raise ValidationError("The scheduled credit source needs owner review.")
            restored[key] = row.amount
        if restored != expected:
            raise ValidationError("The scheduled credit allocation is incomplete.")
        live = {str(row.pk): row.remaining for row in available_issues(sale.customer_id)}
        for key, used in restored.items():
            live[key] = live.get(key, ZERO) + used
        ordered = issue_balances().filter(customer_id=sale.customer_id, pk__in=live)
        plan["credit_sources"] = [
            dict(id=str(row.pk), remaining=str(live[str(row.pk)])) for row in ordered
        ]
        available = sum(live.values(), ZERO)
        principal = amount(claim.details["principal_due"])
        chosen = min(principal, available)
        remainder = principal - chosen
        fee = money(remainder * sale.fee_rate)
        plan.update(
            principal_due=str(principal),
            credit_available=str(available),
            credit_to_apply=str(chosen),
            remaining_principal=str(remainder),
            card_fee=str(fee),
            card_total=str(remainder + fee),
        )
    elif application or plan["status"] == "paid":
        raise ValidationError("This scheduled installment has other funding to review.")
    fee_delta = amount(claim.details["card_fee"]) - sale.processing_fee
    if fee_delta:
        if len(adjustments) != 1:
            raise ValidationError("The scheduled fee adjustment requires review.")
        delta = adjustments[0]
        if (
            delta.scheduled_claim_id != claim.pk
            or delta.actor_id is not None
            or delta.line_id != line.pk
            or delta.request_key != claim.credit_key
            or delta.reason != "credit_application"
            or delta.fee != fee_delta
            or delta.net
            or delta.item_tax
            or delta.fee_tax
        ):
            raise ValidationError("The scheduled fee adjustment does not match its credit.")
    elif adjustments:
        raise ValidationError("Another invoice adjustment requires review.")
    return plan


@transaction.atomic
def apply_scheduled_credit(value):
    from .membership_collection_authority import current_claim, prepared_invoice
    from .membership_reservations import lock_customer
    from .payments.ledger import lock_request

    claim = current_claim(value)
    Customer.objects.select_for_update(no_key=True).get(pk=claim.details["customer"])
    lock_customer(claim.details["customer"])
    lock_request(claim.credit_key)
    claim, invoice = prepared_invoice(claim, before_credit=True)
    credit = amount(claim.details["credit_to_apply"])
    if not credit:
        raise ValidationError("This scheduled installment has no credit to apply.")
    line = invoice.sale.lines.get()
    fee_delta = amount(claim.details["card_fee"]) - invoice.sale.processing_fee
    if fee_delta:
        FinancialLineAdjustment.objects.create(
            request_key=claim.credit_key,
            line=line,
            reason="credit_application",
            fee=fee_delta,
            actor=None,
            scheduled_claim=claim,
        )
    application = CustomerCreditApplication.objects.create(
        id=claim.credit_key,
        customer_id=claim.details["customer"],
        sale=invoice.sale,
        amount=credit,
        fingerprint=claim.fingerprint,
        details=claim.details,
        actor=None,
        scheduled_claim=claim,
    )
    available = {str(row.pk): row for row in available_issues(application.customer_id)}
    for key, used in sources(claim).items():
        issue = available.get(key)
        if not issue or issue.remaining < used:
            raise ValidationError("The scheduled credit source changed before allocation.")
        CustomerCreditAllocation.objects.create(
            application=application,
            issue=issue,
            amount=used,
            allocation=[
                dict(line=str(line.pk), net=str(used), fee="0.00", item_tax="0.00", fee_tax="0.00")
            ],
        )
    prepared_invoice(claim)
    AuditEvent.objects.create(
        actor=None,
        action="customer.credit_applied",
        record_type="membership",
        record_id=str(invoice.installment.purchase_id),
        changes={
            "application": str(application.pk),
            "amount": str(credit),
            "installment": claim.installment_id,
            "scheduled_claim": str(claim.pk),
        },
    )
    return application
