"""Pending test reservations from a browser-owned, expiring public booking flow."""

import json
import unicodedata
import uuid

from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .availability import availability
from .booking_management import assert_capacity, snapshot
from .calendar import lock_calendar
from .customers import (
    check_email_available,
    check_phone_available,
    contact_lock,
    historical_email_customers,
)
from .forms import normalize_phone
from .models import (
    AuditEvent,
    Booking,
    BookingQuote,
    Customer,
    OwnerNotice,
    PricingPolicy,
    Session,
    SiteSettings,
)
from .pricing import booking_quote, validate_attendees

LIFETIME = 20 * 60
PROOF_SALT = "customer-test-booking-profile"
DETAILS = ("children", "adults", "babies", "socks", "supervised", "expected_method")


def canonical_name(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def lookup_phone(phone):
    phone = normalize_phone(phone)
    matches = list(Customer.objects.filter(Q(phone=phone) | Q(previous_phone=phone))[:2])
    if len(matches) > 1:
        raise ValidationError("Please call or text 848-238-5147 for help with this booking.")
    return matches[0] if matches else None


def profile_proof(customer, key):
    return signing.dumps(
        {"id": customer.pk, "revision": customer.revision, "phone": customer.phone, "key": key},
        salt=PROOF_SALT,
    )


def customer_from_flow(flow, *, lock=False):
    try:
        proof = signing.loads(flow["proof"], salt=PROOF_SALT, max_age=LIFETIME)
        if proof["key"] != flow["key"]:
            raise ValueError
        qs = Customer.objects.select_for_update() if lock else Customer.objects
        customer = qs.get(pk=proof["id"])
        if customer.revision != proof["revision"] or customer.phone != proof["phone"]:
            raise ValueError
    except (KeyError, ValueError, signing.BadSignature, Customer.DoesNotExist):
        raise ValidationError(
            "Customer details changed or verification expired. Start again."
        ) from None
    return customer


def assert_flow(flow):
    if not settings.CUSTOMER_TEST_BOOKING:
        raise ValidationError("Customer test booking is not enabled.")
    if not flow or timezone.now().timestamp() > flow.get("expires", 0):
        raise ValidationError("This booking session expired. Please start again.")
    try:
        uuid.UUID(flow["key"])
    except (KeyError, ValueError, TypeError):
        raise ValidationError("Start a new booking session.") from None


def public_session(session_id, *, lock=False):
    qs = Session.objects.select_for_update() if lock else Session.objects
    try:
        session = qs.get(pk=session_id)
    except Session.DoesNotExist:
        raise ValidationError("This play session is unavailable.") from None
    horizon = (
        SiteSettings.objects.filter(pk=1).values_list("booking_horizon_days", flat=True).first()
        or 1
    )
    state = availability(session, horizon)
    if not state["available"]:
        raise ValidationError("This play session is unavailable. Please choose another time.")
    return session


def review_quote(flow, data):
    assert_flow(flow)
    session = public_session(flow["session_id"])
    validate_attendees(
        **{k: data[k] for k in ("children", "adults", "babies", "supervised", "socks")}
    )
    if data["socks"] > 35:
        raise ValidationError("Online sock purchases have a 35-pair limit.")
    assert_capacity(
        session, actor=None, **{k: data[k] for k in ("children", "adults", "supervised")}
    )
    policy = PricingPolicy.objects.first()
    if policy is None:
        raise ValidationError("Pricing is not available yet.")
    return booking_quote(policy, **{k: data[k] for k in DETAILS})


@transaction.atomic
def submit_booking(flow):
    """No staff impersonation; no card setup, waiver, email or confirmation assertion."""
    assert_flow(flow)
    key = uuid.UUID(flow["key"])
    fingerprint = salted_hmac(
        "public-booking", json.dumps(flow, sort_keys=True), algorithm="sha256"
    ).hexdigest()
    lock_calendar()
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(%s, %s)",
                [73215, int.from_bytes(key.bytes[:4], signed=True)],
            )
    existing = Booking.objects.filter(creation_key=key).first()
    if existing:
        if existing.source != "customer_test" or existing.creation_fingerprint != fingerprint:
            raise ValidationError("This booking session has already been used. Start again.")
        return existing
    from . import booking_completion

    completing = booking_completion.integrated(flow)
    if not completing and (settings.BOOKING_COMPLETION_ENABLED or settings.APP_ENV == "staging"):
        raise ValidationError(
            "Restart this booking to complete the current waiver and card setup.",
            code="legacy_booking_flow",
        )
    if completing:
        booking_completion.enabled()
        from .payments.setup import selected_consent

        selected_consent(flow)
    contact_lock()
    deferred_email = None
    if flow.get("proof"):
        customer = customer_from_flow(flow, lock=True)
        if not customer.email:
            email = flow.get("contact_email", "").strip().lower()
            if not email:
                raise ValidationError(
                    {"email": "An email address is required for public bookings."}
                )
            check_email_available(email, customer.pk)
            # Keep the verified customer revision unchanged until card/waiver
            # bindings have been checked inside this same transaction.
            deferred_email = email
    else:
        values = flow.get("contact")
        if not values:
            raise ValidationError("Enter your contact details first.")
        phone = normalize_phone(flow["phone"])
        check_phone_available(phone)
        check_email_available(values["email"])
        customer = Customer(
            last_name=values["last_name"],
            phone=phone,
            email=values["email"].strip().lower(),
            customer_type="family",
            referral_source=values.get("referral_source", "").strip(),
        )
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
            action="customer.public_test_created",
            record_type="customer",
            record_id=str(customer.pk),
            changes={
                "last_name": customer.last_name,
                "phone": phone,
                "email": customer.email,
                "referral_source": customer.referral_source,
            },
        )
    session = public_session(flow["session_id"], lock=True)
    data = flow["details"]
    quote = review_quote(flow, data)
    if quote != flow.get("quote"):
        raise ValidationError("The price changed. Review the updated estimate before submitting.")
    booking = Booking.objects.create(
        customer=customer,
        session=session,
        source="customer_test",
        workflow="integrated_v1" if completing else "legacy_test",
        creation_key=key,
        creation_fingerprint=fingerprint,
        **{k: data[k] for k in DETAILS},
        zelle_sender=data.get("zelle_sender", "") if completing else "",
    )
    saved = BookingQuote.objects.create(
        booking=booking, policy_id=quote["policy_id"], revision=1, snapshot=quote, actor=None
    )
    AuditEvent.objects.create(
        actor=None,
        action="booking.customer_test_created",
        record_type="booking",
        record_id=str(booking.reference),
        changes={"after": snapshot(booking), "quote_id": saved.pk, "source": "customer_test"},
    )
    if completing:
        booking_completion.complete(flow, booking)
    if deferred_email is not None:
        email = deferred_email
        customer.email = email
        customer.revision += 1
        customer.full_clean()
        customer.save(update_fields=["email", "revision"])
        AuditEvent.objects.create(
            actor=None,
            action="customer.public_email_added",
            record_type="customer",
            record_id=str(customer.pk),
            changes={"email": {"before": "", "after": email}},
        )
        previous_ids = list(
            historical_email_customers(email, customer.pk).values_list("pk", flat=True)
        )
        if previous_ids:
            OwnerNotice.objects.create(
                customer=customer,
                subject="Email address reused from customer history",
                details={"previous_customer_ids": previous_ids, "email": email},
            )
    if completing:
        booking_completion.confirmation(booking, flow=flow)
    return booking
