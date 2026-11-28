"""Known, unreconciled provider returns pause use of membership funding.

The original receipt and any credit application remain historical facts. These
checks never post a correction or change an existing booking's saved price.
"""

from django.db.models import Q


def flagged_receipts():
    from .models import PaymentOperation

    return PaymentOperation.objects.filter(
        Q(events__code="external_correction_review")
        | Q(observations__provider_status__in=["external_credit", "voided", "returned"]),
        kind="receipt",
        tender="card",
    ).distinct()


def direct_review_members(member_id=None):
    from .membership_cancellations import unrecorded_provider_return

    sources = flagged_receipts().filter(sale__membership_invoice__isnull=False)
    if member_id is not None:
        sources = sources.filter(sale__membership_invoice__installment__purchase_id=member_id)
    return {
        source.sale.membership_invoice.installment.purchase_id
        for source in sources.select_related("sale__membership_invoice__installment")
        if unrecorded_provider_return(source)
    }


def sale_needs_review(sale):
    from .customer_credit import held_on
    from .membership_cancellations import unrecorded_provider_return

    return held_on(sale) or any(
        unrecorded_provider_return(source) for source in flagged_receipts().filter(sale=sale)
    )


def member_needs_review(member, *, on=None):
    from .membership_renewal_review import parents_needing_review

    return bool(_held_source_members(member.pk) or parents_needing_review(member, on=on))


def held_members(member_id=None, *, on=None):
    from .membership_renewal_review import reviews

    return _held_source_members(member_id) | {
        review["member"].pk for review in reviews(member_id=member_id, on=on)
    }


def _held_source_members(member_id=None):
    from .customer_credit import source_on_hold
    from .customer_credit_records import CustomerCreditAllocation

    sources = flagged_receipts().filter(
        credit_issues__applications__application__sale__membership_invoice__isnull=False
    )
    if member_id is not None:
        sources = sources.filter(
            credit_issues__applications__application__sale__membership_invoice__installment__purchase_id=member_id
        )
    held = [source.pk for source in sources if source_on_hold(source)]
    allocations = CustomerCreditAllocation.objects.filter(
        issue__original_id__in=held,
        application__sale__membership_invoice__isnull=False,
    )
    if member_id is not None:
        allocations = allocations.filter(
            application__sale__membership_invoice__installment__purchase_id=member_id
        )
    return direct_review_members(member_id) | set(
        allocations.values_list(
            "application__sale__membership_invoice__installment__purchase_id", flat=True
        )
    )
