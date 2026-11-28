"""Explicit, audited CSV exports for the currently filtered membership records."""

import csv
import io
import tempfile
import uuid
from itertools import batched

from django import forms
from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch
from django.http import FileResponse
from django.shortcuts import render
from django.views.decorators.http import require_safe

from .availability import NEW_YORK
from .membership_records import MembershipBenefitAssignment, MembershipBenefitEvent
from .models import AuditEvent, PaymentOperation
from .pagination import paginate
from .payments.amounts import COMPONENTS, ZERO
from .permissions import require_actor, staff_permission

REPORTS = {
    "memberships": "Memberships",
    "payments": "Payment transactions",
    "benefits": "Benefit usage",
    "arrival_funds": "Arrival funds",
    "arrival_fund_events": "Arrival fund history",
    "paid_visit_events": "Paid visit application history",
}
CONTACT = ["customer_id", "last_name", "current_phone", "current_email"]


def cell(value):
    """Untrusted customer text must stay text in spreadsheet applications."""
    if value is None:
        return ""
    if isinstance(value, str) and (
        value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@"))
        or value.startswith(("\t", "\r", "\n"))
    ):
        return "'" + value
    return value


def stamp(value):
    return value.astimezone(NEW_YORK).isoformat() if value else ""


def contact(customer):
    return [customer.customer_number, customer.last_name, customer.phone, customer.email]


def membership_rows(records):
    yield [
        "membership",
        *CONTACT,
        "type",
        "places",
        "starts_on",
        "original_ends_on",
        "effective_ends_on",
        "billing",
        "status",
        "recorded_at_new_york",
    ]
    for member in records.iterator(chunk_size=500):
        root = member.membership
        yield [
            member.membership_number,
            *contact(member.customer),
            root.get_kind_display(),
            root.places,
            root.starts_on,
            root.ends_on,
            member.effective_ends_on,
            "Complimentary" if member.purpose == "complimentary" else root.get_billing_display(),
            member.report_status,
            stamp(member.accepted_at),
        ]


def payment_rows(records):
    yield [
        "membership",
        *CONTACT,
        "installment",
        "due_on",
        "service_at_new_york",
        "environment",
        "currency",
        "transaction_id",
        "original_transaction_id",
        "kind",
        "tender",
        "state",
        "requested_amount",
        "recorded_principal",
        "recorded_processing_fee",
        "recorded_item_tax",
        "recorded_fee_tax",
        "recorded_total",
        "requested_at_new_york",
        "manual_received_on",
        "completed_at_new_york",
        "latest_reported_settlement_date",
        "provider_observed_at_new_york",
        "receipt_origin",
        "recorded_sender",
        "earlier_receipt_reference",
        "earlier_receipt_recorded_by_id",
        "earlier_receipt_recorded_at_new_york",
        "shared_bank_receipt_reference",
        "shared_bank_total_reference_only",
        "shared_bank_receipt_recorded_by_id",
        "shared_bank_receipt_recorded_at_new_york",
    ]
    operations = PaymentOperation.objects.filter(
        sale__membership_invoice__installment__purchase_id__in=records.values("pk")
    )
    operations = (
        operations.select_related(
            "sale__customer", "sale__membership_invoice__installment__purchase__membership"
        )
        .prefetch_related("postings", "observations")
        .order_by("requested_at", "pk")
    )
    from .payment_receipt_evidence import receipt_evidence

    for batch in batched(operations.iterator(chunk_size=500), 500):
        evidence = receipt_evidence(batch)
        for operation in batch:
            installment = operation.sale.membership_invoice.installment
            parts = {
                key: sum((getattr(posting, key) for posting in operation.postings.all()), ZERO)
                if operation.state == "succeeded"
                else ZERO
                for key in COMPONENTS
            }
            observed = max(
                operation.observations.all(),
                key=lambda row: (row.observed_at, row.pk),
                default=None,
            )
            yield [
                installment.purchase.membership_number,
                *contact(operation.sale.customer),
                installment.number,
                installment.due_on,
                stamp(operation.sale.service_at),
                operation.sale.environment,
                operation.sale.currency,
                str(operation.pk),
                str(operation.original_id or ""),
                operation.kind,
                operation.tender,
                operation.state,
                operation.amount,
                *[parts[key] for key in COMPONENTS],
                sum(parts.values(), ZERO),
                stamp(operation.requested_at),
                operation.manual_received_on,
                stamp(operation.completed_at),
                observed.settled_date if observed else "",
                stamp(observed.observed_at) if observed else "",
                evidence.get(operation.pk, {}).get("origin", ""),
                evidence.get(operation.pk, {}).get("sender", ""),
                evidence.get(operation.pk, {}).get("receipt_id", ""),
                evidence.get(operation.pk, {}).get("source_actor_id", ""),
                stamp(evidence.get(operation.pk, {}).get("source_recorded_at")),
                evidence.get(operation.pk, {}).get("shared_bank_receipt", ""),
                evidence.get(operation.pk, {}).get("shared_bank_total", ""),
                evidence.get(operation.pk, {}).get("shared_bank_actor_id", ""),
                stamp(evidence.get(operation.pk, {}).get("shared_bank_recorded_at")),
            ]


def benefit_rows(records):
    yield [
        "membership",
        *CONTACT,
        "booking",
        "assignment_id",
        "anonymous_place",
        "benefit",
        "appointment_on",
        "membership_month_starts",
        "membership_month_ends",
        "admission_price",
        "current_state",
        "reserved_at_new_york",
        "state_recorded_at_new_york",
        "event_state",
        "event_recorded_at_new_york",
        "event_reason",
    ]
    assignments = MembershipBenefitAssignment.objects.filter(purchase_id__in=records.values("pk"))
    assignments = (
        assignments.select_related(
            "purchase__membership",
            "purchase__customer",
            "cycle",
            "reserved_by",
            "current__event__batch",
        )
        .prefetch_related(
            Prefetch(
                "events",
                queryset=MembershipBenefitEvent.objects.select_related("batch").order_by("pk"),
            )
        )
        .order_by("appointment_on", "booking_id", "pk")
    )
    for row in assignments.iterator(chunk_size=500):
        state = getattr(row, "current", None)
        values = [
            row.purchase.membership_number,
            *contact(row.purchase.customer),
            row.booking_id,
            str(row.pk),
            row.place,
            row.kind,
            row.appointment_on,
            row.cycle.starts_on,
            row.cycle.ends_on,
            row.price,
            state.status if state else "review",
            stamp(row.reserved_by.recorded_at),
            stamp(state.event.batch.recorded_at) if state else "",
        ]
        for event in row.events.all():
            yield [*values, event.batch.action, stamp(event.batch.recorded_at), event.batch.reason]


def export_response(request, records, form):
    from .membership_paid_visit_exports import paid_visit_rows
    from .membership_source_exports import source_event_rows, source_rows

    require_actor(request.user, "core.export_membership_records")
    report = request.POST.get("report")
    if report not in REPORTS:
        raise PermissionDenied
    if report == "payments":
        require_actor(request.user, "core.view_paymentoperation")
    if report == "benefits":
        require_actor(request.user, "core.view_booking")
    if report in {"arrival_funds", "arrival_fund_events", "paid_visit_events"}:
        require_actor(request.user, "core.view_booking")
        require_actor(request.user, "core.view_paymentoperation")
    makers = {
        "memberships": membership_rows,
        "payments": payment_rows,
        "benefits": benefit_rows,
        "arrival_funds": source_rows,
        "arrival_fund_events": source_event_rows,
        "paid_visit_events": paid_visit_rows,
    }
    document = tempfile.SpooledTemporaryFile(max_size=1024 * 1024, mode="w+b")
    text = io.TextIOWrapper(document, encoding="utf-8-sig", newline="")
    try:
        writer = csv.writer(text)
        count = -1
        for row in makers[report](records):
            writer.writerow([cell(value) for value in row])
            count += 1
        text.flush()
        text.detach()
        document.seek(0)
        AuditEvent.objects.create(
            actor=request.user,
            action="membership.export_prepared",
            record_type="membership_export",
            record_id=str(uuid.uuid4()),
            changes=dict(
                report=REPORTS[report],
                rows=count,
                filters={
                    key: str(value)
                    for key, value in form.cleaned_data.items()
                    if value not in (None, "")
                },
            ),
        )
        response = FileResponse(
            document,
            as_attachment=True,
            filename=f"MonkeyDo-{report}.csv",
            content_type="text/csv; charset=utf-8",
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
    except BaseException:
        document.close()
        raise


@staff_permission("core.view_membershippurchase")
@staff_permission("core.view_customer")
@require_safe
def history(request):
    require_actor(request.user, "core.view_membershippurchase", owner=True)
    from .active_membership_views import check_enabled
    from .membership_reporting import MembershipFilters

    check_enabled()
    events = paginate(
        request,
        AuditEvent.objects.filter(
            record_type="membership_export", action="membership.export_prepared"
        )
        .select_related("actor")
        .order_by("-created_at", "-pk"),
    )
    fields = MembershipFilters().fields
    for event in events:
        event.filter_rows = []
        for key, value in event.changes.get("filters", {}).items():
            if key not in fields:
                continue
            field = fields[key]
            if isinstance(field, forms.ChoiceField):
                value = dict(field.choices).get(value, value)
            event.filter_rows.append((field.label or key.replace("_", " ").capitalize(), value))
    return render(request, "core/membership_export_history.html", {"events": events})
