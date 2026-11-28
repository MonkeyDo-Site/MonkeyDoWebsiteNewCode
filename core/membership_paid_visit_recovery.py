"""Explicit, same-day replacement card requests for a reserved paid visit.

This authority covers only the original accepted remainder and card fee. It
neither changes future billing nor releases uncertain original funds.
"""

import uuid
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.utils import timezone

from .membership_paid_visit_records import MembershipPaidVisitIntent, MembershipPaidVisitRecovery
from .payments.ledger import fingerprint, lock_request


def available():
    with connection.cursor() as cursor:
        return "core_membershippaidvisitrecovery" in connection.introspection.table_names(cursor)


def latest(intent):
    if available():
        return (
            intent.recoveries.select_related("operation", "method", "actor")
            .order_by("-sequence")
            .first()
        )
    return None


def current_operation(intent):
    from .membership_paid_visit_split import latest as split_latest
    from .membership_paid_visit_split import plan as split_plan

    split = split_plan(intent)
    if split:
        attempt = split_latest(split)
        return attempt.operation if attempt else None
    from .membership_paid_visit_manual import current_operation as manual_operation

    manual = manual_operation(intent)
    if manual is not None:
        return manual
    recovery = latest(intent)
    return recovery.operation if recovery else intent.operation


def cards(intent):
    from .membership_payments import available_cards
    from .models import PaymentMethod

    ids = list(available_cards(intent.purchase).values_list("pk", flat=True))
    from .membership_paid_visit_new_card import scoped_methods

    ids.extend(scoped_methods(intent).values_list("pk", flat=True))
    # The originally accepted nonretained card also belongs to this exact purchase.
    if intent.operation_id:
        ids.append(intent.operation.method_id)
    return PaymentMethod.objects.filter(
        pk__in=ids,
        customer_id=intent.purchase.customer_id,
        environment="sandbox",
        state="active",
        provider_method__isnull=False,
    ).order_by("last_four", "pk")


def source_review(*, actor, intent_id, ignore_storage=False):
    from .membership_paid_visit_pending import fresh
    from .membership_sales import authorize
    from .permissions import require_actor

    authorize(actor, collect=True)
    require_actor(actor, "core.change_booking")
    if not available():
        raise ValidationError("Complete the reviewed payment-recovery upgrade first.")
    intent = MembershipPaidVisitIntent.objects.select_related(
        "purchase__membership", "operation"
    ).get(pk=intent_id)
    from .membership_paid_visit_split import plan as split_plan

    if split_plan(intent):
        raise ValidationError(
            "A partial payment is recorded. Use the exact remaining-card controls instead."
        )
    fresh(intent)
    current = current_operation(intent)
    if not current or current.state not in {"declined", "cancelled"}:
        raise ValidationError(
            "Check the existing card outcome before another attempt. No new payment was requested."
        )
    sale = intent.purchase.installments.first().invoice.sale
    operations = list(sale.operations.order_by("requested_at", "pk"))
    if any(op.kind != "receipt" or op.state not in {"declined", "cancelled"} for op in operations):
        raise ValidationError(
            "Reconcile the existing membership money and corrections before another card attempt."
        )
    if not ignore_storage:
        from .membership_paid_visit_new_card import require_known_storage

        require_known_storage(intent)
    recovery = latest(intent)
    data = dict(
        intent=str(intent.pk),
        accepted_offer=intent.fingerprint,
        actor=actor.pk,
        previous=str(current.pk),
        sequence=recovery.sequence + 1 if recovery else 1,
        amount=str(current.amount),
        allocation=current.allocation,
        visit=intent.booking_id,
        source=str(intent.source_sale_id),
        operations=[dict(id=str(op.pk), state=op.state, kind=op.kind) for op in operations],
    )
    return intent, data


def review(*, actor, intent_id, method_id):
    intent, data = source_review(actor=actor, intent_id=intent_id)
    method = cards(intent).filter(pk=method_id).first()
    if method is None:
        raise ValidationError("Choose an available saved card belonging to this customer.")
    data["method"] = str(method.pk)
    return data | dict(fingerprint=fingerprint(data))


@transaction.atomic
def request(*, actor, intent_id, method_id, request_key, reviewed, confirmed):
    from .membership_paid_visit_pending import locked
    from .membership_sales import authorize
    from .models import AuditEvent
    from .payments.jobs import enqueue
    from .payments.ledger import request_operation, writes_allowed
    from .permissions import require_actor

    authorize(actor, collect=True)
    require_actor(actor, "core.change_booking")
    writes_allowed()
    if not available():
        raise ValidationError("Complete the reviewed payment-recovery upgrade first.")
    key = lock_request(request_key)
    prior = MembershipPaidVisitRecovery.objects.filter(pk=key).first()
    if prior:
        if (
            str(prior.intent_id) != str(intent_id)
            or str(prior.method_id) != str(method_id)
            or prior.actor_id != actor.pk
            or prior.fingerprint != reviewed
            or confirmed is not True
        ):
            raise ValidationError("This recovery identity belongs to another reviewed action.")
        return prior
    intent = locked(intent_id)
    if confirmed is not True:
        raise ValidationError("Confirm that the customer authorizes this exact card payment.")
    data = review(actor=actor, intent_id=intent.pk, method_id=method_id)
    if data["fingerprint"] != reviewed:
        raise ValidationError(
            "The card or payment outcome changed. Review it again before confirming."
        )
    recovery = MembershipPaidVisitRecovery.objects.create(
        id=key,
        intent=intent,
        sequence=data["sequence"],
        previous_id=uuid.UUID(data["previous"]),
        operation_id=uuid.uuid5(key, "paid-visit-card-payment"),
        method_id=method_id,
        actor=actor,
        fingerprint=reviewed,
        review=data,
        expires_at=timezone.now() + timedelta(minutes=30),
    )
    operation = request_operation(
        actor=actor,
        sale_id=intent.purchase.installments.first().invoice.sale_id,
        request_key=recovery.operation_id,
        tender="card",
        method_id=method_id,
        purpose="member_purchase",
        allocation=data["allocation"],
        paid_visit_recovery=recovery,
    )
    from .membership_paid_visit_new_card import confirm_future_use

    confirm_future_use(intent=intent, method_id=method_id, actor=actor)
    enqueue(kind="payment_dispatch", reference=operation.pk, key=f"dispatch:{operation.pk}")
    AuditEvent.objects.create(
        actor=actor,
        action="membership.paid_visit_card_requested",
        record_type="membership",
        record_id=str(intent.purchase_id),
        changes=dict(recovery=str(key), operation=str(operation.pk), previous=data["previous"]),
    )
    return recovery


def authorize_receipt(recovery, *, invoice, actor, request_key, method_id, tender, allocation):
    if not isinstance(recovery, MembershipPaidVisitRecovery) or not available():
        raise PermissionDenied
    saved = MembershipPaidVisitRecovery.objects.select_related("intent", "previous").get(
        pk=recovery.pk
    )
    if (
        saved.intent.purchase_id != invoice.installment.purchase_id
        or invoice.installment.number != 1
        or actor is None
        or actor.pk != saved.actor_id
        or tender != "card"
        or request_key != saved.operation_id
        or str(method_id) != str(saved.method_id)
        or allocation != saved.review["allocation"]
        or saved.fingerprint
        != fingerprint({k: v for k, v in saved.review.items() if k != "fingerprint"})
        or saved.previous.state not in {"declined", "cancelled"}
    ):
        raise ValidationError("Use only the exact newly reviewed paid-visit card authority.")
    from .membership_paid_visit_records import MembershipPaidVisitRelease

    if MembershipPaidVisitRelease.objects.filter(intent=saved.intent).exists():
        raise ValidationError("This visit application has already ended.")


def authorize_dispatch(intent, operation):
    """Fresh authority expiry is independent of the original purchase's expiry."""
    from .membership_paid_visit_pending import fresh
    from .membership_sales import authorize
    from .permissions import require_actor

    recovery = latest(intent)
    if recovery is None:
        return None
    if operation.pk != recovery.operation.pk:
        raise ValidationError("Only the latest explicitly reviewed card request may continue.")
    authorize(recovery.actor, collect=True)
    require_actor(recovery.actor, "core.change_booking")
    if timezone.now() >= recovery.expires_at:
        raise ValidationError("This unattempted recovery request expired; review a new request.")
    if recovery.previous.state not in {"declined", "cancelled"}:
        raise ValidationError("The previous card outcome needs review before this request.")
    fresh(intent)
    return recovery


def controls(*, actor, pending):
    if (
        not pending
        or pending["stopped"]
        or not pending["operation"]
        or pending["operation"].state not in {"declined", "cancelled"}
    ):
        return None
    intent = pending["intent"]
    choices = []
    for method in cards(intent):
        try:
            data = review(actor=actor, intent_id=intent.pk, method_id=method.pk)
        except (ValidationError, PermissionDenied):
            continue
        choices.append(
            dict(
                value=f"{method.pk}:{data['fingerprint']}",
                label=f"{method.brand or 'Card'} ending in {method.last_four}",
            )
        )
    if not choices:
        return None
    return dict(choices=choices, key=uuid.uuid4(), amount=pending["card_amount"])
