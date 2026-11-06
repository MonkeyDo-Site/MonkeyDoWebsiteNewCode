import uuid
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.utils import timezone

from .availability import NEW_YORK
from .membership_calendar import schedule
from .models import (
    AuditEvent,
    MembershipDraft,
    MembershipDraftCycle,
    MembershipPricing,
    PricingPolicy,
)
from .permissions import require_actor
from .pricing import Line, quote_lines

RULE_VERSION = "membership-calendar-2026-11-06-v1"


@transaction.atomic
def create_draft(
    *, actor, customer, kind, places, months, billing, starts_on, expected_method, creation_key
):
    require_actor(actor, "core.add_membershipdraft")
    require_actor(actor, "core.view_membershipdraft")
    require_actor(actor, "core.view_customer")
    if type(places) is not int or not 1 <= places <= 2147483647:
        raise ValidationError("Choose a positive whole number of anonymous membership places.")
    if type(months) is not int or months < 3:
        raise ValidationError("New memberships require at least three whole months.")
    if kind not in {"subscription", "unlimited"} or billing not in {"monthly", "prepaid"}:
        raise ValidationError("Choose a supported membership and billing type.")
    if expected_method not in {"card", "cash", "check", "zelle", "gift_card"}:
        raise ValidationError("Choose a supported expected payment method.")
    if type(starts_on) is not date:
        raise ValidationError("Use a civil test start date.")
    try:
        key = uuid.UUID(str(creation_key))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("A valid submission identifier is required.") from None
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(%s, %s)",
                [73217, int.from_bytes(key.bytes[:4], signed=True)],
            )
    current = MembershipDraft.objects.filter(creation_key=key).first()
    if current:
        if (
            current.actor_id,
            current.customer_id,
            current.kind,
            current.places,
            current.months,
            current.billing,
            current.starts_on,
            current.expected_method,
        ) != (actor.pk, customer.pk, kind, places, months, billing, starts_on, expected_method):
            raise ValidationError(
                "This submission identifier was already used for a different draft."
            )
        return current
    if starts_on < timezone.localdate(timezone=NEW_YORK):
        raise ValidationError("Choose today or a future test start date.")
    cycles = schedule(starts_on, months)
    pricing = MembershipPricing.objects.first()
    policy = PricingPolicy.objects.first()
    if not pricing or not policy:
        raise ValidationError("Run the reviewed pricing migrations before creating drafts.")
    unit = getattr(pricing, kind)
    monthly = unit * places
    draft = MembershipDraft.objects.create(
        customer=customer,
        kind=kind,
        places=places,
        months=months,
        billing=billing,
        starts_on=starts_on,
        ends_on=cycles[-1]["ends_on"],
        unit_price=unit,
        pricing=pricing,
        fee_policy=policy,
        expected_method=expected_method,
        creation_key=key,
        actor=actor,
        snapshot={
            "rule_version": RULE_VERSION,
            "original_anchor_day": starts_on.day,
            "test_mode": True,
            "status": "draft",
            "benefits_active": False,
            "terms_accepted": False,
            "monthly_subtotal": str(monthly),
            "term_subtotal": str(monthly * months),
            "fee_rate": str(policy.card_fee_rate),
            "anonymous_places": True,
        },
    )
    rows = []
    for cycle in cycles:
        due = billing == "monthly" or cycle["number"] == 1
        quote = (
            quote_lines(
                [
                    Line(
                        f"{kind.title()} Membership — "
                        + ("whole term" if billing == "prepaid" else "monthly installment"),
                        places,
                        unit * (months if billing == "prepaid" else 1),
                        False,
                    )
                ],
                policy,
                card_base=None if expected_method == "card" else Decimal(0),
            )
            if due
            else None
        )
        rows.append(
            MembershipDraftCycle(
                draft=draft,
                **(cycle | {"charge_on": cycle["charge_on"] if due else None}),
                quote=quote,
            )
        )
    MembershipDraftCycle.objects.bulk_create(rows)
    AuditEvent.objects.create(
        actor=actor,
        action="membership.draft_created",
        record_type="membership_draft",
        record_id=str(draft.pk),
        changes={
            "customer_id": customer.pk,
            "kind": kind,
            "places": places,
            "months": months,
            "billing": billing,
            "starts_on": starts_on.isoformat(),
            "ends_on": draft.ends_on.isoformat(),
            "membership_price_version": pricing.pk,
            "fee_policy": policy.pk,
            "status": "draft",
        },
    )
    return draft
