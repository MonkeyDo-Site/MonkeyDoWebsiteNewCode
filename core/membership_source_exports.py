"""Actual conditional-arrival receipts, returns and applications, without new money twice."""

from django.db.models import DecimalField, OuterRef, Prefetch, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from .membership_exports import CONTACT, contact, stamp
from .membership_records import MembershipArrivalReceipt, MembershipArrivalReceiptReturn
from .payments.amounts import ZERO

IDENTITY = [
    "membership",
    *CONTACT,
    "booking",
    "arrival_intent",
    "current_arrival_status",
    "current_arrival_code",
    "first_membership_payment_state",
    "source_receipt_id",
    "tender",
    "environment",
    "currency",
    "source_received_on",
    "source_sender",
]


def sources(records, *, history=False):
    returned = (
        MembershipArrivalReceiptReturn.objects.filter(receipt_id=OuterRef("pk"))
        .order_by()
        .values("receipt_id")
        .annotate(total=Sum("amount"))
        .values("total")
    )
    query = (
        MembershipArrivalReceipt.objects.filter(intent__purchase_id__in=records.values("pk"))
        .annotate(
            export_returned=Coalesce(
                Subquery(returned),
                Value(ZERO),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )
        )
        .select_related(
            "intent__purchase__membership",
            "intent__purchase__customer",
            "intent__progress",
            "intent__operation__sale",
            "intent__closure",
            "application__operation",
        )
        .order_by("created_at", "pk")
    )
    if history:
        query = query.prefetch_related(
            Prefetch(
                "returns",
                queryset=MembershipArrivalReceiptReturn.objects.order_by("created_at", "pk"),
            )
        )
    return query.iterator(chunk_size=500)


def identity(source):
    intent = source.intent
    state = getattr(intent, "progress", None)
    return [
        intent.purchase.membership_number,
        *contact(intent.purchase.customer),
        intent.booking_id,
        str(intent.pk),
        state.status if state else "review",
        state.code if state else "",
        intent.operation.state,
        str(source.pk),
        source.tender,
        intent.operation.sale.environment,
        intent.operation.sale.currency,
        source.received_on,
        source.sender,
    ]


def source_rows(records):
    """One row per original receipt; applied money is not an additional receipt."""
    yield [
        *IDENTITY,
        "money_originally_received",
        "unused_money_actually_returned",
        "original_money_applied_to_visit_invoice",
        "unapplied_source_balance",
        "source_actor_id",
        "source_recorded_at_new_york",
        "visit_application_transaction_id",
        "visit_application_state",
        "arrival_stopped_at_new_york",
        "separately_recorded_membership_cancellation_id",
    ]
    for source in sources(records):
        returned = source.export_returned
        application = getattr(source, "application", None)
        operation = application.operation if application else None
        applied = operation.amount if operation else ZERO
        closure = getattr(source.intent, "closure", None)
        yield [
            *identity(source),
            source.amount,
            returned,
            applied,
            source.amount - returned - applied,
            source.actor_id,
            stamp(source.created_at),
            str(operation.pk) if operation else "",
            operation.state if operation else "",
            stamp(closure.created_at) if closure else "",
            str(closure.cancellation_id or "") if closure else "",
        ]


def source_event_rows(records):
    """Each receipt/actual return/application is distinct, with additive money columns."""
    yield [
        *IDENTITY,
        "event_kind",
        "event_id",
        "money_received",
        "unused_money_actually_returned",
        "original_money_applied_to_visit_invoice",
        "event_received_or_returned_on",
        "event_recorded_at_new_york",
        "event_actor_id",
        "visit_application_transaction_id",
        "visit_application_state",
    ]
    for source in sources(records, history=True):
        common = identity(source)
        yield [
            *common,
            "receipt",
            str(source.pk),
            source.amount,
            ZERO,
            ZERO,
            source.received_on,
            stamp(source.created_at),
            source.actor_id,
            "",
            "",
        ]
        for returned in source.returns.all():
            yield [
                *common,
                "return",
                str(returned.pk),
                ZERO,
                returned.amount,
                ZERO,
                returned.completed_on,
                stamp(returned.created_at),
                returned.actor_id,
                "",
                "",
            ]
        application = getattr(source, "application", None)
        if application:
            operation = application.operation
            yield [
                *common,
                "invoice_application",
                str(operation.pk),
                ZERO,
                ZERO,
                operation.amount,
                operation.manual_received_on,
                stamp(operation.completed_at),
                operation.actor_id,
                str(operation.pk),
                operation.state,
            ]
