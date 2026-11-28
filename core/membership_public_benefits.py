"""One completed private booking can explicitly reserve a newly available benefit.

The original twenty-minute booking capability is not extended. This service
cannot edit attendees, change a card, confirm a waiver, record arrival or pay.
Existing immutable quotes and reservation batches hold the accepted evidence.
"""

from django.core.exceptions import ValidationError
from django.db import transaction

from .booking_management import calculate_quote, check_editable
from .calendar import lock_calendar
from .membership_booking import COUNTS, existing_daily_places
from .membership_records import MembershipBenefitBatch
from .membership_reservations import lock_customer, reserve
from .membership_sales import enabled
from .models import AuditEvent, Booking, BookingQuote, Customer, Session
from .payments.amounts import amount
from .payments.checkout import charge_state
from .payments.ledger import fingerprint, lock_request, writes_allowed
from .public_booking import assert_flow, canonical_name, customer_from_flow

MARKER = "public_membership_benefit"


def owned_booking(flow):
    enabled()
    assert_flow(flow)
    if (
        flow.get("stage") != "done"
        or flow.get("workflow") != "integrated_v1"
        or flow.get("staff_actor")
    ):
        raise ValidationError("Return to your completed booking to review its available benefit.")
    booking = (
        Booking.objects.select_related("customer", "session")
        .filter(
            pk=flow.get("booking_id"),
            creation_key=flow["key"],
            creation_actor=None,
            source="customer_test",
            workflow="integrated_v1",
        )
        .first()
    )
    if booking is None:
        raise ValidationError("Return to your original booking in this browser.")
    customer = booking.customer
    if flow.get("proof"):
        if customer_from_flow(flow).pk != customer.pk:
            raise ValidationError("Verify the customer who made this booking.")
    else:
        # A new customer has no returning-profile proof. The original private
        # completed flow must still match that untouched profile exactly.
        contact = flow.get("contact") or {}
        if (
            customer.revision != 1
            or customer.phone != flow.get("phone")
            or canonical_name(customer.last_name) != canonical_name(contact.get("last_name", ""))
            or customer.email.casefold() != str(contact.get("email", "")).strip().casefold()
        ):
            raise ValidationError(
                "Your customer details changed. Ask MonkeyDo to review this benefit."
            )
    return booking


def review(*, flow):
    booking = owned_booking(flow)
    check_editable(booking, booking.edit_version)
    state = charge_state(booking)
    if booking.setup_pending or state.comped or state.special_subtotal is not None:
        raise ValidationError("Ask MonkeyDo to review this booking's existing price exception.")
    saved = booking.quotes.first()
    if saved is None:
        raise ValidationError("Ask MonkeyDo to review this booking's membership price.")
    quote = calculate_quote(
        booking,
        saved.policy,
        {key: getattr(booking, key) for key in (*COUNTS, "expected_method")}
        | {"apply_available_benefits": True},
    )
    current = existing_daily_places(booking)
    if not any(
        use["kind"] == "unlimited_daily" and (use["membership_id"], use["place"]) not in current
        for use in quote["membership_plan"]["uses"]
    ):
        raise ValidationError("No additional Unlimited benefit is available for this booking.")
    if amount(quote["total"]) > amount(saved.snapshot["total"]):
        raise ValidationError(
            "Ask MonkeyDo to review the current price before applying this benefit."
        )
    from .payments.zelle import facts as zelle_facts

    agreement = getattr(booking, "card_agreement", None)
    facts = {
        "booking": booking.pk,
        "version": booking.edit_version,
        "previous_quote": saved.pk,
        "previous_total": saved.snapshot["total"],
        "billing_revision": state.revision,
        "provenance": fingerprint(
            dict(customer=booking.customer_id, revision=booking.customer.revision, flow=flow["key"])
        ),
        "card": {
            "consent": str(agreement.consent_id),
            "method": str(agreement.method_id),
        }
        if agreement
        else None,
        "prepayments": zelle_facts(booking)["identity"],
        "quote": quote,
    }
    from .price_adjustments import booking_price_adjustment

    return dict(
        booking=booking,
        previous=saved,
        quote=quote,
        adjustment=booking_price_adjustment(booking, quote),
        facts=facts,
        fingerprint=fingerprint(facts),
    )


@transaction.atomic
def confirm(*, flow, request_key, reviewed_hash, confirmed):
    writes_allowed()
    booking = owned_booking(flow)
    if confirmed is not True:
        raise ValidationError("Review and confirm the updated booking price.")
    key = lock_request(request_key)
    lock_calendar()
    booking = Booking.objects.select_for_update().get(pk=booking.pk)
    Session.objects.select_for_update().get(pk=booking.session_id)
    Customer.objects.select_for_update(no_key=True).get(pk=booking.customer_id)
    lock_customer(booking.customer_id)
    # Recheck the private capability/contact after waiting for all locks.
    booking = owned_booking(flow)
    previous = MembershipBenefitBatch.objects.select_related("quote").filter(pk=key).first()
    if previous:
        evidence = previous.quote.snapshot.get(MARKER, {}) if previous.quote else {}
        if (
            previous.booking_id != booking.pk
            or previous.actor_id is not None
            or previous.action != "reserved"
            or evidence.get("request") != str(key)
            or evidence.get("reviewed") != reviewed_hash
        ):
            raise ValidationError("This confirmation already identifies another booking change.")
        return previous.quote
    reviewed = review(flow=flow)
    if reviewed["fingerprint"] != reviewed_hash:
        raise ValidationError(
            "The booking or available benefits changed. Review the current price."
        )
    booking.edit_version += 1
    booking.save(update_fields=["edit_version"])
    saved = BookingQuote.objects.create(
        booking=booking,
        policy=reviewed["previous"].policy,
        revision=booking.edit_version,
        actor=None,
        snapshot=reviewed["quote"]
        | {
            MARKER: dict(
                request=str(key),
                reviewed=reviewed_hash,
                provenance=reviewed["facts"]["provenance"],
            )
        },
    )
    reserve(actor=None, booking_id=booking.pk, quote_id=saved.pk, request_key=key)
    AuditEvent.objects.create(
        action="booking.membership_benefit_applied",
        record_type="booking",
        record_id=str(booking.reference),
        changes={
            "source": "public_booking_receipt",
            "quote_id": saved.pk,
            "previous_quote_id": reviewed["previous"].pk,
            "amount_due": {
                "before": "$" + reviewed["facts"]["previous_total"],
                "after": "$" + reviewed["quote"]["total"],
            },
        },
    )
    return saved
