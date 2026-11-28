"""Read-only estimates and amount-review proofs, bound to the exact saved edit version."""

import hashlib
import json

from django.core import signing
from django.core.exceptions import ValidationError

from .booking_management import calculate_quote, check_editable

SALT = "staff-booking-amount-reminder-v1"


def edit_estimate(booking, data, *, actor=None):
    check_editable(booking, data["version"])
    saved = booking.quotes.first()
    if not saved:
        raise ValidationError(
            "This booking has no saved pricing policy; an estimate cannot be invented."
        )
    values = {
        key: data[key]
        for key in ("children", "adults", "babies", "socks", "supervised", "expected_method")
    }
    if data.get("special_admissions") is not None:
        values["special_admissions"] = data["special_admissions"]
    values["session"] = data["session"]
    if data.get("membership_resolution"):
        from .membership_booking_exceptions import resolve

        values["membership_resolution_decision"] = resolve(
            booking,
            actor=actor,
            choice=data["membership_resolution"],
            reason=data.get("membership_resolution_reason", ""),
            session=data["session"],
        )
    if data.get("apply_available_benefits"):
        values["apply_available_benefits"] = True
    quote = calculate_quote(booking, saved.policy, values)
    payload = {
        **{
            key: str(value)
            if key == "special_admissions"
            else value.pk
            if key == "session"
            else value
            for key, value in values.items()
        },
        "session": data["session"].pk,
        "version": data["version"],
        "booking": booking.pk,
        "total": quote["total"],
        "policy": saved.policy_id,
    }
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    token = signing.dumps({"fingerprint": fingerprint}, salt=SALT)
    from .price_adjustments import booking_price_adjustment

    return {
        "quote": quote,
        "adjustment": booking_price_adjustment(booking, quote),
        "original_total": saved.snapshot["total"],
        "amount_changed": quote["total"] != saved.snapshot["total"],
        "token": token,
        "fingerprint": fingerprint,
    }


def amount_reviewed(token, estimate):
    try:
        value = signing.loads(token, salt=SALT, max_age=20 * 60)
        return value.get("fingerprint") == estimate["fingerprint"]
    except (signing.BadSignature, TypeError, AttributeError):
        return False
