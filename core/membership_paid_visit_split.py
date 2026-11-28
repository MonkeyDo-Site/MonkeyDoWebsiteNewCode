"""A received partial remainder stays recorded while its explicit card balance resolves."""

import logging
import uuid
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from .membership_paid_visit_split_records import (
    MembershipPaidVisitSplit,
    MembershipPaidVisitSplitCard,
)
from .payments.amounts import ZERO, amount
from .payments.ledger import fingerprint, lock_request, lock_sale
from .pricing import money

logger = logging.getLogger(__name__)


def available():
    # Financial mutations require the reviewed PostgreSQL guards, not merely a
    # sales flag or tables left over from an incomplete upgrade.
    if connection.vendor != "postgresql":
        return False
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT to_regclass('core_membershippaidvisitsplit') IS NOT NULL AND to_regclass('core_membershippaidvisitsplitcard') IS NOT NULL AND to_regprocedure('monkeydo_paid_visit_split_scope()') IS NOT NULL"
        )
        return cursor.fetchone()[0]


def plan(intent):
    if not available():
        return None
    return (
        MembershipPaidVisitSplit.objects.select_related("operation").filter(intent=intent).first()
    )


def latest(split):
    return split.card_attempts.select_related("operation", "method").order_by("-sequence").first()


def portions(*, principal, original_fee, manual, rate):
    principal, original_fee, manual = amount(principal), amount(original_fee), amount(manual)
    if not ZERO < manual < principal:
        raise ValidationError(
            "Enter a received amount above zero and below the remaining principal. Use the full-payment controls for a single payment method."
        )
    card_net = principal - manual
    fee = money(card_net * rate)
    if fee > original_fee:
        raise ValidationError("Review the original card fee before splitting this remainder.")
    return dict(
        manual_net=str(manual),
        card_net=str(card_net),
        card_fee=str(fee),
        card_total=str(card_net + fee),
        fee_removed=str(original_fee - fee),
        new_payment=str(manual + card_net + fee),
    )


def authorize(actor):
    from .membership_sales import authorize as membership_authorize
    from .permissions import require_actor

    membership_authorize(actor, collect=True)
    require_actor(actor, "core.change_booking")
    if not available():
        raise ValidationError(
            "Complete the reviewed split-remainder upgrade before using this payment option."
        )


def review(*, actor, intent_id, manual_amount, tender, method_id, received_on=None, sender_name=""):
    authorize(actor)
    from .membership_paid_visit_manual import receipt_facts
    from .membership_paid_visit_manual import review as original_review
    from .membership_paid_visit_records import MembershipPaidVisitIntent
    from .membership_paid_visit_recovery import cards

    intent = MembershipPaidVisitIntent.objects.select_related("purchase__customer").get(
        pk=intent_id
    )
    if plan(intent):
        raise ValidationError(
            "A partial payment is already recorded. Use its remaining-card controls; do not record that receipt again."
        )
    data = original_review(actor=actor, intent_id=intent_id)
    method = cards(intent).filter(pk=method_id).first()
    if method is None:
        raise ValidationError("Choose an available card belonging to this customer.")
    sale = intent.purchase.installments.first().invoice.sale
    data = {key: value for key, value in data.items() if key != "fingerprint"}
    data |= portions(
        principal=data["net"],
        original_fee=data["fee_removed"],
        manual=manual_amount,
        rate=sale.fee_rate,
    )
    data |= receipt_facts(tender=tender, received_on=received_on, sender_name=sender_name)
    data.update(
        method=str(method.pk),
        customer_revision=intent.purchase.customer.revision,
        member_total_after=str(amount(data["member_total_before"]) - amount(data["fee_removed"])),
    )
    data["manual_allocation"] = [
        dict(line=data["line"], net=data["manual_net"], fee="0.00", item_tax="0.00", fee_tax="0.00")
    ]
    data["card_allocation"] = [
        dict(
            line=data["line"],
            net=data["card_net"],
            fee=data["card_fee"],
            item_tax="0.00",
            fee_tax="0.00",
        )
    ]
    return data | dict(fingerprint=fingerprint(data))


@transaction.atomic
def record_received(
    *,
    actor,
    intent_id,
    manual_amount,
    tender,
    method_id,
    request_key,
    reviewed,
    received_on=None,
    sender_name="",
    verified_received=False,
    card_authorized=False,
):
    """Commit known receipt evidence before a separate card-preparation transaction."""
    authorize(actor)
    from .membership_paid_visit_manual import receipt_facts
    from .membership_paid_visit_pending import locked
    from .models import AuditEvent, FinancialLineAdjustment
    from .payments.ledger import record_manual, request_operation, writes_allowed
    from .payments.receipts import receipt_date

    writes_allowed()
    if verified_received is not True or card_authorized is not True:
        raise ValidationError(
            "Verify the received payment and the customer's authorization for the remaining card amount."
        )
    key = lock_request(request_key)
    receipt = receipt_facts(tender=tender, received_on=received_on, sender_name=sender_name)
    old = MembershipPaidVisitSplit.objects.filter(pk=key).first()
    if old:
        if (
            str(old.intent_id) != str(intent_id)
            or old.actor_id != actor.pk
            or old.facts["reviewed_hash"] != reviewed
            or old.facts["method"] != str(method_id)
            or amount(old.facts["manual_net"]) != amount(manual_amount)
            or any(
                old.facts[name] != value
                for name, value in receipt.items()
                if name != "received_on" or receipt["date_input"] is not None
            )
        ):
            raise ValidationError("This split-payment identity belongs to another reviewed action.")
        return old
    intent = locked(intent_id)
    sale = intent.purchase.installments.first().invoice.sale
    lock_sale(sale.pk)
    data = review(
        actor=actor,
        intent_id=intent.pk,
        manual_amount=manual_amount,
        tender=tender,
        method_id=method_id,
        received_on=received_on,
        sender_name=sender_name,
    )
    if data["fingerprint"] != reviewed:
        raise ValidationError(
            "The payment, card or original funds changed. Review the split again."
        )
    facts = data | dict(
        reviewed_hash=reviewed,
        verified_received=True,
        card_authorized=True,
        fee_key=str(uuid.uuid5(key, "unused-card-fee")),
        receipt_key=str(uuid.uuid5(key, "received-remainder-portion")),
    )
    saved = MembershipPaidVisitSplit.objects.create(
        id=key,
        intent=intent,
        previous_id=uuid.UUID(data["previous"]),
        operation_id=uuid.UUID(facts["receipt_key"]),
        actor=actor,
        facts=facts,
        fingerprint=fingerprint(facts),
    )
    if amount(data["fee_removed"]):
        FinancialLineAdjustment.objects.create(
            request_key=facts["fee_key"],
            line_id=data["line"],
            reason="tender_change",
            fee=-amount(data["fee_removed"]),
            actor=actor,
        )
    operation = request_operation(
        actor=actor,
        sale_id=sale.pk,
        request_key=saved.operation_id,
        tender=tender,
        allocation=data["manual_allocation"],
        purpose="member_purchase",
        received_on=receipt_date(received_on),
        paid_visit_split=saved,
    )
    record_manual(actor=actor, operation_id=operation.pk, received=True)
    AuditEvent.objects.create(
        actor=actor,
        action="membership.paid_visit_partial_received",
        record_type="membership",
        record_id=str(intent.purchase_id),
        changes=dict(
            split=str(saved.pk),
            operation=str(operation.pk),
            amount=data["manual_net"],
            card_remaining=data["card_total"],
        ),
    )
    return saved


def validate_receipt(split, *, allow_applied=False):
    from .payments.invoices import received, total

    facts, operation = split.facts, split.operation
    sale = split.intent.purchase.installments.first().invoice.sale
    if (
        fingerprint(facts) != split.fingerprint
        or operation.kind != "receipt"
        or operation.state != "succeeded"
        or operation.tender != facts["tender"]
        or operation.method_id is not None
        or operation.actor_id != split.actor_id
        or operation.sale_id != sale.pk
        or operation.amount != amount(facts["manual_net"])
        or operation.allocation != facts["manual_allocation"]
        or operation.manual_received_on.isoformat() != facts["received_on"]
        or (not allow_applied and sale.credit_applications.exists())
        or total(sale) != amount(facts["member_total_after"])
    ):
        raise ValidationError(
            "Review the recorded partial payment and original membership invoice before continuing."
        )
    changes = list(sale.lines.get().adjustments.all())
    if amount(facts["fee_removed"]):
        if len(changes) != 1:
            raise ValidationError(
                "Review other invoice corrections before requesting the card remainder."
            )
        change = changes[0]
        if (
            str(change.request_key) != facts["fee_key"]
            or change.reason != "tender_change"
            or change.actor_id != split.actor_id
            or change.net
            or change.item_tax
            or change.fee_tax
            or change.fee != -amount(facts["fee_removed"])
        ):
            raise ValidationError("Review the exact unused card-fee reduction.")
    elif changes:
        raise ValidationError(
            "Review other invoice corrections before requesting the card remainder."
        )
    return sale, received(sale)


def card_review(*, actor, split_id, method_id):
    authorize(actor)
    from .membership_paid_visit_new_card import require_known_storage
    from .membership_paid_visit_pending import fresh
    from .membership_paid_visit_recovery import cards

    split = MembershipPaidVisitSplit.objects.select_related(
        "intent__purchase__customer", "operation", "previous"
    ).get(pk=split_id)
    intent = split.intent
    fresh(intent)
    require_known_storage(intent)
    sale, held = validate_receipt(split)
    current = latest(split)
    previous = current.operation if current else split.previous
    if previous.state not in {"declined", "cancelled"}:
        raise ValidationError(
            "Check the existing card outcome before requesting the remainder again."
        )
    operations = list(sale.operations.order_by("pk"))
    attempts = {row.operation.pk for row in split.card_attempts.select_related("operation")}
    from .membership_paid_visit_records import MembershipPaidVisitRecovery

    earlier = {intent.operation_id} | set(
        MembershipPaidVisitRecovery.objects.filter(intent=intent).values_list(
            "operation__pk", flat=True
        )
    )
    if held != split.operation.amount or any(
        op.kind != "receipt"
        or (
            op.pk != split.operation.pk
            and (op.state not in {"declined", "cancelled"} or op.pk not in earlier | attempts)
        )
        for op in operations
    ):
        raise ValidationError(
            "Reconcile the existing partial payment and card outcomes before another request."
        )
    method = cards(intent).filter(pk=method_id).first()
    if method is None:
        raise ValidationError("Choose an available saved card belonging to this customer.")
    data = dict(
        split=str(split.pk),
        intent=str(intent.pk),
        split_fingerprint=split.fingerprint,
        actor=actor.pk,
        method=str(method.pk),
        previous=str(previous.pk),
        sequence=current.sequence + 1 if current else 1,
        amount=split.facts["card_total"],
        allocation=split.facts["card_allocation"],
        manual_operation=str(split.operation.pk),
        manual_amount=str(held),
        customer_revision=intent.purchase.customer.revision,
        billing_revision=intent.purchase.billing_state.revision,
        operations=[
            dict(id=str(op.pk), kind=op.kind, state=op.state, amount=str(op.amount))
            for op in operations
        ],
    )
    return data | dict(fingerprint=fingerprint(data))


@transaction.atomic
def request_card(*, actor, split_id, method_id, request_key, reviewed, confirmed=False):
    authorize(actor)
    from .membership_paid_visit_pending import locked
    from .models import AuditEvent
    from .payments.jobs import enqueue
    from .payments.ledger import request_operation, writes_allowed

    writes_allowed()
    if confirmed is not True:
        raise ValidationError("Confirm the customer authorizes this exact remaining card payment.")
    key = lock_request(request_key)
    old = MembershipPaidVisitSplitCard.objects.filter(pk=key).first()
    if old:
        if (
            str(old.split_id) != str(split_id)
            or old.actor_id != actor.pk
            or str(old.method_id) != str(method_id)
            or old.fingerprint != reviewed
        ):
            raise ValidationError("This card-request identity belongs to another reviewed action.")
        return old
    split = MembershipPaidVisitSplit.objects.get(pk=split_id)
    intent = locked(split.intent_id)
    lock_sale(intent.purchase.installments.first().invoice.sale_id)
    data = card_review(actor=actor, split_id=split.pk, method_id=method_id)
    if data["fingerprint"] != reviewed:
        raise ValidationError(
            "The card or recorded payment changed. Review the remaining amount again."
        )
    saved = MembershipPaidVisitSplitCard.objects.create(
        id=key,
        split=split,
        sequence=data["sequence"],
        previous_id=uuid.UUID(data["previous"]),
        operation_id=uuid.uuid5(key, "remaining-card-payment"),
        method_id=method_id,
        actor=actor,
        review=data,
        fingerprint=reviewed,
        expires_at=timezone.now() + timedelta(minutes=30),
    )
    operation = request_operation(
        actor=actor,
        sale_id=intent.purchase.installments.first().invoice.sale_id,
        request_key=saved.operation_id,
        tender="card",
        method_id=method_id,
        purpose="member_purchase",
        allocation=data["allocation"],
        paid_visit_split=saved,
    )
    from .membership_paid_visit_new_card import confirm_future_use

    confirm_future_use(intent=intent, method_id=method_id, actor=actor)
    enqueue(kind="payment_dispatch", reference=operation.pk, key=f"dispatch:{operation.pk}")
    AuditEvent.objects.create(
        actor=actor,
        action="membership.paid_visit_split_card_requested",
        record_type="membership",
        record_id=str(intent.purchase_id),
        changes=dict(
            split=str(split.pk),
            attempt=str(saved.pk),
            operation=str(operation.pk),
            amount=data["amount"],
        ),
    )
    return saved


def confirm_split(**values):
    """The received amount survives a later local card-preparation failure."""
    saved = record_received(**values)
    existing = saved.card_attempts.filter(sequence=1).first()
    if existing:
        return saved, existing, ""
    try:
        data = card_review(actor=values["actor"], split_id=saved.pk, method_id=values["method_id"])
        card = request_card(
            actor=values["actor"],
            split_id=saved.pk,
            method_id=values["method_id"],
            request_key=uuid.uuid5(saved.pk, "initial-card-attempt"),
            reviewed=data["fingerprint"],
            confirmed=values["card_authorized"],
        )
        return saved, card, ""
    except (ValidationError, PermissionDenied, DatabaseError) as failure:
        existing = saved.card_attempts.filter(sequence=1).first()
        if existing:
            return saved, existing, ""
        logger.error(
            "Received paid-visit portion retained; remaining card request needs review",
            exc_info=isinstance(failure, DatabaseError),
        )
        from .membership_paid_visit_pending import mark_review

        mark_review(saved.intent_id)
        return (
            saved,
            None,
            "The received payment was recorded. The remaining card payment still needs review. Do not record this receipt again.",
        )


def authorize_receipt(source, *, invoice, actor, request_key, tender, method_id, allocation):
    if not available() or not isinstance(
        source, (MembershipPaidVisitSplit, MembershipPaidVisitSplitCard)
    ):
        raise PermissionDenied
    if isinstance(source, MembershipPaidVisitSplit):
        saved = MembershipPaidVisitSplit.objects.select_related("intent", "previous").get(
            pk=source.pk
        )
        valid = (
            saved.fingerprint == fingerprint(saved.facts)
            and saved.operation_id == request_key
            and tender == saved.facts["tender"]
            and method_id is None
            and allocation == saved.facts["manual_allocation"]
            and saved.previous.state in {"declined", "cancelled"}
        )
        intent, expected_actor = saved.intent, saved.actor_id
    else:
        saved = MembershipPaidVisitSplitCard.objects.select_related(
            "split__intent", "previous"
        ).get(pk=source.pk)
        valid = (
            saved.operation_id == request_key
            and tender == "card"
            and str(method_id) == str(saved.method_id)
            and allocation == saved.review["allocation"]
            and saved.previous.state in {"declined", "cancelled"}
            and saved.fingerprint
            == fingerprint(
                {key: value for key, value in saved.review.items() if key != "fingerprint"}
            )
        )
        intent, expected_actor = saved.split.intent, saved.actor_id
    if (
        not valid
        or actor is None
        or actor.pk != expected_actor
        or invoice.installment.number != 1
        or invoice.installment.purchase_id != intent.purchase_id
    ):
        raise ValidationError("Use only this exact reviewed partial-payment authority.")
    from .membership_paid_visit_records import MembershipPaidVisitRelease

    if (
        MembershipPaidVisitRelease.objects.filter(intent=intent).exists()
        or intent.purchase.cancellations.exists()
    ):
        raise ValidationError("This visit application has ended or has a cancellation recorded.")


def require_funded(intent):
    split = plan(intent)
    if split is None:
        return False
    sale, held = validate_receipt(split, allow_applied=True)
    current = latest(split)
    if current is None or current.operation.state != "succeeded":
        raise ValidationError(
            "The partial payment is recorded. Confirm the remaining card outcome before applying the visit."
        )
    allowed = {split.operation.pk, current.operation.pk}
    from .membership_paid_visit_records import MembershipPaidVisitRecovery

    failed = {intent.operation_id} | set(
        MembershipPaidVisitRecovery.objects.filter(intent=intent).values_list(
            "operation__pk", flat=True
        )
    )
    failed |= {
        row.operation.pk
        for row in split.card_attempts.select_related("operation")
        if row.pk != current.pk
    }
    if (
        held != amount(split.facts["new_payment"])
        or current.operation.allocation != split.facts["card_allocation"]
        or current.operation.amount != amount(split.facts["card_total"])
        or any(
            op.kind != "receipt"
            or (
                op.pk not in allowed
                and (op.pk not in failed or op.state not in {"declined", "cancelled"})
            )
            for op in sale.operations.all()
        )
    ):
        raise ValidationError(
            "Review the exact received amounts and retained card fee before applying visit funds."
        )
    return True


def authorize_dispatch(intent, operation):
    split = plan(intent)
    if split is None:
        return None
    current = latest(split)
    if current is None or current.operation.pk != operation.pk:
        raise ValidationError("Only the latest explicitly authorized card remainder may continue.")
    authorize(current.actor)
    if timezone.now() >= current.expires_at:
        raise ValidationError(
            "This unattempted card request expired. Review the remaining amount again."
        )
    from .membership_paid_visit_new_card import require_known_storage
    from .membership_paid_visit_pending import fresh

    fresh(intent)
    require_known_storage(intent)
    validate_receipt(split)
    if current.previous.state not in {"declined", "cancelled"}:
        raise ValidationError("Review the previous card outcome before continuing.")
    return current


def cancellation_funding(intent):
    """Separate known receipts from a card amount that was never collected."""
    split = plan(intent)
    if split is None:
        return None
    paid = split.card_attempts.filter(operation__state="succeeded").exists()
    return dict(
        split_payment=str(split.pk),
        expected_received=str(
            amount(split.facts["manual_net"])
            + (amount(split.facts["card_total"]) if paid else ZERO)
        ),
        uncollected_card_net="0.00" if paid else split.facts["card_net"],
        uncollected_card_fee="0.00" if paid else split.facts["card_fee"],
    )
