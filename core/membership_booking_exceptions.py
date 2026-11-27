"""Explicit owner decisions for one booking; previews never grant benefits."""

from django.core.exceptions import ValidationError

from .membership_records import MembershipBookingDecision
from .models import AuditEvent
from .permissions import require_actor


def unavailable_memberships(booking):
    from .membership_booking import active
    from .membership_reservations import payment_current

    if booking is None or not active(booking):
        return []
    result, seen = set(), set()
    for assignment in booking.membership_benefits.filter(
        current__status__in=["reserved", "used"]
    ).select_related("purchase__billing_state"):
        if assignment.purchase_id not in seen:
            seen.add(assignment.purchase_id)
            root = assignment.purchase.membership
            stopped = assignment.purchase.billing_state.stopped_on
            if (
                not payment_current(assignment.purchase)
                or not root.starts_on <= assignment.appointment_on <= root.ends_on
                or (stopped and stopped <= assignment.appointment_on)
            ):
                result.add(assignment.purchase_id)
    return sorted(result)


def controls_needed(booking):
    from .membership_booking import active

    if not booking or not active(booking) or booking.attendance:
        return False
    state = getattr(booking, "charge_state", None)
    return bool(unavailable_memberships(booking) or (state and state.membership_decision_id))


def resolve(booking, *, actor=None, choice="", reason="", session=None):
    from .membership_booking import active

    target = session or booking.session
    if choice:
        if not active(booking):
            raise ValidationError("Active membership booking controls are not enabled.")
        require_actor(actor, "core.change_booking", owner=True)
        if choice not in {"normal", "ordinary", "honor"}:
            raise ValidationError("Choose a membership pricing decision.")
        if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 240:
            raise ValidationError("Record a short reason for this booking's membership exception.")
        members = unavailable_memberships(booking) if choice == "honor" else []
        if choice == "honor" and not members:
            raise ValidationError(
                "This booking has no overdue reserved membership benefits to honor."
            )
        if choice == "honor":
            from .availability import NEW_YORK
            from .membership_records import MembershipPurchase

            on = target.starts_at.astimezone(NEW_YORK).date()
            for member in MembershipPurchase.objects.filter(pk__in=members).select_related(
                "membership", "billing_state"
            ):
                if not member.membership.starts_on <= on <= member.membership.ends_on or (
                    member.billing_state.stopped_on and member.billing_state.stopped_on <= on
                ):
                    raise ValidationError(
                        "Those reserved membership benefits do not cover this session. Use ordinary admission prices or review the membership first."
                    )
        return dict(mode=choice, memberships=members, session=target.pk, reason=reason.strip())
    state = getattr(booking, "charge_state", None)
    decision = state.membership_decision if state and state.membership_decision_id else None
    if not decision or (decision.mode == "honor" and decision.session_id != target.pk):
        return None
    if decision.mode == "honor":
        from .availability import NEW_YORK
        from .membership_records import MembershipPurchase

        on = target.starts_at.astimezone(NEW_YORK).date()
        for member in MembershipPurchase.objects.filter(pk__in=decision.memberships).select_related(
            "membership", "billing_state"
        ):
            if not member.membership.starts_on <= on <= member.membership.ends_on or (
                member.billing_state.stopped_on and member.billing_state.stopped_on <= on
            ):
                return None
    return dict(
        mode=decision.mode,
        memberships=decision.memberships,
        session=decision.session_id,
        reason=decision.reason,
    )


def flags(decision):
    return dict(
        ordinary_pricing=bool(decision and decision["mode"] == "ordinary"),
        payment_exceptions=set(decision["memberships"])
        if decision and decision["mode"] == "honor"
        else set(),
    )


def persist(*, actor, booking, state, choice, reason, request_key):
    if not choice:
        return
    data = resolve(booking, actor=actor, choice=choice, reason=reason)
    decision = MembershipBookingDecision.objects.create(
        id=request_key,
        booking=booking,
        session_id=data["session"],
        mode=data["mode"],
        memberships=data["memberships"],
        reason=data["reason"],
        actor=actor,
    )
    previous = state.membership_decision_id
    state.membership_decision = decision
    AuditEvent.objects.create(
        actor=actor,
        action="membership.booking_exception_recorded",
        record_type="booking",
        record_id=str(booking.reference),
        changes={
            "previous": str(previous) if previous else None,
            "decision": str(decision.pk),
            **data,
        },
    )


def add_fields(form, *, booking, owner):
    from django import forms

    if not owner or not controls_needed(booking):
        return
    form.fields["membership_resolution"] = forms.ChoiceField(
        required=False,
        label="Owner: membership pricing for this booking",
        choices=[
            ("", "Keep current decision / resolve the membership payment first"),
            ("ordinary", "Use ordinary admission prices"),
            ("honor", "Honor reserved membership benefits for this booking"),
            ("normal", "Return to normal paid membership rules"),
        ],
    )
    form.fields["membership_resolution_reason"] = forms.CharField(
        required=False,
        max_length=240,
        widget=forms.Textarea(attrs={"rows": 2}),
        label="Reason for this booking decision",
        help_text="Required when changing the decision. Applies only to this booking; membership dues and other bookings stay unchanged.",
    )
