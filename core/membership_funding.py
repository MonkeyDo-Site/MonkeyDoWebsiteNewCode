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
    from django.db.models import F

    from .customer_credit_records import CustomerCreditAllocation
    from .membership_cancellations import unrecorded_provider_return

    direct = "sale__membership_invoice__installment__purchase_id"
    converted = "credit_issues__applications__application__sale__membership_invoice__installment__purchase_id"
    scope = (
        Q(**{direct: member_id}) | Q(**{converted: member_id})
        if member_id is not None
        else Q(**{direct + "__isnull": False}) | Q(**{converted + "__isnull": False})
    )
    sources = flagged_receipts().filter(scope).annotate(review_member_id=F(direct))
    held = [source for source in sources if unrecorded_provider_return(source)]
    members = {
        source.review_member_id
        for source in held
        if source.review_member_id is not None
        and (member_id is None or source.review_member_id == member_id)
    }
    if not held:
        return members
    allocations = CustomerCreditAllocation.objects.filter(
        issue__original_id__in=[source.pk for source in held],
        application__sale__membership_invoice__isnull=False,
    )
    if member_id is not None:
        allocations = allocations.filter(
            application__sale__membership_invoice__installment__purchase_id=member_id
        )
    return members | set(
        allocations.values_list(
            "application__sale__membership_invoice__installment__purchase_id", flat=True
        )
    )
