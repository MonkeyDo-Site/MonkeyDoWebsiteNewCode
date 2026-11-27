"""Narrow verified-customer authority for one private membership renewal.

Browser proofs expire after twenty minutes. Once the explicit first payment is
accepted, immutable evidence authorizes its worker dispatch without an active
browser session. Neither authority permits refunds, retries or another sale.
"""

import hashlib
import uuid
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

from django.conf import settings
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .forms import normalize_phone
from .membership_records import (
    MembershipPublicAcceptance,
    MembershipRenewalLink,
    MembershipRenewalLinkRevocation,
)
from .models import AuditEvent
from .payments.amounts import amount
from .public_booking import canonical_name

LINK_SALT = "membership-private-renewal-link"
PROOF_SALT = "membership-private-renewal-verification"
LIFETIME = 20 * 60


def token_for(link):
    return signing.Signer(salt=LINK_SALT).sign(str(link.pk))


def resolve_link(token):
    try:
        pk = uuid.UUID(signing.Signer(salt=LINK_SALT).unsign(token))
        return MembershipRenewalLink.objects.select_related("customer", "prior__membership").get(
            pk=pk, expires_at__gt=timezone.now(), revocation__isnull=True
        )
    except (
        signing.BadSignature,
        MembershipRenewalLink.DoesNotExist,
        ValueError,
        TypeError,
        AttributeError,
    ):
        raise ValidationError(
            "This renewal link is unavailable. Please call/text 848-238-5147 for assistance."
        ) from None


@transaction.atomic
def create_link(*, actor, prior, request_key):
    from .membership_renewals import renewal_details
    from .membership_sales import authorize
    from .payments.ledger import lock_request

    authorize(actor)
    from .membership_records import MembershipPurchase

    prior = MembershipPurchase.objects.select_related("membership", "billing_state").get(
        pk=prior.pk
    )
    key = lock_request(request_key)
    existing = MembershipRenewalLink.objects.filter(pk=key).first()
    if existing:
        if existing.actor_id != actor.pk or existing.prior_id != prior.pk:
            raise ValidationError("This renewal-link request identifies another membership.")
        return existing, token_for(existing)
    if renewal_details(prior)["available_places"] <= 0:
        raise ValidationError("These membership places already have a renewal recorded.")
    link = MembershipRenewalLink.objects.create(
        id=key,
        prior=prior,
        customer_id=prior.customer_id,
        expires_at=timezone.now() + timedelta(days=30),
        actor=actor,
    )
    AuditEvent.objects.create(
        actor=actor,
        action="membership.renewal_link_created",
        record_type="membership",
        record_id=str(prior.pk),
        changes={"link_id": str(link.pk)},
    )
    return link, token_for(link)


@transaction.atomic
def revoke_link(*, actor, link_id):
    from .membership_sales import authorize

    authorize(actor)
    link = MembershipRenewalLink.objects.get(pk=link_id)
    result, _ = MembershipRenewalLinkRevocation.objects.get_or_create(
        link=link, defaults={"actor": actor}
    )
    return result


def verify_identity(*, token, phone, last_name, request_key=None):
    link = resolve_link(token)
    customer = link.customer
    if (
        not isinstance(last_name, str)
        or normalize_phone(phone) not in {customer.phone, customer.previous_phone}
        or canonical_name(last_name) != canonical_name(customer.last_name)
    ):
        raise ValidationError(
            "Those details could not be verified. Check your phone number and last name, or call/text 848-238-5147."
        )
    key = uuid.UUID(str(request_key)) if request_key else uuid.uuid4()
    now = timezone.now().timestamp()
    proof = signing.dumps(
        dict(
            link=str(link.pk),
            prior=link.prior_id,
            customer=customer.pk,
            revision=customer.revision,
            phone=customer.phone,
            key=str(key),
            verified_at=now,
            expires=now + LIFETIME,
        ),
        salt=PROOF_SALT,
    )
    AuditEvent.objects.create(
        actor=None,
        action="membership.public_identity_verified",
        record_type="membership",
        record_id=str(link.prior_id),
        changes={"link_id": str(link.pk), "customer_revision": customer.revision},
    )
    return proof


def verified_scope(proof):
    if not settings.MEMBERSHIP_SALES_ENABLED:
        raise PermissionDenied
    try:
        data = signing.loads(proof, salt=PROOF_SALT, max_age=LIFETIME)
        now = timezone.now().timestamp()
        if data["expires"] < now or data["verified_at"] > now + 60:
            raise ValueError
        link = MembershipRenewalLink.objects.select_related("customer", "prior__membership").get(
            pk=data["link"],
            expires_at__gt=timezone.now(),
            revocation__isnull=True,
            prior_id=data["prior"],
            customer_id=data["customer"],
        )
        if link.customer.revision != data["revision"] or link.customer.phone != data["phone"]:
            raise ValueError
        key = uuid.UUID(data["key"])
    except (
        signing.BadSignature,
        MembershipRenewalLink.DoesNotExist,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
    ):
        raise PermissionDenied from None
    return data | {"request_key": key, "link_record": link, "customer_record": link.customer}


def check_selection(proof, *, customer_id, operation, prior_id, tender):
    scope = verified_scope(proof)
    if (
        scope["customer"] != customer_id
        or operation != "renewal"
        or prior_id != scope["prior"]
        or tender != "card"
    ):
        raise PermissionDenied
    return scope


def check_purchase(proof, purchase, *, require_acceptance=True):
    scope = verified_scope(proof)
    if (
        purchase.source != "public"
        or purchase.actor_id is not None
        or purchase.customer_id != scope["customer"]
        or purchase.request_key != scope["request_key"]
        or purchase.purpose != "renewal"
        or purchase.origin.prior_id != scope["prior"]
    ):
        raise PermissionDenied
    if require_acceptance:
        try:
            if purchase.public_acceptance.link_id != scope["link_record"].pk:
                raise PermissionDenied
        except MembershipPublicAcceptance.DoesNotExist:
            raise PermissionDenied from None
    return scope


def record_acceptance(*, proof, purchase, card_authorization_id):
    scope = check_purchase(proof, purchase, require_acceptance=False)
    return MembershipPublicAcceptance.objects.create(
        purchase=purchase,
        link=scope["link_record"],
        card_authorization_id=card_authorization_id,
        proof_hash=hashlib.sha256(proof.encode()).hexdigest(),
        customer_revision=scope["revision"],
        verified_at=datetime.fromtimestamp(scope["verified_at"], dt_timezone.utc),
    )


def authorize_dispatch(operation):
    """Validate durable accepted scope; link expiry/revocation affects later access."""
    from .membership_card_setup import source
    from .membership_records import MembershipInvoice
    from .payments.ledger import full_allocation

    if (
        operation.actor_id is not None
        or operation.kind != "receipt"
        or operation.tender != "card"
        or operation.purpose != "member_purchase"
    ):
        raise PermissionDenied
    try:
        invoice = operation.sale.membership_invoice
        member = invoice.installment.purchase
        acceptance = member.public_acceptance
    except (MembershipInvoice.DoesNotExist, MembershipPublicAcceptance.DoesNotExist):
        raise PermissionDenied from None
    auth = acceptance.card_authorization
    if (
        invoice.installment.number != 1
        or member.source != "public"
        or member.actor_id is not None
        or member.purpose != "renewal"
        or acceptance.link.customer_id != member.customer_id
        or acceptance.link.prior_id != member.origin.prior_id
        or auth.actor_id is not None
        or auth.customer_id != member.customer_id
        or auth.request_key != member.request_key
        or auth.offer_fingerprint != member.fingerprint
        or source(auth).pk != operation.method_id
        or operation.amount != amount(invoice.installment.quote["total"])
        or operation.allocation != full_allocation(operation.sale)
    ):
        raise PermissionDenied
    stopped = member.billing_state.stopped_on
    if stopped and stopped <= member.membership.starts_on:
        raise ValidationError(
            "This cancelled membership requires review before its initial payment."
        )


@transaction.atomic
def submit(*, proof, reviewed, accepted, card_authorization_id, method_id, **values):
    from .membership_card_setup import reviewed_source
    from .membership_reservations import lock_customer
    from .membership_sales import purchase
    from .payments.ledger import lock_request

    if set(values) - {"kind", "places", "months", "billing", "starts_on"}:
        raise PermissionDenied
    scope = verified_scope(proof)
    lock_request(uuid.uuid5(scope["link_record"].pk, "public-renewal-checkout"))
    lock_customer(scope["customer"])
    existing = (
        MembershipPublicAcceptance.objects.select_related("purchase")
        .filter(link=scope["link_record"])
        .first()
    )
    if existing:
        return existing.purchase
    card = reviewed_source(
        actor=None,
        authorization_id=card_authorization_id,
        customer=scope["customer_record"],
        request_key=scope["request_key"],
        reviewed=reviewed,
    )
    if str(card.pk) != str(method_id):
        raise PermissionDenied
    member = purchase(
        actor=None,
        authority=proof,
        request_key=scope["request_key"],
        reviewed=reviewed,
        accepted=accepted,
        method_id=method_id,
        card_authorization_id=card_authorization_id,
        customer=scope["customer_record"],
        operation="renewal",
        prior_id=scope["prior"],
        expected_method="card",
        **values,
    )
    return member
