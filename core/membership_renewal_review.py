"""Hold the unresolved early-prepaid/earlier-arrears case for owner review.

This is not a debt-transfer rule or a cancellation of the paid renewal. Original
receipts/terms and existing booking prices remain facts. An explicit booking
exception still follows the existing owner-only decision workflow.
"""

from django.db.models import F

from .membership_records import MembershipOrigin
from .membership_schema import available


def early_prepaid(member, origin):
    return bool(
        origin
        and origin.operation == "renewal"
        and member.purpose == "renewal"
        and member.membership.billing == "prepaid"
        and origin.purchased_on < member.membership.starts_on
    )


def unpaid_required(parent, on):
    from .membership_sales import installment_paid

    if parent.purpose == "complimentary":
        return False
    rows = (
        parent._prefetched_objects_cache.get("installments")
        if hasattr(parent, "_prefetched_objects_cache")
        else None
    )
    if rows is None:
        rows = list(parent.installments.select_related("cycle", "invoice__sale"))
    if not rows:
        return True
    stop = parent.billing_state.stopped_on
    return any(
        not installment_paid(item)
        for item in rows
        if item.number == 1 or (item.due_on <= on and (stop is None or item.cycle.starts_on < stop))
    )


def parents_needing_review(member, *, on=None):
    from .membership_sales import today

    if member.purpose != "renewal" or member.membership.billing != "prepaid":
        return []
    if not available("core_membershiporigin"):
        return []
    on = on or today()
    if not early_prepaid(member, getattr(member, "origin", None)) or unpaid_required(member, on):
        # This review concerns an independently funded renewal. An unconfirmed
        # first payment retains the ordinary pending-payment state and wording.
        return []
    result, visited = [], {member.pk}
    current = member
    while True:
        origin = getattr(current, "origin", None)
        if not early_prepaid(current, origin):
            break
        parent = origin.prior
        if parent.pk in visited:
            # Inconsistent lineage is never a reason to silently grant benefits.
            return result or [parent]
        visited.add(parent.pk)
        if unpaid_required(parent, on):
            result.append(parent)
        current = parent
    return result


def reviews(*, member_id=None, on=None, live_only=False):
    from .membership_sales import today

    if not available("core_membershiporigin"):
        return []
    on = on or today()
    origins = MembershipOrigin.objects.filter(
        operation="renewal",
        purchase__purpose="renewal",
        purchase__membership__billing="prepaid",
        purchase__membership__starts_on__gt=F("purchased_on"),
    )
    if member_id is not None:
        origins = origins.filter(purchase_id=member_id)
    if live_only:
        origins = origins.filter(purchase__membership__ends_on__gte=on).exclude(
            purchase__billing_state__stopped_on__lte=on
        )
    origins = origins.select_related(
        "purchase__membership",
        "purchase__customer",
        "purchase__billing_state",
        "prior__membership",
        "prior__billing_state",
    ).prefetch_related(
        "prior__installments__cycle",
        "prior__installments__invoice__sale",
        "purchase__installments__cycle",
        "purchase__installments__invoice__sale",
    )
    result = []
    for origin in origins:
        # Reuse the relation loaded for this source rather than fetching it again.
        origin.purchase.origin = origin
        parents = parents_needing_review(origin.purchase, on=on)
        if parents:
            result.append(dict(member=origin.purchase, parents=parents))
    return result
