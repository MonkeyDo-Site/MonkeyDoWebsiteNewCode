"""Browser-flow-bound hosted-card exchange. No raw card fields or silent retries."""

import hashlib
import uuid
from datetime import datetime
from datetime import timezone as dt_timezone

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.views.decorators.debug import sensitive_variables

from core.models import AuditEvent, Booking
from core.permissions import require_actor
from core.public_booking import assert_flow, customer_from_flow

from .gateway import Gateway, ProviderFailure, reference
from .ledger import enabled, lock_request, writes_allowed
from .models import (
    BookingCardAgreement,
    PaymentConsent,
    PaymentMethod,
    PaymentPolicyVersion,
    PaymentSetup,
)
from .policy import (
    BACKUP_CANCELLATION,
    BACKUP_PAYMENT,
    CANCELLATION,
    CANCELLATION_PRICE_RULE,
    CANCELLATION_SCOPE,
    PAYMENT,
    POLICY_HASH,
    PRIMARY_PAYMENT,
    PUBLIC_PAYMENT_ACCEPTANCE,
    RETENTION,
    VERSION,
)


def flow_identity(flow):
    if flow and flow.get("purpose") == "membership":
        from core.membership_card_setup import identity

        return identity(flow)
    assert_flow(flow)
    if flow.get("workflow") != "integrated_v1":
        raise ValidationError("Use a new integrated booking for card setup.")
    customer = customer_from_flow(flow) if flow.get("proof") else None
    if customer:
        identity = f"{customer.pk}:{customer.revision}"
    else:
        contact = flow.get("contact", {})
        if not contact.get("last_name") or not contact.get("email"):
            raise ValidationError("Complete customer details before card setup.")
        identity = ":".join([flow.get("phone", ""), contact["last_name"], contact["email"]])
    return salted_hmac("payment-setup-flow", flow["key"] + ":" + identity).hexdigest(), customer


def reusable_methods(flow):
    from django.db.models import Q

    digest, customer = flow_identity(flow)
    current = PaymentSetup.objects.filter(flow_hash=digest, state="succeeded").values("method_id")
    scope = Q(pk__in=current)
    if customer:
        from core.membership_paid_visit_new_card import retained_method_ids
        from core.membership_records import MembershipCardMandate

        scope |= Q(customer=customer, reusable=True) & (
            Q(booking__isnull=False)
            | Q(pk__in=MembershipCardMandate.objects.values("method_id"))
            | Q(pk__in=retained_method_ids())
        )
    return PaymentMethod.objects.filter(scope, state="active", environment="sandbox")


def authorize_actor(flow, actor):
    if flow.get("purpose") == "membership":
        from core.membership_card_setup import authorize_flow

        authorize_flow(flow, actor)
        return
    if not flow.get("staff_actor") and actor is None:
        return
    if actor is None or flow.get("staff_actor") != actor.pk:
        raise ValidationError("Return to the authorized staff booking form.")
    for permission in ("core.view_booking", "core.change_booking", "core.view_customer"):
        require_actor(actor, permission)
    _, customer = flow_identity(flow)
    if customer is None:
        raise ValidationError("Choose the staff booking’s customer before card setup.")
    if flow.get("staff_action") == "create" and not flow.get("staff_booking"):
        require_actor(actor, "core.add_booking")
        if not flow.get("quote") or flow.get("customer_id") != customer.pk:
            raise ValidationError(
                "Review the customer, session and current price before card setup."
            )
        return
    try:
        booking = Booking.objects.get(
            pk=flow.get("staff_booking"), customer=customer, workflow="integrated_v1"
        )
    except Booking.DoesNotExist:
        raise ValidationError("The booking changed. Reload its card setup form.") from None
    if booking.edit_version != flow.get("staff_booking_version") or (
        booking.attendance and flow.get("staff_action") != "replace"
    ):
        raise ValidationError("The booking changed. Reload its card setup form.")
    if flow.get("staff_action") == "replace":
        from .models import PaymentOperation

        if PaymentOperation.objects.filter(
            sale__booking=booking, state__in=["ready", "sending", "unknown", "action"]
        ).exists():
            raise ValidationError("Resolve the pending payment before replacing its source.")


def consent(*, method, digest, retain, actor=None, accepted_at=None, flow=None, terms=None):
    policy, _ = PaymentPolicyVersion.objects.get_or_create(
        version=VERSION,
        defaults={
            "content_hash": POLICY_HASH,
            "text": {
                "payment": PAYMENT,
                "retention": RETENTION,
                "cancellation": CANCELLATION,
                "scope": CANCELLATION_SCOPE,
                "cancellation_price_rule": CANCELLATION_PRICE_RULE,
                "primary_card_payment": PRIMARY_PAYMENT,
                "backup_card_payment": BACKUP_PAYMENT,
                "public_payment_acceptance": PUBLIC_PAYMENT_ACCEPTANCE,
                "backup_cancellation": BACKUP_CANCELLATION,
            },
        },
    )
    if policy.content_hash != POLICY_HASH:
        raise ValidationError("The policy text changed without a new version.")
    accepted = PaymentConsent.objects.create(
        policy=policy,
        method=method,
        flow_hash=digest,
        version=VERSION,
        policy_hash=POLICY_HASH,
        payment_accepted=True,
        cancellation_accepted=True,
        future_use_accepted=retain,
        source="staff" if actor else "public",
        accepted_at=accepted_at or timezone.now(),
        actor=actor,
    )
    from .policy import displayed_cancellation

    wording, pricing_id = (
        (terms["cancellation"], terms["pricing_policy"]) if terms else displayed_cancellation(flow)
    )
    AuditEvent.objects.create(
        actor=actor,
        action="payment.displayed_terms_accepted",
        record_type="payment_consent",
        record_id=str(accepted.pk),
        changes={
            "cancellation": wording,
            "retention": RETENTION,
            "pricing_policy": pricing_id,
            "policy_version": VERSION,
        },
    )
    return accepted


@transaction.atomic
@sensitive_variables()
def prepare(
    *, flow, request_key, nonce, retain, payment_accepted, cancellation_accepted, actor=None
):
    enabled()
    writes_allowed()
    authorize_actor(flow, actor)
    digest, customer = flow_identity(flow)
    # Different request keys in this flow must not exchange a nonce concurrently.
    lock_request(uuid.UUID(digest[:32]))
    membership = flow.get("purpose") == "membership"
    if (
        payment_accepted is not True
        or (cancellation_accepted is not False if membership else cancellation_accepted is not True)
        or type(retain) is not bool
    ):
        raise ValidationError("Accept the payment and cancellation policies before saving a card.")
    try:
        key = uuid.UUID(str(request_key))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Use the current card setup form.") from None
    if not isinstance(nonce, str) or not 1 <= len(nonce) <= 26:
        raise ValidationError("Use the secure provider card-entry form.")
    if (
        PaymentSetup.objects.filter(
            flow_hash=digest,
            state__in=["prepared", "customer_sending", "method_sending", "unknown"],
        )
        .exclude(pk=key)
        .exists()
    ):
        raise ValidationError("An earlier card setup needs review before another exchange.")
    hashed = hashlib.sha256(nonce.encode()).hexdigest()
    setup, created = PaymentSetup.objects.get_or_create(
        id=key,
        defaults={
            "flow_hash": digest,
            "nonce_hash": hashed,
            "customer": customer,
            "customer_revision": customer.revision if customer else None,
            "reusable": retain,
            "actor": actor,
            "kind": "membership" if membership else "booking",
            "expires_at": datetime.fromtimestamp(flow["expires"], tz=dt_timezone.utc),
        },
    )
    if not created and (
        setup.flow_hash != digest
        or setup.nonce_hash != hashed
        or setup.reusable != retain
        or setup.kind != ("membership" if membership else "booking")
    ):
        raise ValidationError("This card setup request has already been used.")
    if membership:
        from core.membership_card_setup import prepared_authorization

        prepared_authorization(flow, setup, actor)
        return setup
    from .policy import displayed_cancellation

    wording, pricing_id = displayed_cancellation(flow)
    AuditEvent.objects.get_or_create(
        action="payment.setup_terms_reviewed",
        record_type="payment_setup",
        record_id=str(setup.pk),
        defaults={
            "actor": actor,
            "changes": {
                "cancellation": wording,
                "pricing_policy": pricing_id,
                "policy_version": VERSION,
            },
        },
    )
    return setup


def persist_method(setup, data, flow=None):
    if not isinstance(data, dict) or data.get("payment_method_type") != "card":
        raise ProviderFailure("invalid_saved_method")
    method_id = reference(data.get("id"))
    if reference(data.get("customer_id")) != setup.provider_customer:
        raise ProviderFailure("invalid_saved_method_owner")
    brand = data.get("card_type")
    last_four = data.get("last4")
    if (
        brand not in {"Visa", "MasterCard", "Amex", "Discover", "JCB", "Diners"}
        or not isinstance(last_four, str)
        or len(last_four) != 4
        or not last_four.isascii()
        or not last_four.isdigit()
    ):
        raise ProviderFailure("invalid_saved_method_metadata")
    # Expiry is used for current eligibility only, never retained locally.
    month, year = data.get("expiry_month"), data.get("expiry_year")
    now = timezone.localtime()
    if (
        type(month) is not int
        or type(year) is not int
        or not 1 <= month <= 12
        or (year, month) < (now.year, now.month)
    ):
        raise ProviderFailure("expired_saved_method")
    with transaction.atomic():
        setup = PaymentSetup.objects.select_for_update().get(pk=setup.pk)
        if setup.state == "succeeded":
            return setup
        method = PaymentMethod.objects.create(
            customer=setup.customer,
            provider_customer=setup.provider_customer,
            provider_method=method_id,
            brand=brand,
            last_four=last_four,
            reusable=setup.reusable,
            consent_version="MD-MEMBERSHIP-CARD-2026-01" if setup.kind == "membership" else VERSION,
            consent_at=setup.created_at,
        )
        reviewed_terms = AuditEvent.objects.filter(
            action="payment.setup_terms_reviewed",
            record_type="payment_setup",
            record_id=str(setup.pk),
        ).first()
        accepted = (
            consent(
                terms=reviewed_terms.changes if reviewed_terms else None,
                method=method,
                digest=setup.flow_hash,
                retain=setup.reusable,
                accepted_at=setup.created_at,
                flow=flow,
                actor=setup.actor,
            )
            if setup.kind == "booking"
            else None
        )
        setup.method = method
        setup.consent = accepted
        setup.state = "succeeded"
        setup.save(update_fields=["method", "consent", "state"])
        AuditEvent.objects.create(
            actor=setup.actor,
            action="payment.card_setup_completed",
            record_type="payment_method",
            record_id=str(method.pk),
            changes={
                "brand": brand,
                "last_four": last_four,
                "reusable": setup.reusable,
                "policy_version": VERSION,
            },
        )
        return setup


@sensitive_variables()
def exchange(
    *,
    flow,
    request_key,
    nonce,
    expiry_month,
    expiry_year,
    retain,
    payment_accepted,
    cancellation_accepted,
    actor=None,
):
    enabled()
    from .gateway import validate_nonce

    validate_nonce(nonce, expiry_month, expiry_year)
    gateway = Gateway()
    setup = prepare(
        flow=flow,
        request_key=request_key,
        nonce=nonce,
        retain=retain,
        payment_accepted=payment_accepted,
        cancellation_accepted=cancellation_accepted,
        actor=actor,
    )
    with transaction.atomic():
        claimed = PaymentSetup.objects.select_for_update().get(pk=setup.pk)
        if claimed.state != "prepared":
            return claimed
        claimed.state = "customer_sending"
        claimed.save(update_fields=["state"])
    try:
        result = gateway.create_customer(setup.pk)
        provider_customer = reference(result.get("id"))
        with transaction.atomic():
            setup = PaymentSetup.objects.select_for_update().get(pk=setup.pk)
            setup.provider_customer = provider_customer
            setup.state = "method_sending"
            setup.save(update_fields=["provider_customer", "state"])
        saved = gateway.save_card(provider_customer, nonce, expiry_month, expiry_year)
        saved_id = reference(saved.get("id"))
        return persist_method(setup, gateway.method(saved_id), flow=flow)
    except (ProviderFailure, ValidationError, TypeError, ValueError, AttributeError):
        with transaction.atomic():
            setup = PaymentSetup.objects.select_for_update().get(pk=setup.pk)
            if setup.state != "succeeded":
                setup.state = "unknown"
                setup.code = "card_setup_review"
                setup.save(update_fields=["state", "code"])
        return setup


@sensitive_variables()
def choose_saved(*, flow, method_id, payment_accepted, cancellation_accepted, actor=None):
    enabled()
    writes_allowed()
    if flow.get("purpose") == "membership":
        raise ValidationError("Use the membership card authorization before selecting this source.")
    authorize_actor(flow, actor)
    digest, customer = flow_identity(flow)
    if payment_accepted is not True or cancellation_accepted is not True:
        raise ValidationError("Verify customer details and accept both payment policies.")
    method = reusable_methods(flow).get(pk=method_id)
    try:
        data = Gateway().method(reference(method.provider_method))
        if (
            reference(data.get("id")) != method.provider_method
            or reference(data.get("customer_id")) != method.provider_customer
            or data.get("payment_method_type") != "card"
        ):
            raise ProviderFailure("invalid_saved_method_owner")
        month, year = data.get("expiry_month"), data.get("expiry_year")
        now = timezone.localtime()
        if (
            type(month) is not int
            or type(year) is not int
            or not 1 <= month <= 12
            or not 1900 <= year <= now.year + 30
        ):
            raise ProviderFailure("invalid_saved_method_metadata")
        # Only a well-formed past expiry is described to the customer as expired.
        if (year, month) < (now.year, now.month):
            raise ValidationError(
                "Your saved card has expired and needs to be updated before this booking can be completed.",
                code="expired_saved_method",
            )
        brand, last_four = data.get("card_type"), data.get("last4")
        if (
            brand not in {"Visa", "MasterCard", "Amex", "Discover", "JCB", "Diners"}
            or not isinstance(last_four, str)
            or len(last_four) != 4
            or not last_four.isascii()
            or not last_four.isdigit()
        ):
            raise ProviderFailure("invalid_saved_method_metadata")
    except (ProviderFailure, TypeError, AttributeError):
        raise ValidationError(
            "Your saved payment method could not be used. Please enter a payment method for this booking.",
            code="unusable_saved_method",
        ) from None
    with transaction.atomic():
        # Check scope/state again after provider I/O, without holding DB locks over it.
        method = reusable_methods(flow).select_for_update().get(pk=method_id)
        method.brand, method.last_four = brand, last_four
        method.save(update_fields=["brand", "last_four"])
        return consent(method=method, digest=digest, retain=method.reusable, actor=actor, flow=flow)


def selected_consent(flow):
    digest, customer = flow_identity(flow)
    if flow.get("payment_method_changed"):
        raise ValidationError("Review and save your card for the selected payment method.")
    try:
        accepted = PaymentConsent.objects.select_related("method").get(
            pk=flow["payment_consent"],
            flow_hash=digest,
            version=VERSION,
            policy_id=VERSION,
            policy_hash=POLICY_HASH,
            payment_accepted=True,
            cancellation_accepted=True,
        )
    except (KeyError, ValueError, PaymentConsent.DoesNotExist):
        raise ValidationError("Complete secure card setup and policy consent.") from None
    method = accepted.method
    if method.state != "active" or method.customer_id != (customer.pk if customer else None):
        raise ValidationError("The saved payment method is no longer available for this customer.")
    if not method.reusable and method.agreements.filter(resolved_at__isnull=True).exists():
        raise ValidationError("This card is reserved for another booking.")
    return accepted


@transaction.atomic
def bind_booking(*, flow, booking):
    """Called inside final booking transaction, never before customer creation."""
    digest, identified = flow_identity(flow)
    if identified is not None:
        if identified.pk != booking.customer_id:
            raise ValidationError("This booking belongs to another customer.")
    else:
        contact = flow["contact"]
        if (
            booking.customer.phone != flow["phone"]
            or booking.customer.email.casefold() != contact["email"].strip().casefold()
            or booking.customer.last_name != contact["last_name"].strip()
        ):
            raise ValidationError("The new customer does not match this booking.")
    previous = (
        BookingCardAgreement.objects.filter(booking=booking).select_related("consent").first()
    )
    if previous:
        if (
            str(previous.consent_id) != str(flow.get("payment_consent"))
            or previous.consent.flow_hash != digest
        ):
            raise ValidationError("This booking has a different card agreement.")
        return previous
    accepted = selected_consent(flow)
    method = PaymentMethod.objects.select_for_update().get(pk=accepted.method_id)
    if method.state != "active":
        raise ValidationError("This card is being removed or requires review.")
    if method.customer_id not in (None, booking.customer_id):
        raise ValidationError("The card belongs to another customer.")
    if method.reusable:
        previous = (
            PaymentMethod.objects.select_for_update()
            .filter(customer=booking.customer, reusable=True, state="active")
            .exclude(pk=method.pk)
        )
        for older in previous:
            older.reusable = False
            older.save(update_fields=["reusable"])
            AuditEvent.objects.create(
                actor=accepted.actor,
                action="payment.future_method_replaced",
                record_type="payment_method",
                record_id=str(older.pk),
                changes={"replacement_id": str(method.pk), "last_four": older.last_four},
            )
            from .methods import queue_disposal

            queue_disposal(older)
    method.customer = booking.customer
    if method.booking_id is None:
        method.booking = booking
    method.save(update_fields=["customer", "booking"])
    agreement, created = BookingCardAgreement.objects.get_or_create(
        booking=booking, defaults={"method": method, "consent": accepted}
    )
    if not created and (agreement.method_id != method.pk or agreement.consent_id != accepted.pk):
        raise ValidationError("This booking already has another card agreement.")
    return agreement


def reconcile_setup(*, actor, setup_id):
    enabled()
    require_actor(actor, "core.review_payment", owner=True)
    setup = PaymentSetup.objects.get(pk=setup_id)
    if setup.state == "succeeded":
        return setup
    if setup.state not in {"unknown", "customer_sending", "method_sending"}:
        raise ValidationError("This card setup does not need reconciliation.")
    gateway = Gateway()
    if not setup.provider_customer:
        customer = gateway.setup_customer(setup.pk)
        provider_id = reference(customer.get("id"))
        with transaction.atomic():
            setup = PaymentSetup.objects.select_for_update().get(pk=setup.pk)
            if setup.provider_customer and setup.provider_customer != provider_id:
                raise ValidationError("This setup has a different provider customer.")
            setup.provider_customer = provider_id
            setup.save(update_fields=["provider_customer"])
    methods = gateway.methods(setup.provider_customer)
    if not isinstance(methods, list) or len(methods) != 1:
        raise ValidationError("Provider review is needed to identify the saved card.")
    return persist_method(setup, gateway.method(reference(methods[0].get("id"))))


@transaction.atomic
def replace_booking_card(*, actor, flow, booking_id):
    """Only explicit reviewed replacement changes the current booking agreement."""
    from .methods import queue_disposal
    from .models import PaymentOperation

    enabled()
    writes_allowed()
    authorize_actor(flow, actor)
    booking = Booking.objects.select_for_update().get(pk=booking_id, workflow="integrated_v1")
    if flow.get("staff_booking") != booking.pk or flow.get("staff_action") != "replace":
        raise ValidationError("Review this booking’s replacement card form.")
    if PaymentOperation.objects.filter(
        sale__booking=booking, state__in=["ready", "sending", "unknown", "action"]
    ).exists():
        raise ValidationError("Reconcile the pending payment before changing its card.")
    accepted = selected_consent(flow)
    agreement = BookingCardAgreement.objects.select_for_update().get(booking=booking)
    if agreement.consent_id == accepted.pk:
        return agreement
    if booking.attendance:
        from .checkout import summary

        if not summary(booking).get("can_collect"):
            raise ValidationError(
                "There is no unresolved reviewed balance requiring a replacement card."
            )
    method = PaymentMethod.objects.select_for_update().get(pk=accepted.method_id)
    if method.state != "active" or method.customer_id != booking.customer_id:
        raise ValidationError("The replacement card is not available for this customer.")
    old = agreement.method
    if method.reusable:
        older = (
            PaymentMethod.objects.select_for_update()
            .filter(customer=booking.customer, reusable=True, state="active")
            .exclude(pk=method.pk)
        )
        for previous in older:
            previous.reusable = False
            previous.save(update_fields=["reusable"])
            queue_disposal(previous)
    if method.booking_id is None:
        method.booking = booking
        method.save(update_fields=["booking"])
    agreement.method = method
    agreement.consent = accepted
    agreement.resolved_at = None
    agreement.save(update_fields=["method", "consent", "resolved_at"])
    queue_disposal(old)
    AuditEvent.objects.create(
        actor=actor,
        action="payment.booking_card_replaced",
        record_type="booking",
        record_id=str(booking.reference),
        changes={
            "last_four": {"before": old.last_four, "after": method.last_four},
            "future_use": method.reusable,
        },
    )
    return agreement
