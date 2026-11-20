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

from core.models import AuditEvent
from core.permissions import require_actor
from core.public_booking import assert_flow, customer_from_flow

from .gateway import Gateway, ProviderFailure, reference
from .ledger import enabled, lock_request
from .models import (
    BookingCardAgreement,
    PaymentConsent,
    PaymentMethod,
    PaymentPolicyVersion,
    PaymentSetup,
)
from .policy import CANCELLATION, CANCELLATION_SCOPE, PAYMENT, POLICY_HASH, RETENTION, VERSION


def flow_identity(flow):
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
    digest, customer = flow_identity(flow)
    if customer is None:
        return PaymentMethod.objects.none()
    return PaymentMethod.objects.filter(
        customer=customer,
        reusable=True,
        state="active",
        environment="sandbox",
        booking__isnull=False,
    )


def consent(*, method, digest, retain, actor=None, accepted_at=None):
    policy, _ = PaymentPolicyVersion.objects.get_or_create(
        version=VERSION,
        defaults={
            "content_hash": POLICY_HASH,
            "text": {
                "payment": PAYMENT,
                "retention": RETENTION,
                "cancellation": CANCELLATION,
                "scope": CANCELLATION_SCOPE,
            },
        },
    )
    if policy.content_hash != POLICY_HASH:
        raise ValidationError("The policy text changed without a new version.")
    return PaymentConsent.objects.create(
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


@transaction.atomic
@sensitive_variables()
def prepare(*, flow, request_key, nonce, retain, payment_accepted, cancellation_accepted):
    enabled()
    digest, customer = flow_identity(flow)
    # Different request keys in this flow must not exchange a nonce concurrently.
    lock_request(uuid.UUID(digest[:32]))
    if (
        payment_accepted is not True
        or cancellation_accepted is not True
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
            "expires_at": datetime.fromtimestamp(flow["expires"], tz=dt_timezone.utc),
        },
    )
    if not created and (
        setup.flow_hash != digest or setup.nonce_hash != hashed or setup.reusable != retain
    ):
        raise ValidationError("This card setup request has already been used.")
    return setup


def persist_method(setup, data):
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
            consent_version=VERSION,
            consent_at=setup.created_at,
        )
        accepted = consent(
            method=method,
            digest=setup.flow_hash,
            retain=setup.reusable,
            accepted_at=setup.created_at,
        )
        setup.method = method
        setup.consent = accepted
        setup.state = "succeeded"
        setup.save(update_fields=["method", "consent", "state"])
        AuditEvent.objects.create(
            actor=None,
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
        return persist_method(setup, gateway.method(saved_id))
    except (ProviderFailure, ValidationError, TypeError, ValueError, AttributeError):
        with transaction.atomic():
            setup = PaymentSetup.objects.select_for_update().get(pk=setup.pk)
            if setup.state != "succeeded":
                setup.state = "unknown"
                setup.code = "card_setup_review"
                setup.save(update_fields=["state", "code"])
        return setup


@sensitive_variables()
def choose_saved(*, flow, method_id, payment_accepted, cancellation_accepted):
    enabled()
    digest, customer = flow_identity(flow)
    if customer is None or payment_accepted is not True or cancellation_accepted is not True:
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
        return consent(method=method, digest=digest, retain=True)


def selected_consent(flow):
    digest, customer = flow_identity(flow)
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
                actor=None,
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
