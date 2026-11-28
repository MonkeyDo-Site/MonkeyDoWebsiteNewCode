"""Read recorded receipt evidence without collecting or inventing bank information."""

import uuid
from decimal import Decimal

from django.apps import apps
from django.db import connection


def receipt_evidence(operations):
    """Bulk metadata for known manual receipts; absent evidence stays absent.

    Older reviewed schemas may lack later membership tables. Normal card/payment
    pages must still work there. Earlier-receipt applications are identified so
    an invoice posting is not described as newly received money.
    """
    manual = {
        operation.pk: operation
        for operation in operations
        if operation.kind == "receipt"
        and operation.state == "succeeded"
        and operation.tender != "card"
    }
    if not manual:
        return {}
    with connection.cursor() as cursor:
        tables = set(connection.introspection.table_names(cursor))
    result = {}

    def records(name):
        model = apps.get_model("core", name)
        return model.objects if model._meta.db_table in tables else None

    def earlier(query):
        for link in query:
            source = link.receipt
            result[link.operation_id] = dict(
                origin="Earlier receipt applied",
                earlier=True,
                received_on=source.received_on,
                sender=source.sender,
                receipt_id=str(source.pk),
                source_actor_id=source.actor_id,
                source_recorded_at=source.created_at,
            )

    for name in (
        "ZelleApplication",
        "MembershipBankAllocation",
        "MembershipArrivalReceiptApplication",
    ):
        query = records(name)
        if query is not None:
            earlier(query.filter(operation_id__in=manual).select_related("receipt"))
    query = records("MembershipRenewalBatchBank")
    if query is not None:
        first = {
            operation.sale.membership_invoice.installment.purchase.request_key: operation
            for operation in manual.values()
            if operation.tender == "zelle"
            and operation.sale.kind == "membership"
            and operation.sale.membership_invoice.installment.number == 1
        }
        for source in (
            query.filter(batch__parts__purchase_id__in=first)
            .select_related("batch")
            .distinct()
            .prefetch_related("batch__parts")
        ):
            for part in source.batch.parts.all():
                operation = first.get(part.purchase_id)
                if operation is None or operation.request_key != uuid.uuid5(
                    part.purchase_id, "first-payment"
                ):
                    continue
                result[operation.pk] = dict(
                    origin="Shared bank transfer allocation",
                    earlier=False,
                    received_on=source.received_on,
                    sender=source.sender,
                    shared_bank_receipt=str(source.pk),
                    shared_bank_total=source.amount,
                    shared_bank_actor_id=source.batch.actor_id,
                    shared_bank_recorded_at=source.created_at,
                )
    query = records("MembershipPaidVisitManualPayment")
    if query is not None:
        by_key = {operation.request_key: operation.pk for operation in manual.values()}
        for record in query.filter(operation_id__in=by_key).select_related("operation"):
            result[by_key[record.operation_id]] = dict(
                origin="Received replacement payment",
                earlier=False,
                received_on=record.operation.manual_received_on,
                sender=record.facts.get("sender", ""),
                receipt_id="",
            )
    combined = {}
    for operation in manual.values():
        if operation.pk in result or operation.sale.kind != "membership":
            continue
        invoice = operation.sale.membership_invoice
        item = invoice.installment
        if item.number != 1:
            continue
        member = item.purchase
        if operation.tender == "zelle" and operation.request_key == uuid.uuid5(
            member.request_key, "first-payment"
        ):
            combined[member.pk] = operation
        plan = item.quote.get("initial_split", {})
        if operation.request_key != uuid.uuid5(
            member.request_key, "first-payment:" + operation.tender
        ):
            continue
        part = next(
            (part for part in plan.get("parts", []) if part["tender"] == operation.tender), None
        )
        if part:
            result[operation.pk] = dict(
                origin="Received first payment",
                earlier=False,
                received_on=operation.manual_received_on,
                sender=part.get("sender", ""),
                receipt_id="",
            )
    query = records("MembershipArrivalCheckout")
    if combined and query is not None:
        for checkout in query.filter(purchase_id__in=combined):
            operation = combined[checkout.purchase_id]
            bank = checkout.facts.get("membership_zelle", {})
            if bank and Decimal(bank["amount"]) == operation.amount:
                result[operation.pk] = dict(
                    origin="Received membership Zelle",
                    earlier=False,
                    received_on=operation.manual_received_on,
                    sender=bank.get("sender", ""),
                    receipt_id="",
                )
    return result
