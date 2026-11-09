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
from .customers import check_phone_available, contact_lock
from .forms import normalize_phone
from .models import (
    AuditEvent,
    Booking,
    BookingQuote,
    Customer,
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
    contact_lock()
    if flow.get("proof"):
        customer = customer_from_flow(flow, lock=True)
    else:
        values = flow.get("contact")
        if not values:
            raise ValidationError("Enter your contact details first.")
        phone = normalize_phone(flow["phone"])
        check_phone_available(phone)
        customer = Customer(
            last_name=values["last_name"],
            phone=phone,
            email=values["email"],
            customer_type="family",
        )
        customer.full_clean()
        customer.save()
        AuditEvent.objects.create(
            actor=None,
            action="customer.public_test_created",
            record_type="customer",
            record_id=str(customer.pk),
            changes={"last_name": customer.last_name, "phone": phone, "email": customer.email},
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
        creation_key=key,
        creation_fingerprint=fingerprint,
        referral_source=data["referral_source"],
        **{k: data[k] for k in DETAILS},
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
    return booking
