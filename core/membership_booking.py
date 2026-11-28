"""Membership pricing hooks shared by confirmed bookings, estimates and arrival."""

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError

from .availability import NEW_YORK
from .membership_calendar_changes import cycle_on, root_for, with_calendar
from .membership_reservations import lock_customer, payment_current, reserve, visit_plan
from .pricing import Line, quote_lines

COUNTS = ("children", "adults", "babies", "socks", "supervised")


def active(booking=None):
    return settings.MEMBERSHIP_SALES_ENABLED and (
        booking is None or booking.workflow == "integrated_v1"
    )


def existing_daily_places(booking):
    return set(
        booking.membership_benefits.filter(
            current__status__in=["reserved", "used"], kind="unlimited_daily"
        ).values_list("purchase_id", "place")
    )


def require_paid_existing(
    booking,
    *,
    special_admissions=None,
    comped=False,
    payment_exceptions=frozenset(),
    ordinary_pricing=False,
):
    if booking is None or comped or special_admissions is not None or ordinary_pricing:
        return
    purchases = set()
    for assignment in booking.membership_benefits.filter(
        current__status__in=["reserved", "used"]
    ).select_related("purchase"):
        if assignment.purchase_id in purchases:
            continue
        purchases.add(assignment.purchase_id)
        root = root_for(assignment.purchase)
        stopped = assignment.purchase.billing_state.stopped_on
        if not root.starts_on <= assignment.appointment_on <= root.ends_on or (
            stopped and stopped <= assignment.appointment_on
        ):
            raise ValidationError(
                "This booking's reserved membership benefits no longer cover its visit. Ask the owner to review ordinary pricing or the membership first. This booking has not been repriced.",
                code="membership_coverage_review",
            )
        if assignment.purchase_id not in payment_exceptions and not payment_current(
            assignment.purchase
        ):
            raise ValidationError(
                "A membership payment needs attention. Resolve it before using the reserved benefits, or have the owner review an admissions-price exception. This booking has not been repriced.",
                code="membership_payment_review",
            )


def lines_for(
    policy,
    *,
    customer_id,
    session,
    values,
    booking=None,
    special_admissions=None,
    comped=False,
    apply_available=False,
    resolution=None,
    proposed_membership=None,
):
    from .membership_booking_exceptions import flags, resolve

    resolution = (
        resolution
        if resolution is not None
        else resolve(booking, session=session)
        if booking
        else None
    )
    overrides = flags(resolution)
    require_paid_existing(
        booking, special_admissions=special_admissions, comped=comped, **overrides
    )
    on = session.starts_at.astimezone(NEW_YORK).date()
    allow_daily = (
        booking is None
        or booking.setup_pending
        or apply_available
        or proposed_membership is not None
    )
    if booking is not None:
        saved = booking.quotes.first()
        old_on = saved.snapshot.get("membership_appointment_on") if saved else None
        allow_daily = (
            allow_daily
            or values["children"] != booking.children
            or values["supervised"] != booking.supervised
            or session.pk != booking.session_id
            or (old_on is not None and old_on != on.isoformat())
        )
    plan = visit_plan(
        policy,
        customer_id=customer_id,
        appointment_on=on,
        **{key: values[key] for key in COUNTS},
        exclude_booking=booking.pk if booking else None,
        special_admissions=special_admissions,
        comped=comped,
        unlimited_places=None if allow_daily else existing_daily_places(booking),
        proposed_membership=proposed_membership,
        **overrides,
    )
    meta = {
        "membership_benefits_applied": bool(plan.uses),
        "membership_plan": plan.snapshot(),
        "membership_options": {"allow_new_unlimited": bool(allow_daily)},
        "membership_appointment_on": on.isoformat(),
        "membership_attendees": {key: values[key] for key in COUNTS},
    }
    if resolution:
        meta["membership_owner_decision"] = resolution
    return list(plan.lines), meta


def new_quote(policy, *, customer_id, session, values, special_admissions=None, comped=False):
    lines, meta = lines_for(
        policy,
        customer_id=customer_id,
        session=session,
        values=values,
        special_admissions=special_admissions,
        comped=comped,
    )
    quote = quote_lines(
        lines,
        policy,
        card_base=None if values["expected_method"] == "card" and not comped else Decimal("0.00"),
    )
    return (
        quote
        | meta
        | dict(
            expected_method=values["expected_method"],
            owner_comped=comped,
            owner_special_admissions=str(special_admissions)
            if special_admissions is not None
            else None,
        )
    )


def booking_quote(booking, policy, values=None):
    from .payments.models import BookingChargeState

    editing = values is not None
    values = values or {key: getattr(booking, key) for key in (*COUNTS, "expected_method")}
    session = values.get("session") or booking.session
    state = BookingChargeState.objects.filter(booking=booking).first()
    comped = bool(state and state.comped)
    special = values.get("special_admissions")
    if special is None:
        special = state.special_subtotal if state else None
    units = (
        0
        if special is not None or comped
        else max(
            0,
            (state.pending_fee_units if state else 0)
            + (booking.children - values["children"] if editing else 0),
        )
    )
    lines, meta = lines_for(
        policy,
        customer_id=booking.customer_id,
        session=session,
        values=values,
        booking=booking,
        special_admissions=special,
        comped=comped,
        apply_available=values.get("apply_available_benefits", False),
        resolution=values.get("membership_resolution_decision"),
    )
    if units:
        lines.append(Line("Partial cancellation fee", units, Decimal("3.00"), False))
    quote = quote_lines(
        lines,
        policy,
        card_base=None if values["expected_method"] == "card" and not comped else Decimal("0.00"),
    )
    return (
        quote
        | meta
        | dict(
            expected_method=values["expected_method"],
            owner_comped=comped,
            owner_special_admissions=str(special) if special is not None else None,
        )
    )


def confirm(booking, *, actor):
    if not active(booking):
        return
    saved = booking.quotes.first()
    if "membership_plan" not in saved.snapshot:
        return
    reserve(
        actor=actor,
        booking_id=booking.pk,
        quote_id=saved.pk,
        request_key=uuid.uuid5(booking.reference, f"membership-quote:{saved.pk}"),
    )


def lock(booking):
    if active(booking):
        lock_customer(booking.customer_id)


def has_available_daily(booking):
    if not active(booking) or booking.setup_pending or booking.attendance:
        return False
    saved = booking.quotes.first()
    if saved is None:
        return False
    state = getattr(booking, "charge_state", None)
    if state and (state.comped or state.special_subtotal is not None):
        return False
    try:
        _, meta = lines_for(
            saved.policy,
            customer_id=booking.customer_id,
            session=booking.session,
            values={key: getattr(booking, key) for key in COUNTS},
            booking=booking,
            apply_available=True,
        )
    except ValidationError:
        return False
    current = existing_daily_places(booking)
    return any(
        use["kind"] == "unlimited_daily" and (use["membership_id"], use["place"]) not in current
        for use in meta["membership_plan"]["uses"]
    )


def summaries(customer_id, session, quote=None):
    """Read-only, appointment-specific membership facts for a verified customer."""
    if not active() or not customer_id or session is None:
        return []
    from collections import Counter

    from django.db.models import Q

    from .membership_records import MembershipPurchase
    from .membership_reservations import summary_for, today
    from .membership_sales import membership_status

    on = session.starts_at.astimezone(NEW_YORK).date()
    applied = Counter(
        use["membership_id"] for use in (quote or {}).get("membership_plan", {}).get("uses", [])
    )
    members = (
        with_calendar(MembershipPurchase.objects.filter(customer_id=customer_id))
        .filter(
            Q(calendar_ends_on__gte=today())
            | Q(calendar_starts_on__lte=on, calendar_ends_on__gte=on)
        )
        .select_related("membership", "billing_state")
        .order_by("calendar_ends_on", "pk")[:12]
    )
    result = []
    for member in members:
        root = root_for(member)
        quota = summary_for(member, on=on)
        cycle = cycle_on(member, on)
        result.append(
            dict(
                kind=root.get_kind_display(),
                places=root.places,
                starts_on=root.starts_on,
                ends_on=root.ends_on,
                status=membership_status(member),
                quota=quota,
                cycle=cycle,
                applied=applied[member.pk],
            )
        )
    return result
