"""One financial event per recorded fact, even when a visit had several applications."""

from decimal import Decimal
from itertools import batched
from uuid import UUID

from django.db import connection

from .customer_credit_records import CustomerCreditAllocation, VisitMembershipConversion
from .membership_exports import CONTACT, contact, stamp
from .membership_paid_visit_records import (
    MembershipPaidVisitIntent,
    MembershipPaidVisitManualPayment,
)
from .models import FinancialLineAdjustment, FinancialSale, PaymentOperation
from .payment_receipt_evidence import receipt_evidence
from .payments.amounts import COMPONENTS, ZERO

MONEY = (
    "original_visit_invoice_funds",
    "original_visit_money_returned",
    "original_processing_fee_recorded",
    "original_processing_fee_retained",
    "new_membership_money_received",
    "new_membership_money_returned",
    "new_membership_processing_fee_received",
    "earlier_receipt_applied_to_membership",
    "converted_credit_created",
    "converted_principal",
    "reversed_item_tax",
    "reversed_fee_tax",
    "converted_credit_applied_to_membership",
    "unused_card_fee_removed",
    "uncollected_membership_amount_cancelled",
)
HEADERS = (
    "memberships",
    *CONTACT,
    "booking",
    "source_invoice",
    "environment",
    "currency",
    "event_kind",
    "event_reference",
    "transaction_id",
    "original_transaction_id",
    "state",
    "tender",
    "requested_amount",
    *MONEY,
    "actual_receipt_or_return_on",
    "recorded_at_new_york",
    "recorded_by_id",
    "receipt_origin",
    "recorded_sender",
    "earlier_receipt_reference",
    "earlier_receipt_recorded_by_id",
    "earlier_receipt_recorded_at_new_york",
)


def paid_visit_rows(records):
    """History for matching memberships; original invoice funds are not new income.

    Source invoices are deduplicated across stopped/retried membership purchases.
    Credit and fee adjustments have their own columns, never received-money cells.
    Bank metadata comes only from recorded evidence, not the customer's profile.
    """
    yield HEADERS
    with connection.cursor() as cursor:
        tables = set(connection.introspection.table_names(cursor))
    conversions = list(
        VisitMembershipConversion.objects.filter(purchase_id__in=records.values("pk"))
        .select_related("purchase__membership", "purchase__customer")
        .prefetch_related("credits")
        .order_by("created_at", "pk")
    )
    intents = (
        list(
            MembershipPaidVisitIntent.objects.filter(purchase_id__in=records.values("pk"))
            .select_related(
                "purchase__membership", "purchase__customer", "release__cancellation_decision"
            )
            .order_by("created_at", "pk")
        )
        if MembershipPaidVisitIntent._meta.db_table in tables
        else []
    )
    groups, member_sources, new_purchases = {}, {}, set()

    def link(sale_id, record):
        source = UUID(str(sale_id))
        member = record.purchase
        group = groups.setdefault(
            source,
            dict(source=source, customer=member.customer, booking=record.booking_id, members=set()),
        )
        group["members"].add(member.membership_number)
        if any(
            key in member.membership.snapshot for key in ("paid_visit_card", "paid_visit_purchase")
        ):
            new_purchases.add(member.pk)
            member_sources[member.pk] = group
        return group

    for intent in intents:
        link(intent.source_sale_id, intent)
    for conversion in conversions:
        link(conversion.details["sale"], conversion)

    def row(group, kind, reference, **changes):
        values = dict.fromkeys(MONEY, ZERO)
        values.update(
            memberships="; ".join(sorted(group["members"])),
            **dict(zip(CONTACT, contact(group["customer"]), strict=True)),
            booking=group["booking"],
            source_invoice=str(group["source"]),
            environment=group.get("environment", ""),
            currency=group.get("currency", ""),
            event_kind=kind,
            event_reference=kind + ":" + str(reference),
        )
        values.update(changes)
        return [values.get(key, "") for key in HEADERS]

    def transactions(operations, *, source):
        for batch in batched(operations.iterator(chunk_size=500), 500):
            evidence = receipt_evidence(batch)
            for operation in batch:
                if source:
                    group = groups[operation.sale_id]
                else:
                    group = member_sources[
                        operation.sale.membership_invoice.installment.purchase_id
                    ]
                parts = {
                    key: sum((getattr(posting, key) for posting in operation.postings.all()), ZERO)
                    if operation.state == "succeeded"
                    else ZERO
                    for key in COMPONENTS
                }
                actual = sum(parts.values(), ZERO)
                meta = evidence.get(operation.pk, {})
                amounts = {}
                if operation.kind == "receipt":
                    amounts[
                        "original_visit_invoice_funds"
                        if source
                        else (
                            "earlier_receipt_applied_to_membership"
                            if meta.get("earlier")
                            else "new_membership_money_received"
                        )
                    ] = actual
                    if source:
                        amounts["original_processing_fee_recorded"] = parts["fee"]
                    elif not meta.get("earlier"):
                        amounts["new_membership_processing_fee_received"] = parts["fee"]
                else:
                    amounts[
                        "original_visit_money_returned"
                        if source
                        else "new_membership_money_returned"
                    ] = actual
                yield row(
                    group,
                    "original_visit_transaction" if source else "membership_transaction",
                    operation.pk,
                    transaction_id=str(operation.pk),
                    original_transaction_id=str(operation.original_id or ""),
                    state=operation.state,
                    tender=operation.tender,
                    requested_amount=operation.amount,
                    actual_receipt_or_return_on=operation.manual_received_on,
                    recorded_at_new_york=stamp(operation.completed_at or operation.requested_at),
                    recorded_by_id=operation.actor_id,
                    receipt_origin=meta.get("origin", ""),
                    recorded_sender=meta.get("sender", ""),
                    earlier_receipt_reference=meta.get("receipt_id", ""),
                    earlier_receipt_recorded_by_id=meta.get("source_actor_id", ""),
                    earlier_receipt_recorded_at_new_york=stamp(meta.get("source_recorded_at")),
                    **amounts,
                )

    def operations(query):
        return (
            query.select_related("sale__membership_invoice__installment__purchase__membership")
            .prefetch_related("postings")
            .order_by("requested_at", "pk")
        )

    for sources in batched(groups, 500):
        for sale in FinancialSale.objects.filter(pk__in=sources).values(
            "pk", "environment", "currency"
        ):
            groups[sale["pk"]].update(environment=sale["environment"], currency=sale["currency"])
        yield from transactions(
            operations(PaymentOperation.objects.filter(sale_id__in=sources)), source=True
        )
    if new_purchases:
        yield from transactions(
            operations(
                PaymentOperation.objects.filter(
                    sale__membership_invoice__installment__purchase_id__in=new_purchases,
                    sale__membership_invoice__installment__number=1,
                )
            ),
            source=False,
        )

    for intent in intents:
        group = groups[intent.source_sale_id]
        yield row(
            group,
            "visit_funds_reserved",
            intent.pk,
            recorded_at_new_york=stamp(intent.created_at),
            recorded_by_id=intent.actor_id,
        )
        released = getattr(intent, "release", None)
        if released:
            cancelled = getattr(released, "cancellation_decision", None)
            yield row(
                group,
                "visit_funds_" + released.kind,
                intent.pk,
                recorded_at_new_york=stamp(released.created_at),
                recorded_by_id=released.actor_id,
                uncollected_membership_amount_cancelled=cancelled.facts["uncollected"]
                if cancelled
                else ZERO,
            )

    converted = {conversion.pk: conversion for conversion in conversions}
    for conversion in conversions:
        group = groups[UUID(conversion.details["sale"])]
        yield row(
            group,
            "visit_admissions_converted",
            conversion.pk,
            original_processing_fee_retained=Decimal(conversion.details["retained_fee"]),
            recorded_at_new_york=stamp(conversion.created_at),
            recorded_by_id=conversion.actor_id,
        )
        for issue in conversion.credits.all():
            parts = {
                key: sum((Decimal(part[key]) for part in issue.allocation), ZERO)
                for key in COMPONENTS
            }
            yield row(
                group,
                "visit_credit_created",
                issue.pk,
                original_transaction_id=str(issue.original_id),
                converted_credit_created=issue.amount,
                converted_principal=parts["net"],
                reversed_item_tax=parts["item_tax"],
                reversed_fee_tax=parts["fee_tax"],
                recorded_at_new_york=stamp(issue.created_at),
                recorded_by_id=conversion.actor_id,
            )
    allocations = (
        CustomerCreditAllocation.objects.filter(
            issue__conversion_id__in=converted,
            application__sale__membership_invoice__installment__purchase_id__in=records.values(
                "pk"
            ),
        )
        .select_related("issue", "application")
        .order_by("pk")
    )
    for allocation in allocations.iterator(chunk_size=500):
        conversion = converted[allocation.issue.conversion_id]
        yield row(
            groups[UUID(conversion.details["sale"])],
            "visit_credit_applied",
            allocation.pk,
            original_transaction_id=str(allocation.issue.original_id),
            converted_credit_applied_to_membership=allocation.amount,
            recorded_at_new_york=stamp(allocation.application.created_at),
            recorded_by_id=allocation.application.actor_id,
        )

    if MembershipPaidVisitManualPayment._meta.db_table in tables:
        plans = MembershipPaidVisitManualPayment.objects.filter(
            intent__purchase_id__in=new_purchases
        ).select_related("intent")
        for batch in batched(plans.iterator(chunk_size=500), 500):
            adjustments = {
                (str(adjustment.request_key), str(adjustment.line_id)): adjustment
                for adjustment in FinancialLineAdjustment.objects.filter(
                    request_key__in=[plan.facts["fee_key"] for plan in batch]
                )
            }
            for plan in batch:
                adjustment = adjustments.get((plan.facts["fee_key"], plan.facts["line"]))
                if adjustment:
                    yield row(
                        groups[plan.intent.source_sale_id],
                        "unused_card_fee_removed",
                        adjustment.pk,
                        unused_card_fee_removed=-adjustment.fee,
                        recorded_at_new_york=stamp(adjustment.created_at),
                        recorded_by_id=adjustment.actor_id,
                    )
