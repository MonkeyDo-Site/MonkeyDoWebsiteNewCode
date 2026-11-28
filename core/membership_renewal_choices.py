"""Bounded renewal choices after removing already committed original places."""

import re

from django.core.exceptions import ValidationError
from django.db.models import F, IntegerField, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from .membership_records import MembershipPurchase
from .membership_renewals import committed_renewals, renewal_details

PAGE_SIZE = 10
MAX_ENTRIES = 100


def candidates(customer_id, *, query="", cursor=None, exclude=()):
    committed = (
        committed_renewals()
        .filter(prior_id=OuterRef("pk"))
        .order_by()
        .values("prior_id")
        .annotate(total=Sum("places"))
        .values("total")
    )
    rows = (
        MembershipPurchase.objects.filter(customer_id=customer_id)
        .annotate(_renewed=Coalesce(Subquery(committed), Value(0), output_field=IntegerField()))
        .filter(membership__places__gt=F("_renewed"))
        .exclude(billing_state__stopped_on__lte=F("membership__starts_on"))
    )
    if query:
        number = re.fullmatch(r"#?[mM]?(\d+)", query.strip())
        rows = (
            rows.filter(pk=int(number[1]))
            if number
            else rows.filter(membership__kind__icontains=query.strip())
        )
    if exclude:
        rows = rows.exclude(pk__in=exclude)
    if cursor:
        previous = (
            MembershipPurchase.objects.select_related("membership")
            .filter(pk=cursor, customer_id=customer_id)
            .first()
        )
        if previous is None:
            raise ValidationError("Search again to refresh the membership list.")
        end = previous.membership.ends_on
        rows = rows.filter(
            Q(membership__ends_on__gt=end) | Q(membership__ends_on=end, pk__gt=previous.pk)
        )
    return rows.select_related("membership", "billing_state__mandate").order_by(
        "membership__ends_on", "pk"
    )


def page(customer_id, *, query="", cursor=None, exclude=(), limit=None):
    limit = min(PAGE_SIZE if limit is None else limit, MAX_ENTRIES)
    if limit < 1:
        return [], [], None
    rows = candidates(customer_id, query=query, cursor=cursor, exclude=exclude)
    choices, unavailable, last = [], [], None
    for member in rows.iterator(chunk_size=50):
        last = member.pk
        try:
            details = renewal_details(member)
        except ValidationError as error:
            if len(unavailable) < 20:
                unavailable.append((member, " ".join(error.messages)))
            continue
        # Recheck the live budget; the annotation is only a listing filter.
        if details["available_places"]:
            choices.append((member, details))
        if len(choices) == limit:
            break
    more = bool(
        last and candidates(customer_id, query=query, cursor=last, exclude=exclude).exists()
    )
    return choices, unavailable, last if more else None


def initial(member, details):
    return dict(
        prior_id=member.pk,
        kind=member.membership.kind,
        places=details["available_places"],
        months=details["minimum_months"],
        billing=member.membership.billing,
        method_id=str(member.billing_state.mandate.method_id)
        if member.billing_state.mandate
        else "",
    )
