"""New card storage for an explicit paid-visit remainder, never future billing."""

import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.utils import timezone

from .membership_paid_visit_records import MembershipPaidVisitCardStorage
from .payments.ledger import fingerprint

VERSION = "MD-PAID-VISIT-RECOVERY-CARD-2026-01"
UNCERTAIN = ("prepared", "customer_sending", "method_sending", "unknown")


def available():
    with connection.cursor() as cursor:
        return "core_membershippaidvisitcardstorage" in connection.introspection.table_names(cursor)


def records():
    return MembershipPaidVisitCardStorage.objects.select_related(
        "authorization__setup__method", "intent__purchase", "previous"
    )


def pending(intent, *, except_setup=None):
    if not available():
        return False
    rows = records().filter(intent=intent, authorization__setup__state__in=UNCERTAIN)
    if except_setup:
        rows = rows.exclude(authorization__setup_id=except_setup)
    return rows.exists()


def require_known_storage(intent, *, except_setup=None):
    if pending(intent, except_setup=except_setup):
        raise ValidationError(
            "Check the existing card setup before another payment or releasing the original visit funds. No new payment was requested."
        )


def scoped_methods(intent):
    from .models import PaymentMethod

    if not available():
        return PaymentMethod.objects.none()
    ids = (
        records()
        .filter(intent=intent, authorization__setup__state="succeeded")
        .values("authorization__setup__method_id")
    )
    return PaymentMethod.objects.filter(
        pk__in=ids,
        customer_id=intent.purchase.customer_id,
        state="active",
        environment="sandbox",
        provider_method__isnull=False,
    )


def method_outstanding(method):
    if not available():
        return False
    return (
        records()
        .filter(
            authorization__setup__method=method,
            intent__release__isnull=True,
        )
        .exists()
    )


def method_claimed(method):
    if not available():
        return False
    return (
        records()
        .filter(
            authorization__setup__method=method,
            intent__recoveries__method=method,
        )
        .exists()
    )


def method_ids():
    if not available():
        return []
    return (
        records()
        .filter(authorization__setup__state="succeeded")
        .values("authorization__setup__method_id")
    )


def retained_method_ids():
    """Only a confirmed recovery may expose its retained card to future visits."""
    from django.db.models import F

    if not available():
        return []
    return (
        records()
        .filter(
            authorization__setup__state="succeeded",
            intent__recoveries__method_id=F("authorization__setup__method_id"),
        )
        .values("authorization__setup__method_id")
    )


def confirm_future_use(*, intent, method_id, actor):
    from .membership_card_setup import replace_future_card

    method = scoped_methods(intent).filter(pk=method_id).first()
    if method:
        replace_future_card(method, actor)


def storage_text(retain):
    return (
        "The customer authorizes secure storage for the remaining first membership payment only. "
        "Saving the card does not charge it or change the card for future membership installments. "
        "An exact reviewed payment must be requested explicitly. "
        + (
            "The customer chooses to keep this card for future MonkeyDo visits, replacing the previous future-visit card only when this payment is explicitly requested."
            if retain
            else "The card is not kept for unrelated future MonkeyDo visits."
        )
    )


def storage_review(*, actor, intent_id):
    from .membership_paid_visit_recovery import source_review
    from .membership_sales import today

    if not available():
        raise ValidationError("Complete the reviewed recovery-card upgrade first.")
    intent, data = source_review(actor=actor, intent_id=intent_id, ignore_storage=True)
    data.update(
        operation="paid_visit_recovery",
        customer=intent.purchase.customer_id,
        customer_revision=intent.purchase.customer.revision,
        billing_revision=intent.purchase.billing_state.revision,
        on=today().isoformat(),
    )
    return intent, data | {"fingerprint": fingerprint(data)}


def validate_flow(flow, actor):
    intent, current = storage_review(actor=actor, intent_id=flow.get("recovery_intent"))
    if (
        flow.get("operation") != "paid_visit_recovery"
        or flow.get("prior_id") != intent.purchase_id
        or flow.get("customer_id") != current["customer"]
        or flow.get("customer_revision") != current["customer_revision"]
        or flow.get("offer_fingerprint") != current["fingerprint"]
        or flow.get("terms_text") != terms(current)
    ):
        raise ValidationError(
            "The payment or original visit changed. Review the card recovery again."
        )
    require_known_storage(intent, except_setup=flow.get("setup_key"))
    return intent, current


def terms(data):
    return (
        f"The customer authorizes saving a card for this booking's remaining ${data['amount']} "
        "first membership payment, including its accepted card fee. The card for future "
        "membership installments stays unchanged. Saving requests no payment."
    )


def bind_storage(*, flow, authorization, setup, actor):
    from .membership_paid_visit_pending import locked

    # The shared setup transaction owns the flow/nonce lock before source scope.
    intent = locked(flow["recovery_intent"])
    _, data = validate_flow(flow, actor)
    facts = data | {"storage_key": flow["key"], "setup_key": str(setup.pk)}
    saved, created = MembershipPaidVisitCardStorage.objects.get_or_create(
        authorization=authorization,
        defaults=dict(
            intent=intent, previous_id=data["previous"], facts=facts, fingerprint=fingerprint(facts)
        ),
    )
    if not created and (saved.facts != facts or saved.intent_id != intent.pk):
        raise ValidationError("This card setup belongs to another recovery review.")
    return saved


def saved_data(*, authority, actor):
    from .membership_card_setup import source
    from .membership_paid_visit_recovery import review

    saved = records().get(authorization=authority)
    method = source(authority)
    choice = ""
    problem = ""
    try:
        data = review(actor=actor, intent_id=saved.intent_id, method_id=method.pk)
        choice = f"{method.pk}:{data['fingerprint']}"
    except (ValidationError, PermissionDenied) as exc:
        problem = (
            " ".join(exc.messages)
            if isinstance(exc, ValidationError)
            else "Review the current membership payment."
        )
    return dict(
        state="saved",
        method_id=str(method.pk),
        brand=method.brand,
        last_four=method.last_four,
        recovery_choice=choice,
        authorization_expired=authority.expires_at <= timezone.now(),
        error=problem,
    )


def context(request, *, pending_paid_visit):
    """Preserve uncertain storage on reload without re-exchanging a nonce."""
    if not pending_paid_visit or pending_paid_visit["stopped"] or not available():
        return None
    from .membership_card_setup import make_flow
    from .membership_card_views import SESSION_KEY
    from .membership_sales import authorize
    from .permissions import require_actor

    actor = request.user
    try:
        authorize(actor, collect=True)
        require_actor(actor, "core.change_booking")
    except PermissionDenied:
        return None
    intent = pending_paid_visit["intent"]
    flows = request.session.get(SESSION_KEY, {})
    owned = [
        f
        for f in flows.values()
        if f.get("operation") == "paid_visit_recovery"
        and f.get("recovery_intent") == str(intent.pk)
        and f.get("staff_actor") == actor.pk
    ]
    flow = owned[-1] if owned else None
    setup = None
    if flow and flow.get("setup_key"):
        from .models import PaymentSetup

        setup = PaymentSetup.objects.filter(
            pk=flow["setup_key"], actor=actor, kind="membership"
        ).first()
    if pending(intent) and not setup:
        other = records().filter(intent=intent, authorization__setup__state__in=UNCERTAIN).first()
        return dict(
            flow=None,
            setup=other.authorization.setup,
            blocked=True,
            other_session=True,
            amount=pending_paid_visit["card_amount"],
        )
    try:
        _, data = storage_review(actor=actor, intent_id=intent.pk)
    except (ValidationError, PermissionDenied):
        if not setup or setup.state not in UNCERTAIN:
            return None
        data = None
    if setup and setup.state in UNCERTAIN:
        return dict(flow=flow, setup=setup, blocked=True, amount=pending_paid_visit["card_amount"])
    if not data:
        return None
    if (
        not flow
        or flow["offer_fingerprint"] != data["fingerprint"]
        or flow["expires"] <= timezone.now().timestamp()
    ):
        # A known stored source remains in the ordinary saved-card selector;
        # starting a fresh storage session cannot repeat its old exchange.
        offer = dict(
            operation="paid_visit_recovery",
            origin={"prior_id": intent.purchase_id},
            expected_method="card",
            fingerprint=data["fingerprint"],
            terms=terms(data),
        )
        flow = make_flow(
            actor=actor, customer=intent.purchase.customer, request_key=uuid.uuid4(), offer=offer
        )
        flow["recovery_intent"] = str(intent.pk)
        flows[flow["key"]] = flow
        request.session[SESSION_KEY] = flows
        setup = None
    return dict(flow=flow, setup=setup, blocked=False, amount=data["amount"])
