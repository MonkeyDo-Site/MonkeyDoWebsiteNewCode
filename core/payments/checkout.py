"""Explicit staff-reviewed arrival/closure; a preview never records attendance or money."""

import uuid
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.booking_completion import enabled
from core.booking_management import snapshot
from core.calendar import lock_calendar
from core.models import AuditEvent, Booking, BookingQuote, Session
from core.permissions import require_actor
from core.pricing import Line, quote_lines, validate_attendees
from core.waivers.models import BookingWaiverReview

from .amounts import COMPONENTS, ZERO, amount
from .checkout_pricing import visit_lines
from .invoices import received, total
from .jobs import enqueue
from .ledger import accept_booking_sale, fingerprint, lock_request, record_manual, request_operation
from .methods import queue_disposal
from .models import BookingChargeState, BookingCheckout, PaymentFollowup, PaymentOperation


def authorize(actor):
    enabled()
    for permission in (
        "core.view_booking",
        "core.change_booking",
        "core.view_customer",
        "core.collect_payment",
    ):
        require_actor(actor, permission)


def charge_state(booking):
    return BookingChargeState.objects.filter(booking=booking).first() or BookingChargeState(
        booking=booking
    )


def require_current(booking, kind):
    if booking.workflow != "integrated_v1":
        raise ValidationError(
            "Use a new integrated booking. Earlier test records cannot be charged."
        )
    if booking.attendance:
        raise ValidationError(
            "Attendance is already recorded. Review the existing payment balance instead."
        )
    if kind not in {"arrival", "cancellation", "no_show"}:
        raise ValidationError("Choose an ordinary booking action.")
    if booking.session.kind != "ordinary":
        raise ValidationError("Use the applicable program or party workflow.")
    if kind == "no_show" and timezone.now() < booking.session.starts_at:
        raise ValidationError(
            "A no show can be recorded after the session starts. Use cancellation before then."
        )


def check_arrival_capacity(booking, counts, override, actor):
    others = booking.session.bookings.exclude(pk=booking.pk).exclude(
        attendance__in=["cancelled", "no_show"]
    )
    children = sum(others.values_list("children", flat=True))
    adults = sum(others.values_list("adults", flat=True))
    supervised = sum(others.filter(supervised=True).values_list("children", flat=True))
    over = (
        children + counts["children"] > booking.session.child_capacity
        or children + adults + counts["children"] + counts["adults"]
        > booking.session.total_capacity
        or (
            booking.supervised
            and not BookingChargeState.objects.filter(
                booking=booking, supervised_exception_session=booking.session
            ).exists()
            and supervised + counts["children"] > booking.session.supervised_capacity
        )
    )
    if over and not override:
        raise ValidationError(
            "Actual attendees exceed the session capacity. Review the arrival-only override before continuing."
        )
    if override:
        require_actor(actor, "core.change_booking")


def verify_coverage(booking, counts, confirmed):
    if confirmed is not True:
        raise ValidationError(
            "Return to waiver handling before confirming arrival. Your entries have not been saved or charged.",
            code="waiver_required",
        )
    review = BookingWaiverReview.objects.filter(booking=booking).first()
    if review and review.paper_signed:
        return
    from core.waivers.paper import active_customer_waivers

    signatures = active_customer_waivers(booking)
    minors = {name.strip().casefold() for signature in signatures for name in signature.minors}
    if not signatures or len(minors) < counts["children"] + counts["babies"]:
        raise ValidationError(
            "Obtain coverage for everyone using Sign waiver now, or record actual signed paper waivers before arrival.",
            code="waiver_required",
        )


def preview(*, actor, booking_id, kind, data, validate_waivers=True):
    authorize(actor)
    booking = Booking.objects.select_related("customer", "session").get(pk=booking_id)
    require_current(booking, kind)
    state = charge_state(booking)
    reopen = data.get("reopen_affected_sessions", False)
    if type(reopen) is not bool or (reopen and kind != "cancellation"):
        raise ValidationError("Review the cancellation reopening choice.")
    if reopen:
        require_actor(actor, "core.change_session", owner=True)
    saved = booking.quotes.first()
    if saved is None:
        raise ValidationError("No accepted pricing policy exists for this booking.")
    counts = {
        key: data.get(key, getattr(booking, key))
        for key in ("children", "adults", "babies", "socks")
    }
    if any(type(value) is not int for value in counts.values()):
        raise ValidationError("Actual attendee and sock quantities must be whole numbers.")
    override = data.get("override_capacity", False)
    if type(override) is not bool:
        raise ValidationError("Review the arrival capacity choice.")
    if kind == "arrival":
        if booking.setup_pending:
            raise ValidationError(
                "Complete booking setup before arrival. Complimentary bookings require no card."
            )
        validate_attendees(**counts, supervised=booking.supervised)
        check_arrival_capacity(booking, counts, override, actor)
        if validate_waivers:
            verify_coverage(booking, counts, data.get("waiver_confirmed"))
        special = state.special_subtotal
        if data.get("special_admissions") is not None:
            require_actor(actor, "core.change_booking", owner=True)
            if special is None or state.comped:
                raise ValidationError(
                    "Apply a special price in owner pricing settings before adjusting it here."
                )
            special = amount(data["special_admissions"])
        units = (
            0
            if special is not None or state.comped
            else max(0, state.pending_fee_units + booking.children - counts["children"])
        )
        lines = visit_lines(
            saved.policy,
            **counts,
            supervised=booking.supervised,
            fee_units=units,
            special_admissions=special,
        )
    else:
        units = state.pending_fee_units + (booking.children if booking.children else 1)
        lines = [Line("Cancellation fee", units, Decimal("3.00"), False)]
        if type(data.get("charge_fee")) is not bool:
            raise ValidationError(
                "Explicitly choose whether to charge the cancellation/no-show fee."
            )
    no_charge = state.comped or (kind != "arrival" and not data["charge_fee"])
    if no_charge:
        lines = [Line(line.label, line.quantity, ZERO, line.taxable) for line in lines]
        quote = quote_lines(lines, saved.policy, card_base=ZERO)
        plan = []
    else:
        method = data.get("method", "card")
        from .zelle import facts as zelle_facts
        from .zelle import plan_with_prepayment

        prepaid = zelle_facts(booking)
        quote, plan, _ = plan_with_prepayment(
            saved.policy, lines, method, data.get("split"), prepaid["available"]
        )
    from .zelle import facts as zelle_facts

    prepaid = zelle_facts(booking)
    if any(part["tender"] == "card" for part in plan):
        try:
            agreement = booking.card_agreement
        except Booking.card_agreement.RelatedObjectDoesNotExist:
            raise ValidationError(
                "No card is bound to this booking. Complete or replace its card setup first."
            ) from None
        if agreement.method.state != "active":
            raise ValidationError("The saved card requires replacement or review before charging.")
        card_identity = str(agreement.method_id)
    else:
        card_identity = None
    from .receipts import receipt_date, sender

    manual = any(part["tender"] != "card" and not part.get("advance") for part in plan)
    zelle = any(part["tender"] == "zelle" and not part.get("advance") for part in plan)
    received_on = receipt_date(data.get("received_on")) if manual else None
    zelle_sender = (
        sender(data.get("zelle_sender", booking.zelle_sender), required=zelle) if zelle else ""
    )
    facts = {
        "prepayments": prepaid["identity"],
        "send_email": data.get("send_email", False),
        "received_on": received_on.isoformat() if received_on else None,
        "zelle_sender": zelle_sender,
        "booking": booking.pk,
        "version": booking.edit_version,
        "billing_revision": state.revision,
        "kind": kind,
        "reopen_affected_sessions": reopen,
        "method_id": card_identity,
        "counts": counts,
        "override_capacity": override,
        "fee_units": units,
        "waiver_confirmed": data.get("waiver_confirmed") is True,
        "comped": state.comped,
        "owner_special_admissions": str(special)
        if kind == "arrival" and special is not None
        else None,
        "charge_fee": data.get("charge_fee"),
        "quote": quote,
        "plan": [
            {"tender": p["tender"], "amount": p["amount"], "advance": bool(p.get("advance"))}
            for p in plan
        ],
    }
    return booking, state, quote, plan, facts, fingerprint(facts)


@transaction.atomic
def confirm(*, actor, booking_id, kind, data, request_key, reviewed_hash, confirmed):
    authorize(actor)
    if confirmed is not True:
        raise ValidationError("Explicitly confirm the reviewed attendance and payment action.")
    key = lock_request(request_key)
    previous = BookingCheckout.objects.filter(request_key=key).first()
    if previous:
        if (
            previous.booking_id != booking_id
            or previous.kind != kind
            or previous.actor_id != actor.pk
            or previous.fingerprint != reviewed_hash
        ):
            raise ValidationError("This confirmation has already been used for a different action.")
        return previous
    lock_calendar(exclusive=data.get("reopen_affected_sessions") is True)
    booking = Booking.objects.select_for_update().get(pk=booking_id)
    Session.objects.select_for_update().get(pk=booking.session_id)
    booking, state, quote, plan, facts, digest = preview(
        actor=actor, booking_id=booking_id, kind=kind, data=data
    )
    if digest != reviewed_hash:
        raise ValidationError(
            "The booking or reviewed price changed. Review it again before confirming."
        )
    if PaymentOperation.objects.filter(
        sale__booking=booking, state__in=["ready", "sending", "unknown", "action", "succeeded"]
    ).exists():
        raise ValidationError(
            "Resolve earlier payment operations before confirming another action."
        )
    before = snapshot(booking)
    previous_special = state.special_subtotal
    if kind == "arrival":
        for field, value in facts["counts"].items():
            setattr(booking, field, value)
        booking.attendance = "arrived"
        booking.setup_pending = False
    else:
        booking.attendance = "cancelled" if kind == "cancellation" else "no_show"
    booking.edit_version += 1
    booking.save()
    if facts["reopen_affected_sessions"]:
        from core.session_blocks import reopen_for_booking

        reopen_for_booking(actor, booking, booking.session)
    if state.pk is None:
        state.booking = booking
    if kind == "arrival" and facts["owner_special_admissions"] is not None:
        state.special_subtotal = amount(facts["owner_special_admissions"])
    state.pending_fee_units = facts["fee_units"] if kind == "arrival" else 0
    state.revision += 1
    state.save()
    if kind == "arrival":
        from .comped import notify_count_change

        notify_count_change(
            actor=actor, booking=booking, before=before, special=state.special_subtotal
        )
        if previous_special != state.special_subtotal:
            AuditEvent.objects.create(
                actor=actor,
                action="booking.owner_price_changed",
                record_type="booking",
                record_id=str(booking.reference),
                changes={
                    "special_admissions": {
                        "before": str(previous_special),
                        "after": str(state.special_subtotal),
                    }
                },
            )
    if kind == "arrival":
        review, _ = BookingWaiverReview.objects.get_or_create(booking=booking)
        review.coverage_confirmed = True
        review.revision += 1
        review.save(update_fields=["coverage_confirmed", "revision", "updated_at"])
    quote["sale_kind"] = "visit" if kind == "arrival" else "cancellation"
    saved = BookingQuote.objects.create(
        booking=booking,
        policy=booking.quotes.first().policy,
        revision=booking.edit_version,
        snapshot=quote,
        actor=actor,
    )
    sale = None
    if amount(quote["total"]):
        sale = accept_booking_sale(
            actor=actor,
            booking_id=booking.pk,
            quote_id=saved.pk,
            creation_key=key,
            kind=quote["sale_kind"],
        )
    checkout = BookingCheckout.objects.create(
        request_key=key,
        fingerprint=digest,
        booking=booking,
        sale=sale,
        kind=kind,
        booking_version=booking.edit_version,
        details=facts,
        actor=actor,
    )
    if sale:
        lines = list(sale.lines.all())
        for position, part in enumerate(plan):
            if part.get("advance"):
                from .zelle import apply_receipts

                apply_receipts(actor=actor, booking=booking, sale=sale, part=part, key=key)
                continue
            allocation = [
                {
                    "line": str(line.pk),
                    **{component: str(part["parts"][i][component]) for component in COMPONENTS},
                }
                for i, line in enumerate(lines)
            ]
            if not amount(part["amount"]):
                continue
            op = request_operation(
                actor=actor,
                sale_id=sale.pk,
                request_key=uuid.uuid5(key, "tender:" + str(position)),
                tender=part["tender"],
                allocation=allocation,
                method_id=booking.card_agreement.method_id if part["tender"] == "card" else None,
                purpose="arrival" if kind == "arrival" else kind,
                received_on=date.fromisoformat(facts["received_on"])
                if part["tender"] != "card"
                else None,
            )
            if part["tender"] == "card":
                enqueue(kind="payment_dispatch", reference=op.pk, key="dispatch:" + str(op.pk))
            else:
                record_manual(actor=actor, operation_id=op.pk, received=True)
    AuditEvent.objects.create(
        actor=actor,
        action="booking." + kind + "_confirmed",
        record_type="booking",
        record_id=str(booking.reference),
        changes={
            "before": before,
            "after": snapshot(booking),
            "checkout_id": str(checkout.pk),
            "total": quote["total"],
            "capacity_override": facts["override_capacity"],
            "fee_units": facts["fee_units"],
            "fee_charged": kind != "arrival" and bool(sale),
        },
    )
    if kind != "arrival" and facts["send_email"]:
        from core.communications.services import enqueue_closure

        enqueue_closure(booking=booking, checkout=checkout, actor=actor)
    resolve_if_settled(booking.pk)
    return checkout


@transaction.atomic
def resolve_if_settled(booking_id):
    booking = Booking.objects.select_for_update().get(pk=booking_id)
    if booking.workflow != "integrated_v1" or not booking.attendance:
        return False
    checkout = booking.checkouts.select_related("sale").order_by("-created_at").first()
    if checkout is None:
        return False
    if PaymentOperation.objects.filter(
        sale__booking=booking, state__in=["ready", "sending", "unknown", "action"]
    ).exists():
        return False
    from .zelle import facts as zelle_facts

    if zelle_facts(booking)["refund_due"]:
        return False
    if checkout.sale and received(checkout.sale) < total(checkout.sale):
        return False
    PaymentFollowup.objects.filter(
        operation__sale__booking=booking, resolved_at__isnull=True
    ).update(resolved_at=timezone.now())
    BookingChargeState.objects.filter(booking=booking).update(pending_fee_units=0)
    try:
        agreement = booking.card_agreement
    except Booking.card_agreement.RelatedObjectDoesNotExist:
        return True
    if agreement.resolved_at is None:
        agreement.resolved_at = timezone.now()
        agreement.save(update_fields=["resolved_at"])
        queue_disposal(agreement.method)
    return True


@transaction.atomic
def note_followup(*, actor, operation_id, plan):
    from .models import PaymentEvent

    authorize(actor)
    if plan not in dict(PaymentFollowup._meta.get_field("plan").choices):
        raise ValidationError("Choose an available payment follow-up action.")
    operation = PaymentOperation.objects.select_for_update().get(pk=operation_id)
    if operation.state not in {"unknown", "action", "declined", "sending"}:
        raise ValidationError("This payment no longer needs that follow-up action.")
    followup, _ = PaymentFollowup.objects.select_for_update().get_or_create(
        operation=operation, defaults={"plan": "owner_review"}
    )
    before = followup.plan
    followup.plan = plan
    followup.actor = actor
    followup.save(update_fields=["plan", "actor", "updated_at"])
    PaymentEvent.objects.create(
        operation=operation, state=operation.state, source="staff", code="plan_" + plan, actor=actor
    )
    AuditEvent.objects.create(
        actor=actor,
        action="payment.followup_recorded",
        record_type="payment",
        record_id=str(operation.pk),
        changes={"plan": {"before": before, "after": plan}},
    )
    return followup


def summary(booking):
    from .zelle import facts as zelle_facts

    prepaid = zelle_facts(booking)
    state = charge_state(booking)
    checkout = booking.checkouts.select_related("sale").order_by("-created_at").first()
    if checkout is None:
        return {
            "zelle": prepaid,
            "status": "Comped" if state.comped else "Due at arrival",
            "received": prepaid["received"],
            "due": ZERO if state.comped else None,
            "sale": None,
            "pending": False,
        }
    sale = checkout.sale
    if sale is None:
        return {
            "zelle": prepaid,
            "status": "Zelle refund due"
            if prepaid["refund_due"]
            else "Comped"
            if state.comped
            else "No fee",
            "received": ZERO,
            "due": ZERO,
            "sale": None,
            "pending": False,
        }
    operations = sale.operations.all()
    expected = total(sale)
    paid = received(sale)
    due = max(ZERO, expected - paid)
    pending = operations.filter(state__in=["ready", "sending", "unknown", "action"]).exists()
    external_review = operations.filter(
        events__code="external_correction_review", followup__resolved_at__isnull=True
    ).exists()
    corrected = operations.exclude(kind="receipt").exists() or external_review
    if corrected:
        status = "Payment correction requires owner review"
    elif operations.filter(state="unknown").exists():
        status = "Outcome unknown — review required"
    elif operations.filter(state="action").exists():
        status = "Authentication or review required"
    elif pending:
        status = "Charge pending"
    elif not due:
        status = "Paid"
    elif operations.filter(state="declined").exists():
        status = "Card declined — balance unpaid"
    else:
        status = "Partially paid" if paid else "Unpaid"
    if prepaid["refund_due"]:
        status = "Zelle refund due"
    return {
        "zelle": prepaid,
        "status": status,
        "received": paid,
        "due": None if corrected else due,
        "total": expected,
        "sale": sale,
        "pending": pending,
        "operations": operations.order_by("-requested_at"),
        "can_collect": bool(due and not pending and not corrected),
        "can_retry": bool(
            due
            and not pending
            and not corrected
            and operations.filter(kind="receipt", tender="card", state="declined").exists()
        ),
    }
