"""Reserve an original paid visit until its separately authorized card remainder is known.

A source reservation is not customer credit, a refund or another receipt. The
original visit stays intact until a separate atomic, idempotent completion.
"""

import copy
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.utils import timezone

from .membership_paid_visit_records import MembershipPaidVisitIntent, MembershipPaidVisitRelease
from .payments.amounts import ZERO, amount
from .payments.ledger import fingerprint, lock_request, lock_sale

CARD_MARKER = "paid_visit_card"


def available():
    # The shared ledger also reads historical data during reviewed upgrades.
    # A sales switch does not imply that this newer table already exists.
    with connection.cursor() as cursor:
        return "core_membershippaidvisitintent" in connection.introspection.table_names(cursor)


def active():
    return MembershipPaidVisitIntent.objects.filter(release__isnull=True)


def protect_conversion(booking_id, intent=None):
    if not available():
        return
    reserved = active().filter(booking_id=booking_id).first()
    if reserved is None:
        if intent is not None:
            raise ValidationError("This paid-visit reservation is no longer pending.")
        return
    if not isinstance(intent, MembershipPaidVisitIntent) or intent.pk != reserved.pk:
        raise ValidationError(
            "This paid visit is reserved for an existing membership card payment. Open that membership before another conversion."
        )


def protect_source(original):
    if available() and active().filter(source_sale_id=original.sale_id).exists():
        raise ValidationError(
            "This visit's funds are reserved for a membership payment. Reconcile or stop that application before a separate refund or conversion."
        )


def authorize_receipt(
    *, invoice, actor, request_key, tender, allocation, recovery=None, method_id=None, manual=None
):
    """All generic collection paths must respect the accepted conditional source."""
    member = invoice.installment.purchase
    marker = member.membership.snapshot.get(CARD_MARKER)
    if manual is not None:
        if not marker or recovery is not None:
            raise PermissionDenied
        from .membership_paid_visit_manual import authorize_receipt as authorize_manual

        return authorize_manual(
            manual,
            invoice=invoice,
            actor=actor,
            request_key=request_key,
            tender=tender,
            method_id=method_id,
            allocation=allocation,
        )
    if recovery is not None:
        if not marker:
            raise PermissionDenied
        from .membership_paid_visit_recovery import authorize_receipt as authorize_recovery

        return authorize_recovery(
            recovery,
            invoice=invoice,
            actor=actor,
            request_key=request_key,
            method_id=method_id,
            tender=tender,
            allocation=allocation,
        )
    if not marker:
        return
    if invoice.installment.number != 1:
        if (
            not available()
            or not MembershipPaidVisitRelease.objects.filter(
                intent__purchase=member, kind="completed"
            ).exists()
        ):
            raise ValidationError(
                "Complete the original paid-visit application before later collection."
            )
        return
    if (
        available()
        and MembershipPaidVisitRelease.objects.filter(
            intent__purchase=member, kind="stopped"
        ).exists()
    ):
        raise ValidationError(
            "This visit application was stopped. Review the membership separately before new collection."
        )
    line = invoice.sale.lines.get()
    fee = amount(invoice.installment.quote["processing_fee"])
    expected = [
        dict(
            line=str(line.pk),
            net=str(amount(marker["new_payment"]) - fee),
            fee=str(fee),
            item_tax="0.00",
            fee_tax="0.00",
        )
    ]
    if (
        actor is None
        or actor.pk != member.actor_id
        or tender != "card"
        or request_key != uuid.uuid5(member.request_key, "first-payment")
        or allocation != expected
    ):
        raise ValidationError(
            "Use only the card remainder accepted with this paid visit; do not collect its original funds again."
        )


def protect_generic_payment(member):
    if (
        member.membership.snapshot.get(CARD_MARKER)
        and not MembershipPaidVisitRelease.objects.filter(
            intent__purchase=member, kind="completed"
        ).exists()
    ):
        raise ValidationError(
            "Use the paid-visit application controls and check the existing card outcome. The reserved original visit amount must not be collected again."
        )


def locked(intent_id):
    from .calendar import lock_calendar
    from .membership_reservations import lock_customer
    from .models import Booking, Session

    intent = MembershipPaidVisitIntent.objects.get(pk=intent_id)
    lock_calendar()
    booking = Booking.objects.select_for_update().get(pk=intent.booking_id)
    Session.objects.select_for_update().get(pk=booking.session_id)
    lock_customer(booking.customer_id)
    lock_sale(intent.source_sale_id)
    return MembershipPaidVisitIntent.objects.select_related(
        "purchase__membership", "purchase__billing_state__mandate", "actor", "operation", "booking"
    ).get(pk=intent_id)


def lock_operation(operation):
    if operation.kind != "receipt" or operation.sale.kind != "membership" or not available():
        return None
    intent = MembershipPaidVisitIntent.objects.filter(
        purchase__installments__invoice__sale_id=operation.sale_id,
        purchase__installments__number=1,
    ).first()
    return locked(intent.pk) if intent else None


def restored_offer(intent):
    data = copy.deepcopy(intent.offer)
    data["cycles"] = [
        dict(
            number=row.number, starts_on=row.starts_on, ends_on=row.ends_on, charge_on=row.charge_on
        )
        for row in intent.purchase.membership.cycles.all()
    ]
    return data


def fresh(intent, *, dispatch=False):
    from .membership_arrival import ProposedMembership
    from .membership_conversion import review
    from .membership_sales import authorize
    from .payments.ledger import writes_allowed

    authorize(intent.actor, collect=True)
    writes_allowed()
    from .membership_funding import member_needs_review

    if member_needs_review(intent.purchase):
        raise ValidationError(
            "A recorded membership payment needs reconciliation before applying visit funds."
        )
    if intent.purchase.cancellations.exists() or intent.purchase.billing_state.stopped_on:
        raise ValidationError("This membership has a cancellation that needs owner reconciliation.")
    if MembershipPaidVisitRelease.objects.filter(intent=intent).exists():
        raise ValidationError("This paid-visit application has already been completed or stopped.")
    if dispatch and timezone.now() >= intent.expires_at:
        raise ValidationError(
            "This unattempted card request has expired; review it before continuing."
        )
    # The original operation retains its accepted card. A later mandate is for
    # future installments; dispatch validates the original method itself.
    data = restored_offer(intent)
    current = review(
        actor=intent.actor,
        booking_id=intent.booking_id,
        proposed_membership=ProposedMembership(data, recorded_purchase_id=intent.purchase_id),
        paid_intent=intent,
    )
    if current["fingerprint"] != data["paid_visit"]["conversion"]["fingerprint"]:
        raise ValidationError(
            "The paid visit or its funds changed. The original visit remains unchanged pending owner review."
        )
    return data


def allow_dispatch(intent, operation=None):
    if intent is None:
        return True
    try:
        from .membership_paid_visit_recovery import authorize_dispatch

        if operation is None or authorize_dispatch(intent, operation) is None:
            fresh(intent, dispatch=True)
    except (ValidationError, PermissionDenied):
        mark_review(intent.pk)
        return False
    return True


def create(*, actor, member, offer, invoice, method):
    from .payments.jobs import enqueue
    from .payments.ledger import request_operation

    if not available():
        raise ValidationError("Complete the reviewed paid-visit card upgrade before this purchase.")
    marker = offer["paid_visit"]
    operation = None
    if amount(marker["new_payment"]):
        line = invoice.sale.lines.get()
        fee = amount(invoice.installment.quote["processing_fee"])
        operation = request_operation(
            actor=actor,
            sale_id=invoice.sale_id,
            request_key=uuid.uuid5(member.request_key, "first-payment"),
            tender="card",
            method_id=method.pk,
            purpose="member_purchase",
            allocation=[
                dict(
                    line=str(line.pk),
                    net=str(amount(marker["new_payment"]) - fee),
                    fee=str(fee),
                    item_tax="0.00",
                    fee_tax="0.00",
                )
            ],
        )
    data = {key: value for key, value in offer.items() if key != "cycles"}
    intent = MembershipPaidVisitIntent.objects.create(
        id=uuid.uuid5(member.request_key, "paid-visit-intent"),
        purchase=member,
        booking_id=marker["booking"],
        source_sale_id=marker["conversion"]["sale"],
        operation=operation,
        conversion_key=uuid.uuid5(member.request_key, "paid-visit-conversion"),
        fingerprint=member.fingerprint,
        offer=data,
        actor=actor,
        expires_at=timezone.now() + timedelta(minutes=30),
    )
    if operation:
        enqueue(kind="payment_dispatch", reference=operation.pk, key=f"dispatch:{operation.pk}")
    else:
        complete(intent.pk)
    return intent


def queue_ready(member):
    if not settings.MEMBERSHIP_SALES_ENABLED or not available():
        return
    intent = active().filter(purchase=member).first()

    from .membership_paid_visit_manual import is_funded

    if intent and is_funded(intent):
        from .payments.jobs import enqueue

        enqueue(
            kind="membership_paid_visit", reference=intent.pk, key=f"paid-visit-funded:{intent.pk}"
        )


def release_completed(intent, conversion):
    release = MembershipPaidVisitRelease.objects.create(
        intent=intent,
        request_key=uuid.uuid5(intent.pk, "completed"),
        kind="completed",
        conversion=conversion,
        actor=intent.actor,
    )
    resolve_notices(intent, intent.actor)
    return release


@transaction.atomic
def _complete(intent_id):
    from .membership_paid_visit import complete_purchase

    intent = locked(intent_id)
    released = MembershipPaidVisitRelease.objects.filter(intent=intent).first()
    if released:
        return released
    data = fresh(intent)
    from .membership_paid_visit_recovery import current_operation

    current = current_operation(intent)
    from .membership_paid_visit_manual import require_funded

    manual_funded = require_funded(intent)
    if not manual_funded and current and current.state != "succeeded":
        raise ValidationError(
            "Check the existing membership card outcome before applying the visit."
        )
    first = intent.purchase.installments.first()
    if first.invoice.sale.operations.exclude(
        kind="receipt", state__in=["succeeded", "declined", "cancelled"]
    ).exists():
        raise ValidationError(
            "A membership payment correction needs review before applying the visit."
        )
    complete_purchase(
        actor=intent.actor,
        member=intent.purchase,
        offer=data,
        invoice=first.invoice,
        paid_intent=intent,
    )
    from .payments.models import PaymentFollowup

    PaymentFollowup.objects.filter(
        operation__sale=first.invoice.sale, resolved_at__isnull=True
    ).update(resolved_at=timezone.now())
    return MembershipPaidVisitRelease.objects.get(intent=intent)


def complete(intent_id):
    try:
        return _complete(intent_id)
    except Exception:
        # The receipt committed separately; alert on a failed pure continuation.
        mark_review(intent_id)
        raise


@transaction.atomic
def mark_review(intent_id):
    from .membership_reservations import lock_customer
    from .models import OwnerNotice

    intent = MembershipPaidVisitIntent.objects.select_related("purchase").get(pk=intent_id)
    lock_customer(intent.purchase.customer_id)
    if MembershipPaidVisitRelease.objects.filter(intent=intent).exists():
        return
    OwnerNotice.objects.get_or_create(
        reviewed_at__isnull=True,
        customer_id=intent.purchase.customer_id,
        subject="Paid visit membership application needs review",
        details=dict(
            kind="paid_visit_membership", intent=str(intent.pk), membership=intent.purchase_id
        ),
    )


def resolve_notices(intent, actor):
    from .models import OwnerNotice

    OwnerNotice.objects.filter(
        details__kind="paid_visit_membership",
        details__intent=str(intent.pk),
        reviewed_at__isnull=True,
    ).update(reviewed_at=timezone.now(), reviewed_by=actor)


def outcome_updated(operation):
    if operation.sale.kind == "membership" and available():
        intent = active().filter(purchase__installments__invoice__sale_id=operation.sale_id).first()
        if intent and operation.state in {"declined", "unknown", "action"}:
            mark_review(intent.pk)


def stop_facts(intent):
    operations = list(intent.purchase.installments.first().invoice.sale.operations.order_by("pk"))
    receipts = sum(
        (op.amount for op in operations if op.kind == "receipt" and op.state == "succeeded"), ZERO
    )
    returned = sum(
        (op.amount for op in operations if op.kind != "receipt" and op.state == "succeeded"), ZERO
    )
    from .membership_paid_visit_manual import plan as manual_plan
    from .membership_paid_visit_new_card import pending as storage_pending
    from .membership_records import MembershipCancellation

    cancelled_manual = bool(
        manual_plan(intent)
        and MembershipCancellation.objects.filter(purchase_id=intent.purchase_id).exists()
    )
    allowed = (
        not cancelled_manual
        and not storage_pending(intent)
        and not any(op.state in {"sending", "unknown", "action"} for op in operations)
        and not any(op.kind != "receipt" and op.state == "ready" for op in operations)
        and receipts == returned
    )
    data = dict(
        intent=str(intent.pk),
        offer=intent.fingerprint,
        operations=[
            dict(id=str(op.pk), state=op.state, kind=op.kind, amount=str(op.amount))
            for op in operations
        ],
    )
    return data | dict(fingerprint=fingerprint(data), allowed=allowed)


@transaction.atomic
def stop(*, actor, intent_id, request_key, reviewed, reason):
    from .membership_sales import authorize
    from .models import AuditEvent, PaymentEvent, PaymentOperation
    from .payments.ledger import writes_allowed
    from .permissions import require_actor

    authorize(actor, collect=True)
    require_actor(actor, "core.change_booking", owner=True)
    writes_allowed()
    key = lock_request(request_key)
    prior = MembershipPaidVisitRelease.objects.filter(request_key=key).first()
    if prior:
        if (
            str(prior.intent_id) != str(intent_id)
            or prior.kind != "stopped"
            or prior.actor_id != actor.pk
            or prior.reason != str(reason).strip()
        ):
            raise ValidationError("This stop identity belongs to another action.")
        return prior
    intent = locked(intent_id)
    if MembershipPaidVisitRelease.objects.filter(intent=intent).exists():
        raise ValidationError("This application was already completed or stopped.")
    if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 500:
        raise ValidationError("Enter a short owner reason for releasing these visit funds.")
    data = stop_facts(intent)
    if data["fingerprint"] != reviewed or not data["allowed"]:
        raise ValidationError(
            "Reconcile the existing card outcome and any money still held before releasing visit funds."
        )
    from .membership_paid_visit_recovery import current_operation

    current = current_operation(intent)
    if current:
        op = PaymentOperation.objects.select_for_update().get(pk=current.pk)
        if op.state == "ready":
            op.state = "cancelled"
            op.result_code = "paid_visit_stopped"
            op.completed_at = timezone.now()
            op.save(update_fields=["state", "result_code", "completed_at"])
            PaymentEvent.objects.create(
                operation=op,
                state="cancelled",
                source="staff",
                code="paid_visit_stopped",
                actor=actor,
            )
    release = MembershipPaidVisitRelease.objects.create(
        intent=intent, request_key=key, kind="stopped", reason=reason.strip(), actor=actor
    )
    resolve_notices(intent, actor)
    AuditEvent.objects.create(
        actor=actor,
        action="membership.paid_visit_stopped",
        record_type="membership",
        record_id=str(intent.purchase_id),
        changes=dict(intent=str(intent.pk), reason=reason.strip()),
    )
    return release


def context(member):
    if not available():
        return None
    intent = (
        MembershipPaidVisitIntent.objects.select_related("operation", "booking")
        .filter(purchase=member)
        .first()
    )
    if not intent:
        return None
    release = MembershipPaidVisitRelease.objects.filter(intent=intent).first()
    if release and release.kind == "completed":
        return None
    can_complete = False
    from .membership_paid_visit_recovery import current_operation

    operation = current_operation(intent)
    if not release and (not operation or operation.state == "succeeded"):
        try:
            fresh(intent)
            from .membership_paid_visit_manual import require_funded

            require_funded(intent)
            can_complete = True
        except (ValidationError, PermissionDenied):
            pass
    facts = stop_facts(intent)
    return dict(
        intent=intent,
        stopped=bool(release),
        operation=operation,
        source_amount=intent.offer["paid_visit"]["applied"],
        card_amount=intent.offer["paid_visit"]["new_payment"],
        can_complete=can_complete,
        can_stop=not release and facts["allowed"],
        stop_reviewed=facts["fingerprint"],
        stop_key=uuid.uuid4(),
    )
