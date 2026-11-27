"""Persistent read-only membership payment attention, including unissued dues."""

from django.db.models import Case, DecimalField, F, OuterRef, Q, Subquery, Sum, Value, When
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast, Coalesce
from django.utils import timezone

from .membership_records import MembershipInstallment
from .membership_sales import today
from .models import FinancialLineAdjustment, FinancialPosting
from .payments.amounts import ZERO


def affected_bookings(member):
    return (
        member.benefit_assignments.filter(
            current__status="reserved",
            booking__attendance="",
            booking__setup_pending=False,
            booking__session__ends_at__gt=timezone.now(),
        )
        .values("booking_id")
        .distinct()
    )


def installment_balances(*, on=None, due_only=True):
    currency = DecimalField(max_digits=14, decimal_places=2)
    posted = (
        FinancialPosting.objects.filter(
            operation__sale_id=OuterRef("invoice__sale_id"), operation__state="succeeded"
        )
        .order_by()
        .values("operation__sale_id")
        .annotate(
            value=Sum(
                Case(
                    When(
                        operation__kind="receipt",
                        then=F("net") + F("fee") + F("item_tax") + F("fee_tax"),
                    ),
                    default=-(F("net") + F("fee") + F("item_tax") + F("fee_tax")),
                    output_field=currency,
                )
            )
        )
        .values("value")
    )
    adjustments = (
        FinancialLineAdjustment.objects.filter(line__sale_id=OuterRef("invoice__sale_id"))
        .order_by()
        .values("line__sale_id")
        .annotate(value=Sum(F("net") + F("fee") + F("item_tax") + F("fee_tax")))
        .values("value")
    )
    from .customer_credit_records import CustomerCreditAllocation

    credits = (
        CustomerCreditAllocation.objects.filter(application__sale_id=OuterRef("invoice__sale_id"))
        .order_by()
        .values("application__sale_id")
        .annotate(value=Sum("amount"))
        .values("value")
    )
    dues = (
        MembershipInstallment.objects.all()
        .exclude(purchase__purpose="complimentary")
        .exclude(
            Q(purchase__billing_state__stopped_on__isnull=False)
            & Q(cycle__starts_on__gte=F("purchase__billing_state__stopped_on"))
        )
        .annotate(
            paid_amount=Coalesce(
                Subquery(posted, output_field=currency), Value(ZERO), output_field=currency
            ),
            credited_amount=Coalesce(
                Subquery(credits, output_field=currency), Value(ZERO), output_field=currency
            ),
            adjusted_total=Coalesce(
                F("invoice__sale__total"), Cast(KeyTextTransform("total", "quote"), currency)
            )
            + Coalesce(
                Subquery(adjustments, output_field=currency), Value(ZERO), output_field=currency
            ),
        )
        .filter(
            Q(invoice__isnull=True) | Q(paid_amount__lt=F("adjusted_total") - F("credited_amount"))
        )
        .select_related("purchase__customer", "purchase__membership", "invoice__sale")
        .order_by("due_on", "purchase_id", "number")
    )
    if due_only:
        dues = dues.filter(due_on__lte=on or today())
    return dues


def payment_notices():
    result = []
    for item in installment_balances()[:20]:
        item.remaining = item.adjusted_total - item.paid_amount - item.credited_amount
        item.affected_bookings = affected_bookings(item.purchase).count()
        item.issue_label = "Installment due"
        if getattr(item, "invoice", None) is not None:
            states = set(item.invoice.sale.operations.values_list("state", flat=True))
            if states & {"unknown", "action"}:
                item.issue_label = "Check payment outcome"
            elif states & {"ready", "sending"}:
                item.issue_label = "Payment processing"
            elif "declined" in states:
                item.issue_label = "Payment declined"
        result.append(item)
    return result
