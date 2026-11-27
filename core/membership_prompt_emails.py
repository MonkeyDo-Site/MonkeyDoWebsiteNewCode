"""One explicitly requested renewal reminder, with fresh protected-link copy."""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.urls import reverse
from django.utils import timezone

from .communications.models import MessageDelivery, MessageEvent
from .communications.services import enqueue
from .membership_booking_prompts import candidate_members, private_link
from .membership_public_authority import token_for
from .membership_records import MembershipPromptEmail, MembershipRenewalPrompt
from .membership_renewals import renewal_details
from .membership_reservations import lock_customer
from .membership_sales import enabled, today
from .payments.ledger import fingerprint, writes_allowed

KIND = "membership_requested_renewal"
logger = logging.getLogger(__name__)


def eligible(event):
    member = event.purchase
    if (
        event.action != "email_later"
        or not event.remind_at
        or not event.remind_at <= timezone.now() <= event.remind_at + timedelta(days=30)
        or event.ends_on != member.membership.ends_on
        or member.billing_state.stopped_on
        or member.cancellations.exists()
        or not event.customer.email
    ):
        return None
    try:
        details = renewal_details(member)
    except ValidationError:
        return None
    return details if details["available_places"] else None


def content(event, details, link):
    from .date_display import display_date

    root = event.purchase.membership
    end, on = event.ends_on, today()
    places = details["available_places"]
    label = f"{places} {root.get_kind_display()} membership{'s' if places != 1 else ''}"
    timing = f"Your {label} {'ended' if end < on else 'ends' if places == 1 else 'end'} on {display_date(end)}."
    if details["minimum_months"] == 1:
        rule = (
            f"Renew by {display_date(end + timedelta(days=7))} without a new three-month minimum."
        )
        beginning = (
            "Your renewed membership will begin after your current term ends."
            if on <= end
            else "Your renewed membership will begin when you renew."
        )
    else:
        rule = "Renewal now requires a new three-month minimum."
        beginning = "Your renewed membership will begin when you renew."
    url = settings.BOOKING_STAGING_ORIGIN.rstrip("/") + reverse(
        "public_membership_renewal", args=[token_for(link)]
    )
    text = "\n\n".join(
        [
            f"Dear Family {event.customer.last_name},",
            "Here's the membership renewal link you requested.",
            timing,
            rule,
            beginning,
            "Renew membership: " + url,
            "This link does not extend the seven-day renewal deadline.",
            "Get ready to go bananas,\n\nThe Monkey Do team",
        ]
    )
    return "Your requested Monkey Do renewal link", text


def withdraw(authority, code, except_id=None):
    messages = MessageDelivery.objects.filter(
        renewal_prompt_evidence__authority=authority, state="queued"
    ).select_for_update(of=("self",))
    if except_id:
        messages = messages.exclude(pk=except_id)
    for message in messages:
        message.state, message.code = "cancelled", code
        message.save(update_fields=["state", "code"])
        MessageEvent.objects.create(delivery=message, state="cancelled", code=code)


def current_event(event_id):
    return MembershipRenewalPrompt.objects.select_related(
        "customer", "purchase__membership", "purchase__billing_state"
    ).get(pk=event_id)


@transaction.atomic
def refresh(authority):
    enabled()
    writes_allowed()
    event = current_event(authority.prompt_id)
    lock_customer(event.customer_id)
    details = eligible(event)
    attempted = authority.deliveries.exclude(message__state__in=["queued", "cancelled"]).exists()
    link = authority.link
    if (
        details is None
        or attempted
        or link.expires_at <= timezone.now()
        or hasattr(link, "revocation")
        or hasattr(link, "acceptance")
    ):
        withdraw(authority, "requested_renewal_obsolete")
        return None
    subject, text = content(event, details, link)
    key = f"requested-renewal:{authority.pk}:" + fingerprint(
        dict(recipient=event.customer.email, subject=subject, text=text)
    )
    previous = (
        authority.deliveries.select_related("message")
        .filter(message__dedupe_key__startswith=key)
        .order_by("-pk")
        .first()
    )
    if previous:
        key = (
            (key + ":v" + str(authority.deliveries.count()))
            if previous.message.state == "cancelled"
            else previous.message.dedupe_key
        )
    message = enqueue(
        key=key,
        kind=KIND,
        recipient=event.customer.email,
        subject=subject,
        text=text,
        customer=event.customer,
        membership=event.purchase,
        actor=None,
    )
    MembershipPromptEmail.objects.get_or_create(authority=authority, message=message)
    withdraw(authority, "requested_renewal_refreshed", except_id=message.pk)
    return message


@transaction.atomic
def prepare(event_id):
    enabled()
    writes_allowed()
    event = current_event(event_id)
    lock_customer(event.customer_id)
    if eligible(event) is None:
        return None
    link = private_link(event)
    return refresh(link.prompt)


def prepare_due(*, limit=20, dry_run=False):
    enabled()
    writes_allowed()
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValidationError("Use a requested-reminder limit between 1 and 100.")
    events = list(
        MembershipRenewalPrompt.objects.filter(
            action="email_later",
            link_authority__isnull=True,
            remind_at__lte=timezone.now(),
            remind_at__gte=timezone.now() - timedelta(days=30),
            purchase_id__in=candidate_members().values("pk"),
        )
        .exclude(customer__email="")
        .order_by("remind_at", "pk")[:limit]
    )
    ready, blocked = 0, 0
    for event in events:
        if dry_run:
            ready += 1
            continue
        try:
            ready += prepare(event.pk) is not None
        except (ValidationError, DatabaseError):
            # Each request is atomic. A changed contact or failed producer must
            # not prevent unrelated, previously accepted jobs from running.
            blocked += 1
            logger.warning("Requested renewal reminder preparation deferred: %s", event.pk)
    return dict(ready=ready, blocked=blocked, dry_run=dry_run)


def overview_context(member):
    return dict(
        requested_renewal_history=member.renewal_prompts.filter(action="email_later")
        .prefetch_related("link_authority__deliveries__message")
        .order_by("-created_at")[:20]
    )
