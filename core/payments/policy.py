"""Versioned approved payment rules, kept distinct from waiver signatures."""

import hashlib

VERSION = "MD-PAYMENT-2026-01"
PAYMENT = (
    "You're almost done with your booking. Please enter your payment method. "
    "Please note: Payment will be processed after you arrive. For cash, check, "
    "or zelle, please enter a backup credit card. This card will be charged only "
    "in the event that another form of payment is not received. Once the payment "
    "is received upon arrival, the backup credit card information will be "
    "automatically deleted from our system."
)
RETENTION = (
    "The automatic removal above applies to a card used only for this booking. "
    "If you separately choose to keep this card for future visits, it will remain "
    "available for those visits. A card needed for another outstanding booking "
    "cannot be removed until that responsibility has been resolved or replaced."
)
CANCELLATION = (
    "If the booking is cancelled, or the customer doesn't arrive, the customer's "
    "credit card will be charged $3 per each $15 admission."
)
CANCELLATION_SCOPE = (
    "The approved fee is $3 per child admission, including Supervised Play. "
    "A required baby-only or adult-only admission also has a $3 fee; extra adult "
    "admissions do not. Owner-comped $0 bookings have no cancellation fee."
)
POLICY_HASH = hashlib.sha256(
    "\n".join([VERSION, PAYMENT, RETENTION, CANCELLATION, CANCELLATION_SCOPE]).encode()
).hexdigest()
