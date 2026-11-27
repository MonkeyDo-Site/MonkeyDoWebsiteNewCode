# Active memberships — authorized third stage

The owner authorized the complete saved [roadmap](THIRD_STAGE_ROADMAP.md) on November 26, 2026, with autonomous progress and early representative screen review. Use [membership rules](MEMBERSHIPS.md), [payment rules](PAYMENTS.md), [accepted email text](EMAIL_TEMPLATES.md) and [shared workflow standards](SHARED_WORKFLOW_STANDARDS.md). The accidental email/time pasted into the authorization are not contact or scheduling instructions.

## Reconciled scope

| Work | Accepted behavior | First implementation boundary |
|---|---|---|
| Purchases and accepted terms | Subscription/Unlimited anonymous places; versioned accepted terms/prices; three-month initial minimum with audited owner exceptions; monthly/prepaid; membership payment at purchase | Reuse immutable draft pricing/calendar as source calculations; active purchases have explicit acceptance and truthful collection state, with no automatic draft activation |
| Payments and installments | Exact-cent nontaxable membership/fee calculations; fixed-term scheduled installments; no automatic renewal/retries; unknown outcomes reconcile first | Reuse financial sale/line/posting, operation, durable job, provider and message-outbox infrastructure; distinguish pending, failed and paid |
| Booking benefits | Appointment date determines paid eligibility; Unlimited then Subscription free then $5.99 then ordinary; per-place/per-booking limits; stacked adult allowances; supervised/Chol Hamoed rules | Start with one deterministic pure planner; follow with atomic durable reservations/usage/release and integration across public/staff booking, edits, arrival and cancellation |
| Additions, renewals and changes | Separate purchase cohorts; original anchors/prices preserved; actual-date grace renewal, seven-day boundary, early renewal after expiry; explicit owner exceptions | Stable existing M identifiers, latest details and immutable historical facts; no rewriting consumed benefits or past receipts |
| Conversion and customer credit | Unpaid amounts never become credit; original card fee retained; accountant-directed fee-tax reversal; excess reusable credit; no double spending | Linked immutable adjustments/reallocations of existing paid funds; credit applications are not new receipts |
| Communications and operations | Combined booking/member email; approved notices only; no successful-installment receipts or automatic customer failure email; persistent overdue/credit alerts | Current verified customer contacts, private links, exact payment truth and deduplicated durable delivery |

## Review and implementation sequence

1. Reconcile and test eligibility, benefits, accepted dates/prices and payment calculations against the saved examples.
2. Prepare the compact purchase page, membership overview and member-aware booking samples early, using real calculation services and clearly labelled fictional/provider-simulated review data.
3. Build complete durable purchase/payment/installment and booking-benefit scenarios, then renewals/additions/exceptions, conversions/credit, communications and operational exports.
4. Keep one draft PR/gallery updated while the owner reviews samples; continue independent implementation and tests without requesting another go-ahead.
5. Prepare the as-built testing guide and reviewed schema/deployment handoff when the implementation and owner review are complete. Merge/deploy/live payments require separate explicit authorization.

## Affected pages and invariants

Public purchase/renewal and booking; staff membership list/detail/purchase/add/renew/cancel/correct; customer membership/payment cards; Today/Bookings/arrival/edit/cancel; Dashboard; secure card/signing returns; emails and membership/payment/benefit exports. Keep compact combined forms, bounded paging and useful status/type/customer/explicit-date filters. Existing membership IDs and signed evidence stay unchanged. Owner special admissions prices require explicit review; a member's free visit is not an owner-comped booking.

The existing public 20-minute booking-form limit and backend 30-minute temporary capacity reservation remain as approved. Benefit reservations occur on successful confirmed booking; they must not be consumed by a price preview. Membership never bypasses capacity, closure, visibility or waiver rules. Existing historical bookings/financial facts are not repriced automatically.

## Current evidence

First implementation increment: `core/membership_benefits.py` plans member pricing from trusted accepted-place/current-payment/usage inputs without mutating any record. Twenty-six focused tests cover the saved mixed-membership examples, per-place limits, benefit order and expiry, stacked adult allowances, supervised/Chol Hamoed exclusions, future appointment months/lapses, overdue state, accepted prices, nontaxable socks and owner-price/comped separation. It is not yet wired to active membership persistence, booking prices, benefit reservation locks or payment collection; those remain in progress. No existing draft or booking has been activated or repriced.

Integration check to complete before wiring owner-priced visits: the existing custom-admissions branch in `checkout_pricing.visit_lines` marks its separately added sock line taxable, unlike ordinary socks and the approved category. Reconcile that shared defect and its regression cases without rewriting historical snapshots.

The baseline is merged PR #36 (`91612c8bea19cd951afb390ab7194da61edd3f57`), with 712 passing application tests and passing GitHub checks. The owner said deployment was about to begin; this document does not independently confirm completion on the Droplet. Actual Banquest hosted-field layout and some provider-specific installment behavior remain technical verification items. No new provider call, hosted deployment or production billing is authorized by recording this scope.
