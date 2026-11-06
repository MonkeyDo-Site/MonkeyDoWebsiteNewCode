# Membership draft foundation

This increment adds **test membership drafts**, not purchased/active memberships. It establishes immutable product prices, separate draft cohorts, civil-date calendar calculations and saved planned payment estimates. No payment, card consent, accepted terms, benefit grant, job or email is created.

## Staff use

Apply migrations, then rerun `python manage.py configure_staff_group` to add the reviewed draft creation/view capabilities. Open **Membership drafts**, create a draft for an existing artificial customer, and choose Subscription/Unlimited, anonymous place count, whole-month duration, monthly/prepaid billing, expected payment method and a test start date. New drafts require three months minimum; durations are not limited to a fixed selector. Calendar representability is validated before allocating cycles.

The selected test date represents a hypothetical new purchase/start date; a future planning date does not defer a real membership purchase charge. The final sale workflow still must collect membership payment at purchase independently of future visit payment.

Each submission saves a distinct draft cohort with its original day anchor, product price version, fee policy, start/end dates, rule version, count and billing choice. Repeating an identical submission returns that draft; changing its payload under the same identifier is rejected. Drafts cannot be edited, activated or deleted through these screens. Preparing a different scenario creates a new draft rather than rewriting history. The customer page links to that customer's drafts.

Owner **Membership pricing** appends an immutable monthly product-price version (initially $17.99 Subscription/$39.99 Unlimited per anonymous place). The existing **Staging pricing** screen supplies the card-fee policy. Saved drafts keep both versions even after future prices change. Ordinary staff cannot set product prices.

## Dates and financial estimates

Cycles use New York civil dates, preserving the original billing-day anchor. When the anniversary exists, payment and benefit-reset dates coincide. Otherwise payment is planned on the shorter month's final day and reset on the next day. Later months return to the original anchor.

- January 29 in a leap year: charge/reset February 29.
- January 29 in a non-leap year: charge February 28, reset March 1.
- January 30/31: charge the final February day, reset March 1, then return to the original March anchor.
- October 31: charge November 30/reset December 1, then charge/reset December 31. Three months run October 31 through January 30.

Persisted cycle bounds and planned payment dates are separate fields. They are not a collection schedule or evidence of paid/available benefits. Monthly drafts show one planned installment per month; prepaid drafts show the entire selected term in the first payment and no further installments. Membership charges and their card fee are nontaxable under the approved business classification. Quotes use the existing Decimal calculator; noncard expected tender has no processing fee. Amounts describe only the membership draft, with no admission conversion/credit or bundled visit allocation.

The pure renewal-calendar helper covers early renewal, actual-date grace renewal, December 12/13 boundary and minimum-term selection. It is not exposed as a renewal sale screen and does not alter existing memberships. The initial-draft screen still requires the new-purchase three-month minimum.

## Integrity and verification limits

Drafts, cycles and product-price versions reject application updates/deletes and PostgreSQL UPDATE/DELETE. SQLite guards UPDATE only, allowing its test cleanup; it does not establish PostgreSQL concurrency safety. PostgreSQL serializes repeated creation identifiers and persists the draft, all cycle estimates and audit as one transaction. Staff view/create and customer-view capabilities are enforced server-side; owner pricing is separately guarded.

Deferred: actual purchases and accepted checkout terms, saved cards/payment outcomes, installments/jobs/overdue state, benefit allocation and booking integration, renewal/addition/consolidation workflows, complimentary memberships, cancellations/refunds, admission conversion/customer-credit ledger, reports and notifications. Draft package descriptions are previews, not active entitlements. No Banquest/R2/Resend operations, deployment, hosting changes or purchases occur.
