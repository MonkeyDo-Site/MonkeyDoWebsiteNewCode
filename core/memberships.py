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
    *,
    actor,
    customer,
    kind,
    places,
    months,
    billing,
    starts_on,
    expected_method,
    creation_key,
    minimum_override=False,
):
    require_actor(actor, "core.add_membershipdraft")
    require_actor(actor, "core.view_membershipdraft")
    require_actor(actor, "core.view_customer")
    if type(places) is not int or not 1 <= places <= 2147483647:
        raise ValidationError("Choose a positive whole number of anonymous membership places.")
    if minimum_override:
        require_actor(actor, "core.add_membershipdraft", owner=True)
    if type(months) is not int or months < (1 if minimum_override else 3):
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
            "owner_minimum_override": bool(minimum_override and months < 3),
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
            "owner_minimum_override": bool(minimum_override and months < 3),
        },
    )
    return draft


EDIT_FIELDS = ("kind", "places", "months", "billing", "starts_on", "expected_method")


def draft_state(draft):
    return {
        key: getattr(draft, key).isoformat() if key == "starts_on" else getattr(draft, key)
        for key in EDIT_FIELDS
    }


def current_draft(root, revision=None, *, original=False):
    """Read model for the latest version, preserving the root's existing internal ID."""
    from copy import copy
    from types import SimpleNamespace

    latest = None if original else revision or root.revisions.first()
    result = copy(root)
    result.version_number = latest.number if latest else 1
    result.version_saved_at = latest.created_at if latest else root.created_at
    result.original_draft = root
    if latest:
        for key in EDIT_FIELDS:
            item = latest.data[key]
            setattr(result, key, date.fromisoformat(item) if key == "starts_on" else item)
        result.ends_on = date.fromisoformat(latest.data["ends_on"])
        result.unit_price = Decimal(latest.data["unit_price"])
        result.snapshot = latest.data["snapshot"]
        result.version_cycles = [
            SimpleNamespace(
                **{
                    **cycle,
                    **{
                        key: date.fromisoformat(cycle[key]) if cycle[key] else None
                        for key in ("starts_on", "ends_on", "charge_on")
                    },
                }
            )
            for cycle in latest.cycles
        ]
    else:
        result.version_cycles = root.cycles.all()
    return result


@transaction.atomic
def edit_draft(
    *,
    actor,
    draft_id,
    version,
    submission_key,
    kind,
    places,
    months,
    billing,
    starts_on,
    expected_method,
    minimum_override=False,
):
    from .models import MembershipDraftRevision

    require_actor(actor, "core.change_membershipdraft")
    require_actor(actor, "core.view_membershipdraft")
    require_actor(actor, "core.view_customer")
    root = (
        MembershipDraft.objects.select_for_update()
        .select_related("pricing", "fee_policy")
        .get(pk=draft_id)
    )
    current = current_draft(root)
    try:
        key = uuid.UUID(str(submission_key))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Reload the membership before submitting this edit.") from None
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(%s, %s)",
                [73218, int.from_bytes(key.bytes[:4], signed=True)],
            )
    submitted = {
        "version": version,
        "kind": kind,
        "places": places,
        "months": months,
        "billing": billing,
        "starts_on": starts_on.isoformat() if type(starts_on) is date else str(starts_on),
        "expected_method": expected_method,
        "minimum_override": minimum_override,
    }
    saved = MembershipDraftRevision.objects.filter(submission_key=key).first()
    if saved:
        if saved.draft_id != root.pk or saved.actor_id != actor.pk or saved.submission != submitted:
            raise ValidationError(
                "This submission was already used for a different membership edit."
            )
        return current_draft(root, saved)
    if current.version_number != version:
        raise ValidationError(
            "Membership changed while you were editing. Reload and review the latest version."
        )
    if hasattr(root, "purchase"):
        raise ValidationError(
            "This is a purchased membership. Use its renewal, addition or correction controls to preserve payments and benefits."
        )
    if type(places) is not int or not 1 <= places <= 2147483647:
        raise ValidationError("Choose a positive whole number for Amount.")
    if minimum_override:
        require_actor(actor, "core.change_membershipdraft", owner=True)
    inherited_exception = current.months < 3 and (kind, places, months, starts_on) == (
        current.kind,
        current.places,
        current.months,
        current.starts_on,
    )
    if type(months) is not int or months < (1 if minimum_override or inherited_exception else 3):
        raise ValidationError(
            "A one- or two-month term change requires an explicit owner exception."
        )
    if kind not in {"subscription", "unlimited"} or billing not in {"monthly", "prepaid"}:
        raise ValidationError("Choose a supported membership and billing type.")
    if expected_method not in {"card", "cash", "check", "zelle", "gift_card"}:
        raise ValidationError("Choose a supported expected payment method.")
    if type(starts_on) is not date or (
        starts_on < timezone.localdate(timezone=NEW_YORK) and starts_on != current.starts_on
    ):
        raise ValidationError("Keep the existing start date or choose today/a future date.")
    windows = schedule(starts_on, months)
    unit = getattr(root.pricing, kind)
    subtotal = unit * places
    cycles = []
    for window in windows:
        due = billing == "monthly" or window["number"] == 1
        quote = (
            quote_lines(
                [
                    Line(
                        f"{kind.title()} Membership",
                        places,
                        unit * (months if billing == "prepaid" else 1),
                        False,
                    )
                ],
                root.fee_policy,
                card_base=None if expected_method == "card" else Decimal(0),
            )
            if due
            else None
        )
        cycles.append(
            {
                "number": window["number"],
                "starts_on": window["starts_on"].isoformat(),
                "ends_on": window["ends_on"].isoformat(),
                "charge_on": window["charge_on"].isoformat() if due else None,
                "quote": quote,
            }
        )
    state = {key: submitted[key] for key in EDIT_FIELDS}
    snapshot = {
        **current.snapshot,
        "original_anchor_day": starts_on.day,
        "monthly_subtotal": str(subtotal),
        "term_subtotal": str(subtotal * months),
        "owner_minimum_override": months < 3 and (minimum_override or inherited_exception),
    }
    data = {
        **state,
        "ends_on": windows[-1]["ends_on"].isoformat(),
        "unit_price": str(unit),
        "snapshot": snapshot,
    }
    revision = MembershipDraftRevision.objects.create(
        draft=root,
        number=version + 1,
        data=data,
        cycles=cycles,
        submission_key=key,
        submission=submitted,
        actor=actor,
    )
    AuditEvent.objects.create(
        actor=actor,
        action="membership.draft_edited",
        record_type="membership_draft",
        record_id=str(root.pk),
        changes={
            "before": {
                **draft_state(current),
                "ends_on": current.ends_on.isoformat(),
                "term_subtotal": current.snapshot["term_subtotal"],
            },
            "after": {
                **state,
                "ends_on": data["ends_on"],
                "term_subtotal": snapshot["term_subtotal"],
            },
            "revision": revision.number,
            "owner_minimum_override": snapshot["owner_minimum_override"],
            "membership_price_version": root.pricing_id,
            "fee_policy": root.fee_policy_id,
        },
    )
    return current_draft(root, revision)
