"""Fresh, browser-owned receipt access never grants purchase/payment authority."""

import hashlib

from django.conf import settings
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from .membership_public_authority import LIFETIME, PROOF_SALT
from .membership_records import MembershipPublicAcceptance
from .models import AuditEvent
from .public_booking import customer_from_flow

SESSION_KEY = "initial_membership_receipt_access"
READ_SALT = "membership-public-receipt-read"


def owned_receipt(request):
    """Authenticate the old browser's accepted source, without renewing it."""
    from .public_membership_views import INITIAL_SESSION_KEY
    from .public_membership_views import SESSION_KEY as PURCHASE_KEY

    if not settings.MEMBERSHIP_SALES_ENABLED:
        raise PermissionDenied
    try:
        checkout_id = request.session[INITIAL_SESSION_KEY]["checkout_id"]
        proof = request.session[PURCHASE_KEY][checkout_id]["proof"]
        # Signature only: expiry still applies to EVERY financial entry point.
        data = signing.loads(proof, salt=PROOF_SALT)
        receipt = MembershipPublicAcceptance.objects.select_related(
            "checkout__customer", "purchase__membership", "purchase__customer"
        ).get(checkout_id=checkout_id, link__isnull=True)
        source = receipt.checkout
        if (
            data.get("purpose") != "purchase"
            or data["checkout"] != checkout_id
            or data["key"] != checkout_id
            or data["customer"] != source.customer_id
            or data["revision"] != source.customer_revision
            or data["verified_at"] != source.verified_at.timestamp()
            or data["expires"] != source.expires_at.timestamp()
            or hashlib.sha256(proof.encode()).hexdigest() != receipt.proof_hash
        ):
            raise ValueError
        return receipt
    except (
        signing.BadSignature,
        MembershipPublicAcceptance.DoesNotExist,
        KeyError,
        TypeError,
        ValueError,
        AttributeError,
        ValidationError,
    ):
        raise PermissionDenied from None


def grant(request, record):
    receipt = owned_receipt(request)
    customer = customer_from_flow(record["flow"])
    if (
        str(receipt.checkout_id) != record["checkout"]
        or customer.pk != receipt.purchase.customer_id
    ):
        raise PermissionDenied
    now = timezone.now().timestamp()
    record["proof"] = signing.dumps(
        dict(
            checkout=record["checkout"],
            customer=customer.pk,
            revision=customer.revision,
            phone=customer.phone,
            browser=record["browser"],
            identity_key=record["flow"]["key"],
            verified_at=now,
            expires=min(record["flow"]["expires"], now + LIFETIME),
        ),
        salt=READ_SALT,
    )
    AuditEvent.objects.create(
        actor=None,
        action="membership.public_receipt_verified",
        record_type="membership",
        record_id=str(receipt.purchase_id),
        changes={"checkout_id": record["checkout"], "customer_revision": customer.revision},
    )
    request.session[SESSION_KEY] = record
    return receipt


def receipt_for(request):
    receipt = owned_receipt(request)
    try:
        record = request.session[SESSION_KEY]
        data = signing.loads(record["proof"], salt=READ_SALT, max_age=LIFETIME)
        customer = receipt.purchase.customer
        now = timezone.now().timestamp()
        if (
            data["expires"] <= now
            or data["verified_at"] > now + 60
            or data["checkout"] != str(receipt.checkout_id)
            or record["checkout"] != str(receipt.checkout_id)
            or data["browser"] != record["browser"]
            or data["identity_key"] != record["flow"]["key"]
            or data["customer"] != customer.pk
            or data["revision"] != customer.revision
            or data["phone"] != customer.phone
        ):
            raise ValueError
    except (signing.BadSignature, KeyError, ValueError, TypeError, AttributeError):
        raise PermissionDenied from None
    return receipt
