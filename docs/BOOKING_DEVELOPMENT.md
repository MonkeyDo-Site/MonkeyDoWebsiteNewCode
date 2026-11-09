# Staff test reservations and saved pricing

This increment supports local/staging staff testing. It does not enable public checkout or confirmed customer bookings.

## Staff workflow

Apply migrations, then rerun `python manage.py configure_staff_group` to grant the reviewed default staff group its new booking capabilities. Sign in and open **Bookings**. Create a test reservation for an existing customer and a future ordinary session, including backend-only sessions beyond the public booking horizon. Choose accompanied or supervised play, attendees, socks and expected payment method. Supervised play must be enabled for the session and cannot be reserved after its start; accompanied reservations remain available until the session ends.

Saving holds capacity and stores a price snapshot with status **Setup pending**. It does not assert verified card setup, waiver coverage, arrival, payment or confirmation delivery. Membership benefits are explicitly absent. Use artificial customers only.

Open a reservation to edit counts/payment choice, change timing, or use **Cancel booking**. Cancellation marks the test booking **Cancelled** and makes its spaces available. This pending-test action does not implement the final cancellation/no-show fee workflow and does not waive or charge a customer fee. Only pending records with blank attendance support these tools. Legacy records without a price snapshot retain that absence; attendee repricing is blocked rather than inventing historical amounts.

Owner capacity overrides are explicit and audited. They cannot override closures, party/exclusive sessions, ended sessions or supervised-play cutoff. Staff permissions are checked in both views and service functions. Competing capacity requests serialize on PostgreSQL session locks; stale edits are rejected. Repeated identical creation identifiers return the original record; changed payloads using that identifier are rejected.

## Pricing

Owner **Staging pricing** creates a new immutable version for future reservations. Existing snapshots remain unchanged; count/payment-choice edits use the original pricing version and append a new quote revision. Timing-only changes preserve the quote. Versions and quotes reject ORM updates/deletes and PostgreSQL UPDATE/DELETE. SQLite is local-only and permits raw DELETE for Django test cleanup; it is not the supported staging database.

Seeded prices: ordinary child $15; first accompanying adult free, additional adult $5; minimum admission for a babies-only/adults-only group $15; supervised child $18.99; socks $1.99. Admission is taxable; socks are nontaxable under the recorded requirements. Default staging tax is **6.6%**, card fee **3%**. Production pricing is blocked; UEZ approval remains outstanding.

Calculations use Decimal and round monetary components to cents with ROUND_HALF_UP. The processing fee applies to the discounted pretax subtotal, never sales tax. Tax includes taxable items plus the portion of the processing fee attributable to taxable items. The displayed quote has one processing-fee line and one combined sales-tax line. Noncard expected methods have no card fee. The quote is an estimate, not a payment ledger or evidence of money received.

For example: two ordinary child admissions with one accompanying adult produce $30 subtotal + $0.90 fee + $2.04 combined tax = **$32.94** using staging tax. Generic calculator regression cases cover the approved membership arithmetic after hypothetical benefit allocation; actual membership allocation is not implemented in this increment. The calculator can allocate a pretax card-funded base proportionally, but inclusive split-tender collection remains future payment work.

## Remaining integration

Card/waiver setup, confirmation emails, arrivals/charges, membership benefits/conversion credit, split tenders, real cancellation/no-show fees, owner special pricing/complimentary visits, refunds and Banquest/R2/Resend integrations remain unfinished. The original internal reservation primitive is retained for existing tests; it does not provide a public confirmed-booking API.

No hosted deployment, Droplet resize, provider call, outbound email or payment is performed by these tools. Production activation remains separate approved work.
