"""Explicit cohort additions and renewals. No automatic term extension or repricing."""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db.models import F, Sum

from .membership_calendar import renewal_start
from .membership_records import MembershipOrigin


def effective_expiry(member):
    stop = member.billing_state.stopped_on
    try:
        return (
            min(member.membership.ends_on, stop - timedelta(days=1))
            if stop
            else member.membership.ends_on
        )
    except OverflowError:
        raise ValidationError("Review the original membership effective end date.") from None


def remaining_places(member):
    committed = (
        MembershipOrigin.objects.filter(prior=member, operation="renewal")
        .exclude(purchase__billing_state__stopped_on__lte=F("purchase__membership__starts_on"))
        .aggregate(n=Sum("places"))["n"]
        or 0
    )
    return max(0, member.membership.places - committed)


def renewal_details(member, *, on=None):
    from .membership_reservations import payment_current
    from .membership_sales import today

    on = on or today()
    root = member.membership
    expiry = effective_expiry(member)
    if expiry < root.starts_on:
        raise ValidationError(
            "This membership ended before it began. Start a new purchase instead."
        )
    if not payment_current(member):
        raise ValidationError(
            "Resolve the original membership payment before renewing. Existing payments and terms have not changed."
        )
    starts_on, minimum = renewal_start(expiry, on)
    return dict(
        prior_id=member.pk,
        customer_id=member.customer_id,
        kind=root.kind,
        places=root.places,
        available_places=remaining_places(member),
        starts_on=starts_on,
        ends_on=expiry,
        minimum_months=minimum,
    )
