"""A durable system claim remains separate from public or staff permission."""

import uuid
from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .availability import NEW_YORK
from .membership_collection_plan import installment_plan
from .membership_records import MembershipCollectionClaim, MembershipInstallment
from .membership_reservations import lock_customer
from .membership_sales import enabled as membership_enabled
from .membership_sales import today
from .models import AuditEvent
from .payments.ledger import fingerprint, lock_request, writes_allowed


def enabled():
    membership_enabled()
    writes_allowed()
    if not settings.MEMBERSHIP_COLLECTIONS_ENABLED:
        raise PermissionDenied


def claim_key(item):
    return uuid.uuid5(item.purchase.request_key, f"scheduled-installment:{item.number}")


def current_claim(value):
    """Validate the exact persisted scope before financial services may use it."""
    enabled()
    if type(value) is not MembershipCollectionClaim:
        raise PermissionDenied
    try:
        claim = MembershipCollectionClaim.objects.select_related("installment__purchase").get(
            pk=value.pk
        )
    except (MembershipCollectionClaim.DoesNotExist, ValueError, TypeError):
        raise PermissionDenied from None
    body = {key: val for key, val in claim.details.items() if key != "fingerprint"}
    if (
        claim.pk != claim_key(claim.installment)
        or claim.payment_key != uuid.uuid5(claim.pk, "payment")
        or claim.credit_key != uuid.uuid5(claim.pk, "credit")
        or claim.fingerprint != fingerprint(body)
        or claim.details.get("fingerprint") != claim.fingerprint
        or claim.planned_on != today()
        or claim.expires_at <= timezone.now()
        or claim.details.get("installment") != claim.installment_id
        or claim.details.get("mandate") != str(claim.mandate_id)
    ):
        raise PermissionDenied
    return claim


def authorize(value):
    """Authorize a pristine preparation; dispatch will have its own live checks."""
    claim = current_claim(value)
    plan = installment_plan(claim.installment_id)
    if plan["status"] != "ready_for_scheduling" or plan["fingerprint"] != claim.fingerprint:
        raise ValidationError("The scheduled installment changed and needs review.")
    return claim


@transaction.atomic
def prepare_claim(installment_id):
    enabled()
    item = MembershipInstallment.objects.select_related("purchase").get(pk=installment_id)
    lock_customer(item.purchase.customer_id)
    key = lock_request(claim_key(item))
    existing = MembershipCollectionClaim.objects.filter(pk=key).first()
    if existing:
        return authorize(existing)
    plan = installment_plan(item.pk)
    if plan["status"] != "ready_for_scheduling":
        raise ValidationError("This installment requires review before scheduled collection.")
    expiry = timezone.make_aware(datetime.combine(today() + timedelta(days=1), time.min), NEW_YORK)
    claim = MembershipCollectionClaim.objects.create(
        id=key,
        installment=item,
        mandate_id=uuid.UUID(plan["mandate"]),
        payment_key=uuid.uuid5(key, "payment"),
        credit_key=uuid.uuid5(key, "credit"),
        planned_on=today(),
        expires_at=expiry,
        fingerprint=plan["fingerprint"],
        details=plan,
    )
    AuditEvent.objects.create(
        actor=None,
        action="membership.collection_claimed",
        record_type="membership",
        record_id=str(item.purchase_id),
        changes={"installment": item.pk, "claim": str(claim.pk), "payment_requested": False},
    )
    return claim
