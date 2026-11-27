"""Membership-specific authority around the shared hosted-card exchange.

Membership storage never creates a booking PaymentConsent. Provider nonces and
raw card fields are never persisted here or accepted as local payment methods.
"""

import uuid
from datetime import datetime
from datetime import timezone as dt_timezone

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .membership_records import MembershipCardAuthorization, MembershipPurchase
from .membership_sales import authorize
from .models import AuditEvent, Customer, PaymentMethod
from .payments.gateway import Gateway, ProviderFailure, reference
from .payments.ledger import writes_allowed

LIFETIME = 20 * 60
CARD_VERSION = "MD-MEMBERSHIP-CARD-2026-01"


def storage_text(retain):
    return (
        "The customer authorizes secure card storage for the reviewed membership purchase and its accepted fixed-term payments. "
        "Saving this card does not charge it. Only confirmation of the membership purchase requests the selected initial payment. "
        + (
            "The customer also chooses to keep this card for future MonkeyDo visits, replacing any previously saved future-use card when this purchase is confirmed."
            if retain
            else "This authorization does not keep the card for unrelated future MonkeyDo visits."
        )
    )


def identity(flow):
    if (
        not flow
        or flow.get("purpose") != "membership"
        or timezone.now().timestamp() > flow.get("expires", 0)
    ):
        raise ValidationError("This membership card session expired. Review the purchase again.")
    try:
        key = uuid.UUID(flow["key"])
        customer = Customer.objects.get(pk=flow["customer_id"], revision=flow["customer_revision"])
    except (KeyError, ValueError, TypeError, Customer.DoesNotExist):
        raise ValidationError(
            "Customer details changed. Review the membership purchase again."
        ) from None
    digest = salted_hmac(
        "membership-card-flow", f"{key}:{customer.pk}:{customer.revision}:{flow.get('staff_actor')}"
    ).hexdigest()
    return digest, customer


def authorize_flow(flow, actor):
    if actor is None or not isinstance(flow, dict):
        raise ValidationError("Return to the authorized membership purchase form.")
    authorize(actor, collect=True)
    if actor.pk != flow.get("staff_actor"):
        raise ValidationError("Return to the authorized membership purchase form.")
    identity(flow)
    if not flow.get("offer_fingerprint") or not flow.get("terms_text"):
        raise ValidationError("Review the membership terms before saving a card.")


def make_flow(*, actor, customer, request_key, offer, expires=None):
    authorize(actor, collect=True)
    return dict(
        purpose="membership",
        key=str(request_key),
        staff_actor=actor.pk,
        customer_id=customer.pk,
        customer_revision=customer.revision,
        offer_fingerprint=offer["fingerprint"],
        terms_text=offer["terms"],
        prior_id=(offer.get("origin") or {}).get("prior_id"),
        expires=expires or timezone.now().timestamp() + LIFETIME,
    )


def prepared_authorization(flow, setup, actor):
    digest, customer = identity(flow)
    authorization, created = MembershipCardAuthorization.objects.get_or_create(
        setup=setup,
        defaults=dict(
            customer=customer,
            request_key=flow["key"],
            flow_hash=digest,
            offer_fingerprint=flow["offer_fingerprint"],
            terms_text=flow["terms_text"],
            storage_version=CARD_VERSION,
            storage_text=storage_text(setup.reusable),
            expires_at=datetime.fromtimestamp(flow["expires"], dt_timezone.utc),
            retain=setup.reusable,
            actor=actor,
        ),
    )
    if not created and (
        authorization.offer_fingerprint != flow["offer_fingerprint"]
        or authorization.actor_id != actor.pk
    ):
        raise ValidationError(
            "Review the saved card for the current membership terms before continuing."
        )
    return authorization


def available_methods(flow):
    digest, customer = identity(flow)
    authorizations = MembershipCardAuthorization.objects.filter(flow_hash=digest)
    scoped = Q(pk__in=authorizations.exclude(method=None).values("method_id")) | Q(
        pk__in=authorizations.filter(setup__state="succeeded").values("setup__method_id")
    )
    scoped |= Q(customer=customer, reusable=True)
    if flow.get("prior_id"):
        prior = MembershipPurchase.objects.filter(pk=flow["prior_id"], customer=customer).first()
        if prior and prior.billing_state.mandate:
            scoped |= Q(pk=prior.billing_state.mandate.method_id)
    return PaymentMethod.objects.filter(
        scoped,
        customer=customer,
        state="active",
        environment="sandbox",
        provider_method__isnull=False,
    )


def verify_saved_method(method):
    """Read the provider source and expiry without charging or retaining expiry."""
    data = Gateway().method(reference(method.provider_method))
    if (
        not isinstance(data, dict)
        or reference(data.get("id")) != method.provider_method
        or reference(data.get("customer_id")) != method.provider_customer
        or data.get("payment_method_type") != "card"
    ):
        raise ProviderFailure("invalid_saved_method_owner")
    if data.get("last4") != method.last_four or data.get("card_type") != method.brand:
        raise ValidationError(
            "The saved card details changed. Review this card before using it for the membership."
        )
    month, year = data.get("expiry_month"), data.get("expiry_year")
    now = timezone.localtime()
    if (
        type(month) is not int
        or type(year) is not int
        or not 1 <= month <= 12
        or not now.year <= year <= now.year + 30
        or (year, month) < (now.year, now.month)
    ):
        raise ValidationError(
            "This saved card needs updated expiration details before it can be used."
        )


@transaction.atomic
def choose_saved(*, actor, flow, method_id, accepted=False):
    authorize_flow(flow, actor)
    writes_allowed()
    if accepted is not True:
        raise ValidationError(
            "Review and accept the current membership terms before selecting a card."
        )
    # Caller-facing provider I/O happens before holding the local source lock.
    method = available_methods(flow).get(pk=method_id)
    verify_saved_method(method)
    method = available_methods(flow).select_for_update().get(pk=method_id)
    digest, customer = identity(flow)
    return MembershipCardAuthorization.objects.create(
        method=method,
        customer=customer,
        request_key=flow["key"],
        flow_hash=digest,
        offer_fingerprint=flow["offer_fingerprint"],
        terms_text=flow["terms_text"],
        storage_version=CARD_VERSION,
        storage_text=storage_text(method.reusable),
        expires_at=datetime.fromtimestamp(flow["expires"], dt_timezone.utc),
        retain=method.reusable,
        actor=actor,
    )


def source(authorization):
    if authorization.method_id:
        return authorization.method
    setup = authorization.setup
    if not setup or setup.kind != "membership" or setup.state != "succeeded" or not setup.method_id:
        raise ValidationError(
            "Check the existing card setup outcome before continuing. No membership payment has been requested."
        )
    return setup.method


def reviewed_source(*, actor, authorization_id, customer, request_key, reviewed):
    try:
        authority = MembershipCardAuthorization.objects.select_related(
            "method", "setup__method"
        ).get(
            pk=authorization_id,
            actor=actor,
            customer=customer,
            request_key=request_key,
            offer_fingerprint=reviewed,
            expires_at__gte=timezone.now(),
        )
    except (MembershipCardAuthorization.DoesNotExist, ValueError, TypeError):
        raise ValidationError(
            "Review the selected card for this membership purchase before confirming."
        ) from None
    method = source(authority)
    if (
        method.customer_id != customer.pk
        or method.state != "active"
        or method.environment != "sandbox"
        or not method.provider_method
    ):
        raise ValidationError("This card is no longer available for the membership purchase.")
    return method


def replace_future_card(method, actor):
    if not method.reusable:
        return
    from .payments.methods import queue_disposal

    for old in (
        PaymentMethod.objects.select_for_update()
        .filter(customer=method.customer, reusable=True, state="active")
        .exclude(pk=method.pk)
    ):
        old.reusable = False
        old.save(update_fields=["reusable"])
        AuditEvent.objects.create(
            actor=actor,
            action="payment.future_method_replaced",
            record_type="payment_method",
            record_id=str(old.pk),
            changes={"replacement_id": str(method.pk), "last_four": old.last_four},
        )
        queue_disposal(old)
