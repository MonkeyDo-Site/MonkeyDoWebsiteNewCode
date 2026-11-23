"""Versioned approved payment rules, kept distinct from waiver signatures."""

import hashlib

VERSION = "MD-PAYMENT-2026-03"
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
    "If the booking is cancelled, or the customer doesn’t arrive, the fee is $3 per each $15 or $18 admission. "
    "The customer’s credit card will be charged. The cancellation policy applies to members as specified in the membership agreement."
)
CANCELLATION_SCOPE = (
    "The approved fee is $3 per child admission, including Supervised Play. "
    "A required baby-only or adult-only admission also has a $3 fee; extra adult "
    "admissions do not. Owner-comped $0 bookings have no cancellation fee."
)
PRIMARY_PAYMENT = "You’re almost done with your booking. You chose to pay by credit card. Please enter your credit card info. Payment will be processed at your visit."
BACKUP_PAYMENT = "Please note: MonkeyDo requires a backup credit card for each booking by cash, check or Zelle. Please enter your credit card info. The card will only be charged in the event the form of payment you chose isn’t received."
PUBLIC_PAYMENT_ACCEPTANCE = "The customer accepts the displayed payment terms by explicitly selecting Save card securely; no separate payment-policy checkbox is presented. Cancellation acknowledgment and optional future-use consent remain separate."
BACKUP_CANCELLATION = CANCELLATION.replace(
    "credit card will be charged", "backup card will be charged"
)
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
        ]
    ).encode()
).hexdigest()
