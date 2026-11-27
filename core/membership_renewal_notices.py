"""Approved cohort notices, rechecked before dispatch and never a purchase."""

import uuid
from datetime import timedelta
from datetime import timezone as dt_timezone

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import BigIntegerField, Exists, F, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.urls import reverse

from .communications.models import MessageDelivery, MessageEvent
from .communications.services import enqueue
from .membership_public_authority import token_for
from .membership_records import (
    MembershipPurchase,
    MembershipRenewalLink,
    MembershipRenewalNotice,
    MembershipRenewalNoticeDelivery,
)
from .membership_renewals import remaining_places
from .membership_reservations import lock_customer, payment_current
from .membership_sales import enabled, today
from .models import AuditEvent
from .payments.ledger import fingerprint, writes_allowed

KINDS = {"expiry": "membership_expiry_notice", "grace": "membership_grace_notice"}


def direct_payment_review(member_id=None):
    from .membership_cancellations import unrecorded_provider_return
    from .models import PaymentOperation

    sources = (
        PaymentOperation.objects.filter(
            Q(events__code="external_correction_review")
            | Q(observations__provider_status__in=["external_credit", "voided", "returned"]),
            sale__membership_invoice__isnull=False,
            kind="receipt",
            tender="card",
            state="succeeded",
        )
        .select_related("sale__membership_invoice__installment")
        .distinct()
    )
    if member_id is not None:
        sources = sources.filter(sale__membership_invoice__installment__purchase_id=member_id)
    return {
        source.sale.membership_invoice.installment.purchase_id
        for source in sources
        if unrecorded_provider_return(source)
    }


def notice_dates(ends_on):
    try:
        return dict(
            expiry=ends_on - timedelta(days=5),
            grace=ends_on + timedelta(days=6),
            deadline=ends_on + timedelta(days=7),
        )
    except OverflowError:
        raise ValidationError("The membership renewal dates need owner review.") from None


def eligible(member, kind):
    if kind not in KINDS:
        raise ValidationError("Choose an approved membership notice.")
    dates = notice_dates(member.membership.ends_on)
    if dates[kind] != today():
        return None
    if (
        member.billing_state.stopped_on
        or member.cancellations.exists()
        or not member.customer.email
    ):
        return None
    if not payment_current(member) or direct_payment_review(member.pk):
        return None
    places = remaining_places(member)
    return (dates, places) if places else None


def message_content(notice, member, *, dates, places, link):
    from .date_display import display_date

    url = settings.BOOKING_STAGING_ORIGIN.rstrip("/") + reverse(
        "public_membership_renewal", args=[token_for(link)]
    )
    greeting = f"Dear Family {member.customer.last_name},"
    if notice.kind == "expiry":
        name = f"{places} {member.membership.get_kind_display()} membership{'s' if places != 1 else ''}"
        paragraphs = [
            greeting,
            "Ready for more Monkey Do adventures?",
            f"Your {name} {'expire' if places != 1 else 'expires'} on {display_date(notice.ends_on)}.",
            "We'd love to keep the fun going!",
            "Renew membership: " + url,
            "Renew within 7 days from when your membership ends with no three-month minimum. Renewal after 7 days requires a new three month minimum.",
            "Get ready to go bananas,\n\nThe Monkey Do team",
        ]
        subject = "More Monkey Do adventures? Your membership ends soon"
    else:
        paragraphs = [
            greeting,
            "There's still time for more Monkey Do adventures!",
            "Your membership renewal grace period ends tomorrow, "
            + display_date(dates["deadline"])
            + ".",
            "Renew by then to renew without a new three-month minimum. Your renewed membership will begin as soon as you renew.",
            "Renew membership: " + url,
            "We'd love to see you again,\n\nThe Monkey Do team",
        ]
        subject = "Your Monkey Do membership renewal window ends tomorrow"
    return subject, "\n\n".join(paragraphs)


def cancel_queued(notice, code, *, except_id=None):
    messages = MessageDelivery.objects.filter(
        renewal_notice_evidence__notice=notice, state="queued"
    ).select_for_update(of=("self",))
    if except_id:
        messages = messages.exclude(pk=except_id)
    for message in messages:
        message.state, message.code = "cancelled", code
        message.save(update_fields=["state", "code"])
        MessageEvent.objects.create(delivery=message, state="cancelled", code=code)


@transaction.atomic
def refresh_notice(notice):
    """Caller and claim share customer-before-message lock ordering."""
    enabled()
    writes_allowed()
    member = MembershipPurchase.objects.select_related(
        "membership", "customer", "billing_state"
    ).get(pk=notice.purchase_id)
    lock_customer(member.customer_id)
    data = eligible(member, notice.kind)
    attempted = notice.deliveries.exclude(message__state__in=["queued", "cancelled"]).exists()
    if data is None or attempted or member.membership.ends_on != notice.ends_on:
        cancel_queued(notice, "membership_notice_obsolete")
        return None
    link = MembershipRenewalLink.objects.filter(notice=notice).first()
    if link is None or hasattr(link, "revocation") or hasattr(link, "acceptance"):
        cancel_queued(notice, "membership_notice_link_unavailable")
        return None
    from django.utils import timezone

    if link.expires_at <= timezone.now():
        cancel_queued(notice, "membership_notice_link_unavailable")
        return None
    dates, places = data
    subject, text = message_content(notice, member, dates=dates, places=places, link=link)
    key = f"membership-notice:{notice.pk}:" + fingerprint(
        dict(recipient=member.customer.email, subject=subject, text=text)
    )
    previous = (
        notice.deliveries.select_related("message")
        .filter(message__dedupe_key__startswith=key)
        .order_by("-pk")
        .first()
    )
    if previous:
        if previous.message.state == "cancelled":
            key += ":v" + str(notice.deliveries.count())
        else:
            key = previous.message.dedupe_key
    message = enqueue(
        key=key,
        kind=KINDS[notice.kind],
        recipient=member.customer.email,
        subject=subject,
        text=text,
        customer=member.customer,
        membership=member,
        actor=None,
    )
    MembershipRenewalNoticeDelivery.objects.get_or_create(notice=notice, message=message)
    cancel_queued(notice, "membership_notice_refreshed", except_id=message.pk)
    return message


@transaction.atomic
def prepare_notice(*, member_id, kind):
    enabled()
    writes_allowed()
    member = MembershipPurchase.objects.select_related(
        "membership", "customer", "billing_state"
    ).get(pk=member_id)
    lock_customer(member.customer_id)
    data = eligible(member, kind)
    if data is None:
        return None
    dates, places = data
    key = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"monkeydo:renewal-notice:{member.pk}:{kind}:{member.membership.ends_on.isoformat()}",
    )
    notice, created = MembershipRenewalNotice.objects.get_or_create(
        pk=key,
        defaults=dict(
            purchase=member,
            kind=kind,
            ends_on=member.membership.ends_on,
            due_on=dates[kind],
            places=places,
        ),
    )
    if created:
        MembershipRenewalLink.objects.create(
            id=uuid.uuid5(key, "renewal-link"),
            notice=notice,
            prior=member,
            customer=member.customer,
            actor=None,
            expires_at=notice.created_at.astimezone(dt_timezone.utc) + timedelta(days=30),
        )
        AuditEvent.objects.create(
            actor=None,
            action="membership.renewal_notice_prepared",
            record_type="membership",
            record_id=str(member.pk),
            changes=dict(
                notice=str(notice.pk),
                kind=kind,
                due_on=notice.due_on.isoformat(),
                ends_on=notice.ends_on.isoformat(),
            ),
        )
    return refresh_notice(notice)


def candidates(*, limit):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValidationError("Use a notice limit between 1 and 100.")
    on = today()
    try:
        days = {on + timedelta(days=5): "expiry", on - timedelta(days=6): "grace"}
    except OverflowError:
        return []
    from .membership_records import MembershipOrigin
    from .membership_reporting import held_members, reporting_members

    renewed = (
        MembershipOrigin.objects.filter(prior_id=OuterRef("pk"), operation="renewal")
        .exclude(purchase__billing_state__stopped_on__lte=F("purchase__membership__starts_on"))
        .order_by()
        .values("prior_id")
        .annotate(total=Sum("places"))
        .values("total")
    )
    existing = MembershipRenewalNotice.objects.filter(
        purchase_id=OuterRef("pk"), due_on=on, ends_on=OuterRef("membership__ends_on")
    )
    records = (
        reporting_members()
        .filter(
            Q(purpose="complimentary")
            | Q(_has_installments=True, _unpaid_first=False, _unpaid_due=False),
            membership__ends_on__in=days,
            billing_state__stopped_on__isnull=True,
        )
        .exclude(customer__email="")
        .exclude(pk__in=held_members())
        .exclude(pk__in=direct_payment_review())
        .annotate(
            _notice_exists=Exists(existing),
            _renewed=Coalesce(
                Subquery(renewed, output_field=BigIntegerField()),
                Value(0),
                output_field=BigIntegerField(),
            ),
        )
        .filter(_notice_exists=False, _renewed__lt=F("membership__places"))
        .order_by("membership__ends_on", "pk")
    )
    return [(member, days[member.membership.ends_on]) for member in records[:limit]]


def prepare_due(*, limit=20, dry_run=False):
    if not settings.BOOKING_EMAIL_ENABLED:
        return dict(examined=0, ready=0)
    enabled()
    writes_allowed()
    examined, ready = 0, 0
    for member, kind in candidates(limit=limit):
        examined += 1
        if dry_run:
            ready += int(eligible(member, kind) is not None)
        else:
            ready += int(prepare_notice(member_id=member.pk, kind=kind) is not None)
    return dict(examined=examined, ready=ready)


def overview_context(member):
    try:
        dates = notice_dates(member.membership.ends_on)
    except ValidationError:
        dates = None
    return dict(
        renewal_notice_dates=dates,
        renewal_notice_history=member.renewal_notices.prefetch_related(
            "deliveries__message"
        ).order_by("-due_on", "-pk"),
    )
