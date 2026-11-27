"""Initial public membership identity; no purchase or card collection here."""

import hashlib
import json
import uuid
from datetime import datetime
from datetime import timezone as dt_timezone

from django.conf import settings
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .customers import (
    check_email_available,
    check_phone_available,
    contact_lock,
    historical_email_customers,
)
from .forms import normalize_phone
from .membership_records import MembershipPublicCheckout
from .models import AuditEvent, Customer, OwnerNotice
from .payments.ledger import lock_request, writes_allowed
from .public_booking import customer_from_flow


@transaction.atomic
def begin(flow):
    """Consume the caller's private, completed shared-identity flow exactly once."""
    from .membership_public_authority import LIFETIME, PROOF_SALT
    from .membership_sales import enabled

    if not settings.MEMBERSHIP_SALES_ENABLED:
        raise PermissionDenied
    enabled()
    writes_allowed()
    try:
        now = timezone.now()
        expires = min(float(flow["expires"]), now.timestamp() + LIFETIME)
        if flow["stage"] != "details" or not expires > now.timestamp():
            raise ValueError
        key = lock_request(uuid.UUID(flow["key"]))
        identity = (
            flow["proof"]
            if flow.get("proof")
            else json.dumps(
                {"phone": normalize_phone(flow["phone"]), "contact": flow["contact"]},
                sort_keys=True,
            )
        )
        digest = hashlib.sha256(identity.encode()).hexdigest()
    except (KeyError, ValueError, TypeError, AttributeError):
        raise ValidationError(
            "Verify your customer details before choosing a membership."
        ) from None
    record = MembershipPublicCheckout.objects.select_related("customer").filter(pk=key).first()
    if record:
        if record.identity_hash != digest:
            raise PermissionDenied
        if record.customer.revision != record.customer_revision or record.expires_at <= now:
            raise ValidationError("Your customer verification expired or changed. Start again.")
    else:
        contact_lock()
        if flow.get("proof"):
            customer = customer_from_flow(flow, lock=True)
            if not customer.email:
                email = flow.get("contact_email", "").strip().lower()
                if not email:
                    raise ValidationError({"email": "Enter an email address to continue."})
                check_email_available(email, customer.pk)
                customer.email = email
                customer.revision += 1
                customer.full_clean()
                customer.save(update_fields=["email", "revision"])
                AuditEvent.objects.create(
                    actor=None,
                    action="customer.public_membership_email_added",
                    record_type="customer",
                    record_id=str(customer.pk),
                    changes={"email": email, "revision": customer.revision},
                )
        else:
            if flow.get("new_contact_ready") is not True:
                raise ValidationError("Complete your customer details before continuing.")
            values = flow["contact"]
            phone = normalize_phone(flow["phone"])
            check_phone_available(phone)
            check_email_available(values.get("email", ""))
            customer = Customer(
                last_name=values.get("last_name", "").strip(),
                phone=phone,
                email=values.get("email", "").strip().lower(),
                customer_type="family",
                referral_source=values.get("referral_source", "").strip(),
            )
            if not customer.email:
                raise ValidationError({"email": "Enter an email address to continue."})
            customer.full_clean()
            customer.save()
            previous_ids = list(
                historical_email_customers(customer.email, customer.pk).values_list("pk", flat=True)
            )
            if previous_ids:
                OwnerNotice.objects.create(
                    customer=customer,
                    subject="Email address reused from customer history",
                    details={"previous_customer_ids": previous_ids, "email": customer.email},
                )
            AuditEvent.objects.create(
                actor=None,
                action="customer.public_membership_created",
                record_type="customer",
                record_id=str(customer.pk),
                changes={
                    field: getattr(customer, field)
                    for field in ("last_name", "phone", "email", "referral_source")
                },
            )
        record = MembershipPublicCheckout.objects.create(
            id=key,
            customer=customer,
            customer_revision=customer.revision,
            identity_hash=digest,
            verified_at=now,
            expires_at=datetime.fromtimestamp(expires, dt_timezone.utc),
        )
        AuditEvent.objects.create(
            actor=None,
            action="membership.public_purchase_identity_verified",
            record_type="customer",
            record_id=str(customer.pk),
            changes={"checkout_id": str(key), "customer_revision": customer.revision},
        )
    return signing.dumps(
        dict(
            checkout=str(record.pk),
            purpose="purchase",
            customer=record.customer_id,
            revision=record.customer_revision,
            phone=record.customer.phone,
            key=str(record.pk),
            verified_at=record.verified_at.timestamp(),
            expires=record.expires_at.timestamp(),
        ),
        salt=PROOF_SALT,
    )


def resolve(data):
    """Called only after the shared authority verifier checks the signature/age."""
    record = MembershipPublicCheckout.objects.select_related("customer").get(
        pk=data["checkout"],
        customer_id=data["customer"],
        customer_revision=data["revision"],
        expires_at__gt=timezone.now(),
    )
    if (
        data.get("purpose") != "purchase"
        or str(record.pk) != data["key"]
        or record.verified_at.timestamp() != data["verified_at"]
        or record.expires_at.timestamp() != data["expires"]
        or record.customer.revision != data["revision"]
        or record.customer.phone != data["phone"]
    ):
        raise ValueError
    return data | {
        "request_key": record.pk,
        "checkout_record": record,
        "customer_record": record.customer,
        "operation": "purchase",
        "prior": None,
    }
