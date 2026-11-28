"""Optional renewal choices stay beside an existing, privately owned booking."""

import uuid
from datetime import datetime, time, timedelta
from datetime import timezone as dt_timezone

from django.conf import settings
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import BigIntegerField, F, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.urls import reverse

from .availability import NEW_YORK
from .membership_records import (
    MembershipOrigin,
    MembershipPromptLink,
    MembershipRenewalLink,
    MembershipRenewalPrompt,
)
from .membership_renewals import renewal_details
from .membership_reservations import lock_customer
from .membership_sales import enabled, today
from .models import AuditEvent
from .payments.ledger import fingerprint, writes_allowed

SALT = "booking-membership-renewal-choice"
ACTIONS = {"seen", "renew", "not_now", "email_later"}


def remind_at(on):
    try:
        return datetime.combine(on + timedelta(days=1), time(9), NEW_YORK)
    except OverflowError:
        raise ValidationError("The reminder date needs owner review.") from None


def provenance(customer, flow, source, actor):
    return fingerprint(
        dict(
            customer=customer.pk,
            revision=customer.revision,
            flow=str(flow["key"]),
            source=source,
            actor=actor.pk if actor else None,
        )
    )


def candidate_members(customer=None):
    from .membership_reporting import held_members, reporting_members

    renewed = (
        MembershipOrigin.objects.filter(prior_id=OuterRef("pk"), operation="renewal")
        .exclude(purchase__billing_state__stopped_on__lte=F("purchase__membership__starts_on"))
        .order_by()
        .values("prior_id")
        .annotate(n=Sum("places"))
        .values("n")
    )
    records = (
        reporting_members()
        .filter(
            Q(purpose="complimentary")
            | Q(_has_installments=True, _unpaid_first=False, _unpaid_due=False),
            billing_state__stopped_on__isnull=True,
            calendar_ends_on__lte=today() + timedelta(days=5),
        )
        .exclude(pk__in=held_members())
        .annotate(
            _renewed=Coalesce(
                Subquery(renewed, output_field=BigIntegerField()),
                Value(0),
                output_field=BigIntegerField(),
            )
        )
        .filter(_renewed__lt=F("membership__places"))
        .order_by("-calendar_ends_on", "-pk")
    )
    return records.filter(customer=customer) if customer is not None else records


def candidates(customer):
    return candidate_members(customer)[:100]


def opportunity(member, *, customer, flow, source, actor, pending_email=""):
    on, end = today(), member.current_membership.ends_on
    events = list(member.renewal_prompts.filter(ends_on=end))
    flow_key = uuid.UUID(str(flow["key"]))
    if any(event.flow_key == flow_key and event.action != "seen" for event in events):
        return None
    deferred = any(
        event.flow_key != flow_key
        and event.action in {"not_now", "email_later"}
        and event.window == "initial"
        for event in events
    )
    window = "followup" if deferred else "initial"
    if deferred and (on - end).days < 30:
        return None
    if any(
        event.window == "followup" and event.action == "seen" and event.flow_key != flow_key
        for event in events
    ):
        return None
    if (end - on).days > 5 or member.billing_state.stopped_on or member.cancellations.exists():
        return None
    try:
        details = renewal_details(member)
    except ValidationError:
        return None
    if not details["available_places"]:
        return None
    payload = dict(
        purchase=member.pk,
        customer=customer.pk,
        revision=customer.revision,
        flow=str(flow_key),
        source=source,
        actor=actor.pk if actor else None,
        provenance=provenance(customer, flow, source, actor),
        window=window,
        ends_on=end.isoformat(),
        on=on.isoformat(),
        places=details["available_places"],
        minimum=details["minimum_months"],
        can_email=bool(customer.email or pending_email),
        can_renew=source == "public"
        or actor.has_perms(["core.add_membershippurchase", "core.collect_payment"]),
    )
    when = remind_at(on)
    return dict(
        payload=payload,
        token=signing.dumps(payload, salt=SALT),
        kind=member.membership.get_kind_display(),
        places=details["available_places"],
        ends_on=end,
        expired=end < on,
        minimum=details["minimum_months"],
        remind_at=when,
        reminder_after_grace=(when.date() - end).days > 7,
        pending_contact=not customer.email and bool(pending_email),
        can_email=payload["can_email"],
        can_renew=payload["can_renew"],
    )


def context(*, customer, flow, source, actor=None, pending_email=""):
    if not settings.MEMBERSHIP_SALES_ENABLED or customer is None:
        return {"renewal_rows": []}
    rows = []
    for member in candidates(customer):
        row = opportunity(
            member,
            customer=customer,
            flow=flow,
            source=source,
            actor=actor,
            pending_email=pending_email,
        )
        if row:
            rows.append(row)
        if len(rows) == 12:
            break
    return {"renewal_rows": rows}


def record_event(*, customer, flow, source, actor, row, action):
    key = uuid.uuid5(
        uuid.UUID(str(flow["key"])),
        f"renewal:{row['purchase']}:{row['ends_on']}:{row['window']}:{action}",
    )
    event, created = MembershipRenewalPrompt.objects.get_or_create(
        pk=key,
        defaults=dict(
            purchase_id=row["purchase"],
            customer=customer,
            flow_key=flow["key"],
            source=source,
            actor=actor,
            customer_revision=customer.revision,
            provenance=row["provenance"],
            window=row["window"],
            action=action,
            ends_on=row["ends_on"],
            on=row["on"],
            remind_at=remind_at(today()) if action == "email_later" else None,
            snapshot=row,
            fingerprint=fingerprint(dict(row=row, action=action)),
        ),
    )
    if not created and (
        event.provenance != row["provenance"]
        or event.actor_id != (actor.pk if actor else None)
        or event.customer_id != customer.pk
    ):
        raise ValidationError("This renewal choice belongs to another booking review.")
    if created:
        AuditEvent.objects.create(
            actor=actor,
            action="membership.renewal_prompt_" + action,
            record_type="membership",
            record_id=str(row["purchase"]),
            changes=dict(prompt=str(event.pk), flow=str(flow["key"]), window=row["window"]),
        )
    return event


def private_link(event):
    authority, _ = MembershipPromptLink.objects.get_or_create(
        pk=uuid.uuid5(event.pk, "link-authority"), defaults=dict(prompt=event)
    )
    link, _ = MembershipRenewalLink.objects.get_or_create(
        pk=uuid.uuid5(authority.pk, "renewal-link"),
        defaults=dict(
            prior_id=event.purchase_id,
            customer_id=event.customer_id,
            prompt=authority,
            actor=None,
            expires_at=authority.created_at.astimezone(dt_timezone.utc) + timedelta(days=30),
        ),
    )
    return link


def result(event):
    if event.action == "renew":
        if event.source == "staff":
            url = reverse("membership_renew", args=[event.purchase_id])
        else:
            from .membership_public_authority import token_for

            url = reverse("public_membership_renewal", args=[token_for(private_link(event))])
        return dict(action="renew", url=url)
    if event.action == "email_later":
        return dict(
            action="email_later", message="Reminder requested for 9 a.m. tomorrow, New York time."
        )
    return dict(action=event.action, message="You can continue your booking.")


@transaction.atomic
def choose(*, customer, flow, source, actor, token, action, pending_email=""):
    enabled()
    writes_allowed()
    if source == "staff":
        from .payments.staff_create import permitted

        permitted(actor)
        if action == "renew":
            from .membership_sales import authorize

            authorize(actor, collect=True)
    elif source != "public" or actor is not None:
        raise PermissionDenied
    if action not in ACTIONS or not isinstance(token, str) or len(token) > 8192:
        raise ValidationError("Choose a current booking renewal option.")
    try:
        row = signing.loads(token, salt=SALT, max_age=30 * 60)
        if (
            row["provenance"] != provenance(customer, flow, source, actor)
            or row["flow"] != str(flow["key"])
            or row["source"] != source
            or row["actor"] != (actor.pk if actor else None)
            or row["customer"] != customer.pk
            or row["revision"] != customer.revision
        ):
            raise ValueError
    except (signing.BadSignature, KeyError, ValueError, TypeError):
        raise ValidationError("This renewal review changed. Refresh the booking choices.") from None
    lock_customer(customer.pk)
    prior = MembershipRenewalPrompt.objects.filter(
        purchase_id=row["purchase"],
        flow_key=flow["key"],
        ends_on=row["ends_on"],
        window=row["window"],
        action=action,
    ).first()
    if prior and prior.provenance == row["provenance"]:
        return result(prior)
    member = next((item for item in candidates(customer) if item.pk == row["purchase"]), None)
    fresh = (
        opportunity(
            member,
            customer=customer,
            flow=flow,
            source=source,
            actor=actor,
            pending_email=pending_email,
        )
        if member
        else None
    )
    if not fresh or fingerprint(fresh["payload"]) != fingerprint(row):
        raise ValidationError("This renewal option changed. Refresh the booking choices.")
    if action == "renew" and not row["can_renew"]:
        raise PermissionDenied
    if action == "email_later" and not row["can_email"]:
        raise ValidationError("Add an email address before requesting a renewal reminder.")
    seen = record_event(
        customer=customer, flow=flow, source=source, actor=actor, row=row, action="seen"
    )
    event = (
        seen
        if action == "seen"
        else record_event(
            customer=customer, flow=flow, source=source, actor=actor, row=row, action=action
        )
    )
    return result(event)
