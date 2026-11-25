"""Versioned approved payment rules, kept distinct from waiver signatures."""

import hashlib
from decimal import Decimal

VERSION = "MD-PAYMENT-2026-05"
PAYMENT = (
    "You're almost done with your booking. Please enter your payment method. "
    "Please note: Payment will be processed after you arrive. For cash, check, "
    "or zelle, please enter a backup credit card. This card will be charged only "
    "in the event that another form of payment is not received. Once the payment "
    "is received upon arrival, the backup credit card information will be "
    "automatically deleted from our system."
)
RETENTION = (
    "A card used only for this booking is automatically removed once its payment responsibilities are settled. "
    "If you choose to keep the card for future visits, it remains saved for those visits."
)

CANCELLATION = (
    "A cancelled booking or a no-show incurs a $3 fee per each $15 or $18.99 admission in the booking. "
    "The customer’s backup card will be charged. The cancellation policy applies to Members as specified in the membership agreement."
)
CANCELLATION_SCOPE = (
    "The approved fee is $3 per child admission, including Supervised Play. "
    "A required baby-only or adult-only admission also has a $3 fee; extra adult "
    "admissions do not. Owner-comped $0 bookings have no cancellation fee."
)
PRIMARY_PAYMENT = "You’re almost done with your booking. You chose to pay by credit card. Please enter your credit card info. Payment will be processed at your visit."
BACKUP_PAYMENT = "Please note: MonkeyDo requires a backup credit card for each booking by cash, check or Zelle. Please enter your credit card info. The card will only be charged in the event the form of payment you chose isn’t received at the time of arrival."
PUBLIC_PAYMENT_ACCEPTANCE = "The customer accepts the displayed payment terms by explicitly selecting Confirm booking; no separate payment-policy checkbox is presented. Cancellation acknowledgment and optional future-use consent remain separate."
BACKUP_CANCELLATION = CANCELLATION
CANCELLATION_PRICE_RULE = "Admission prices follow the accepted booking pricing policy; exact displayed terms are retained in the consent audit."
POLICY_HASH = hashlib.sha256(
    "\n".join(
        [
            VERSION,
            PAYMENT,
            RETENTION,
            CANCELLATION,
            CANCELLATION_SCOPE,
            PRIMARY_PAYMENT,
            BACKUP_PAYMENT,
            PUBLIC_PAYMENT_ACCEPTANCE,
            BACKUP_CANCELLATION,
            CANCELLATION_PRICE_RULE,
        ]
    ).encode()
).hexdigest()


def displayed_cancellation(flow=None):
    from core.models import Booking, PricingPolicy

    policy = None
    if flow and flow.get("staff_booking"):
        booking = Booking.objects.filter(pk=flow["staff_booking"]).first()
        saved = booking.quotes.first() if booking else None
        policy = saved.policy if saved else None
    elif flow and flow.get("quote", {}).get("policy_id"):
        policy = PricingPolicy.objects.filter(pk=flow["quote"]["policy_id"]).first()
    policy = policy or PricingPolicy.objects.first() or PricingPolicy()
    prices = [
        format(value, ".0f") if value == value.to_integral_value() else format(value, ".2f")
        for value in (Decimal(str(policy.child_price)), Decimal(str(policy.supervised_price)))
    ]
    wording = CANCELLATION.replace("$15 or $18.99", f"${prices[0]} or ${prices[1]}")
    return wording, policy.pk
