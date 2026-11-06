# Membership requirements

Current owner decisions consolidated November 5, 2026. [Main requirements](MONKEYDO_REQUIREMENTS.md), [payments](PAYMENTS.md), and [email wording](EMAIL_TEMPLATES.md) supply shared behavior. These rules are not implemented by this documentation change.

## 1. Products, anonymous places, and public copy

| Rule | Subscription Membership | Unlimited Membership |
|---|---|---|
| Price per place/month | **$17.99** | **$39.99** |
| Ordinary child admission | Two free visits per place per membership month, then unlimited **$5.99** visits that month | One free visit per purchased place per New York calendar day |
| Adults | Two free when Subscription benefits apply | Two free when Unlimited benefits apply |
| Supervised play | 25% off: **$14.24** per eligible child | No discount/free benefit; **$18.99** |
| Chol Hamoed | Subscription benefits continue | Unlimited benefits excluded; ordinary pricing |
| Parties | **15%** | **15%** |
| Initial commitment | Minimum **three months** | Minimum **three months** |

Places are not assigned to named children. Three Unlimited Memberships cover up to three child daily benefits, not unlimited visits for an entire family. Ordinary bookings still require an adult and available capacity. Membership is not guaranteed admission.

Subscription marketing:

> $17.99 per child, per month <br>
> Two free play sessions per month <br>
> Just $5.99 for every additional play session that month <br>
> Two free adults for every visit <br>
> 25% off supervised play <br>
> 15% discount on parties. Call/text for details. <br>
> Three-month minimum

Unlimited marketing:

> $39.99 per child, per month <br>
> One free visit per day with two free adults <br>
> 15% discount on parties. Call/text for details. <br>
> Three-month minimum <br>
> * Excludes Chol Hamoed and supervised play. Unlimited Members pay full price for Chol Hamoed and supervised-play visits.

Do not put an exhaustive technical eligibility checklist on marketing cards. Present applicable price/consent information at purchase. “Month” is public copy; cycle is an internal concept.

### Owner-supplied checkout terms (AG)

Unlimited:

> Your membership begins on [date] and continues for [number] months. New memberships require a minimum initial term of three months. If you select monthly billing, the saved payment method will be charged monthly automatically, starting from today. Cancellation and no-show fees apply to all visits booked with membership benefits. Members enjoy a 15% discount on parties. Supervised play and Chol Hamoed visits are excluded from membership benefits. Members can book supervised play and Chol Hamoed visits at full price. Membership can be renewed after the membership ends. Membership that is renewed one week past the membership end date is subject to a three month minimum. Membership renewed within a week has no monthly minimum. Membership cannot be cancelled during the initial three month term.

Subscription:

> Your membership begins on [date] and continues for [number] months. New memberships require a minimum initial term of three months. If you select monthly billing, the saved payment method will be charged monthly automatically, starting from today. Cancellation and no-show fees apply to all visits booked with membership benefits. Unused free visits do not roll over to the next month. Members enjoy 25% off on supervised play visits and a 15% discount on parties. Membership can be renewed after the membership ends. Membership that is renewed one week past the membership end date is subject to a three month minimum. Membership renewed within a week has no monthly minimum. Membership cannot be cancelled during the initial three month term.

Operational interpretation: renewals may be purchased ahead of expiration and begin after the old term; “no monthly minimum” means the initial three-month minimum is not repeated for qualifying renewal, not a zero-month term. At least one month is purchased. The explicit seven-day examples below govern the boundary. Owner may make exceptional early cancellation or renewal overrides. The selected term ends without automatic renewal; scheduled installments only complete the term purchased. Keep exact accepted terms/version with the purchase; do not substitute the old assistant twenty-item outline.

## 2. Terms, cohorts, and billing

- Any whole-number duration, minimum three for new membership/additional places; no maximum. Common choices 3/4/5/6/12 plus Enter another number/whole-number selector. Extensions can be one or two months. Not limited to old 3/6/9/12 choices.
- Monthly or full-term upfront payment, no prepayment discount. New membership charge at purchase, independent of a future visit's arrival charge. With combined purchase/booking send one combined email showing accurate paid/due portions.
- Each later purchase/addition creates a separate cohort with place count, type, accepted price, start/end, original billing anchor, cycles and initial commitment. Types may coexist. Preserve accepted price through that term; renewal shows/accepts then-current price unless owner exception.
- Future price changes must not silently rewrite accepted cohort prices or historical benefits.
- Only owner may consolidate cohorts: show originals, choose effective date/resulting count/expiry/billing schedule/financial adjustment, end originals/create replacement, preserve history. No silent consolidation.
- No ordinary cancellation in the initial three months. Afterward customer calls/texts; owner chooses immediate or end-current-cycle cancellation and refund. Owner may make early exceptions and create complimentary memberships for any duration.

### Billing calendar

Use original billing-day anchor; benefit reset and charge date sometimes differ in short months. Persist each calculated cycle's bounds, charge schedule/outcome and allocations; never infer all history from current settings.

| Purchase/example | First relevant charge/reset | Following cycle |
|---|---|---|
| August 5 | Next charge and reset September 5; first cycle Aug5–Sep4 | Original fifth-day anchor |
| October 31 | Charge November 30; reset December 1; first cycle through Nov30 | Dec1–Dec30; charge/reset Dec31; next through Jan30 |
| January 29, non-leap year | Charge Feb28; reset Mar1 | Mar1–Mar28; charge/reset Mar29 |
| January 29, leap year | **Charge and reset Feb29** (latest clarification) | Next charge/reset Mar29 |
| January 30 | Charge last February day; reset Mar1 | Through Mar29; charge/reset Mar30 |
| January 31 | Charge last February day; reset Mar1 | Through Mar30; charge/reset Mar31 |

General rule: when anniversary exists, charge/reset then. Otherwise charge last day of shorter month, reset following day, and return to original anchor when available. Leap-year Jan29 is settled, not open. Implement New York/DST semantics; gateway schedule “EST” wording alone does not establish compliance.

## 3. Benefit reservation and adult allowances

- Appointment date, not booking creation date, determines active paid term, cycle/daily benefit and exclusions. Benefits unavailable during lapse or overdue-payment inactivity.
- A cohort with N places covers at most N children in one booking. Two Subscription places have four free child visits per cycle but cannot make four children free in one booking: at most two apply; other children are ordinary price.
- Each Subscription place gets two free visits then unlimited $5.99 ordinary visits in its paid cycle. No rollover.
- Each Unlimited place supplies one child benefit per calendar day. Reserve on successful confirmed booking; prevent concurrent double allocation. Additional same-day visits after benefit use follow ordinary pricing unless independent Subscription benefits apply.
- Allocate available Unlimited daily benefits, then free Subscription benefits, then Subscription $5.99 benefits, then ordinary $15. Within eligible free benefits use soonest-expiring first.
- Multiple places of one type do not multiply that type's adult allowance. Subscription-only qualifying visit: two free adults. Unlimited-only benefit visit: two. Both types applying in the same booking: **four free adults**; fifth+ $5. On an Unlimited-only second visit or Chol Hamoed without benefits, ordinary first-adult-free rules apply. Subscription benefits can still supply their adult allowance independently.
- Chol Hamoed marking is date-level only, no per-slot overrides. Excludes Unlimited benefits, not the customer; full-price booking remains possible and does not consume excluded benefits. Subscription continues. Preserve date designation in price snapshot.
- Supervised Subscription discount does not consume ordinary free/$5.99 visits; Unlimited supplies no supervised discount.

| Example: 2 Subscription + 1 Unlimited place | Pretax ordinary admission result |
|---|---:|
| First Monday visit, 4 children +2 adults, Subscription free benefits available | $15.00 (1 Unlimited +2 Subscription free; 1 ordinary child) |
| Wednesday, 3 children +3 adults, remaining Subscription free visits | $0.00 (both types apply; adult allowances stack) |
| Friday, 4 children +2 adults, Subscription free visits exhausted | $26.98 (1 Unlimited +2×$5.99 +1×$15) |
| Second Monday visit, 3 children +2 adults, Unlimited already used but 2 Subscription free benefits available | $15.00 |

### Changes, cancellations, and reinstatement

- Cancel/no-show/reduce children: release applicable free/daily benefit allocation, preserve history, apply approved $3 per affected child unless fee waived. Member free or $5.99 admission does not eliminate fee. Partial-removal fee waits until remaining visit payment at arrival.
- Reschedule across dates/cycles: release old reservations, recalculate benefit eligibility and pricing for new appointment, record before/after. Same-day move transfers Unlimited usage without double consuming.
- Released Unlimited benefits do not automatically reprice another existing booking. Before finalization/payment customer may use **Apply available Unlimited benefit**, review new price and confirm; owner/staff can also explicitly apply.
- After installment failure, do not automatically cancel or reprice existing future bookings. Owner reviews overdue installment/affected bookings and chooses payment resolution, ordinary pricing, cancellation or exception. Preserve snapshots/audit for explicit changes.

## 4. Renewals

- Early renewal starts the day after current term ends, not immediately. An initial purchase's selected term ends unless affirmatively renewed.
- Seven-day grace after expiry allows renewal without new three-month commitment; owner may override. **No benefits during the gap**. Renewal during grace starts actual renewal date and anchors new cycles there, not backdated.
- Example expires Dec5: renew Dec6 -> starts Dec6; renew Dec10 -> starts Dec10, no benefits Dec6–9; renew through Dec12 qualifies, Dec13 normally new three-month minimum.
- May change type or renew fewer places at renewal. If count/type matches all eligible expiring places, renew them; otherwise show cohort type/count/start/expiry/cycle/price and ask which places. A transaction can renew multiple cohorts while keeping each history/schedule. New additional places still have their own initial minimum.
- Type conversion normally takes effect after old cohort expires. Owner may make a midterm exception. Preserve old usage and accepted new price/type in a new linked cohort.
- Show booking-flow renewal opportunity within five days of expiry; allow Renew / Not now / email reminder. After Not now, one further prompt when booking at least 30 days after expiry. Personalized renewal link lasts 30 days, verifies phone/last name and shows only renewal data; a 30-day link does not extend the seven-day minimum-term grace.
- Approved notices: five days before expiry and one day before grace ends; one per relevant cohort, suppress obsolete notices when renewed. These are membership notices, not a restoration of prohibited appointment reminders. Already-expired “Email me later” option must use appropriate future notice timing, not a past expiry-relative date; exact discretionary timing is an implementation detail to make explicit before enabling that optional path.
- Membership history/benefit usage belongs in membership records, not customer comments. Export active/expiring memberships, payment history and benefit usage.

## 5. Failed installments, cancellation, and permissions

- No automatic charge retries initially. Persistent Dashboard and owner email alert identifies customer/cohort/installment and affected future bookings. No automatic customer failure email; optional owner-triggered follow-up template exists.
- Temporarily inactive benefits until required payments current. During booking allow secure payment-method update/manual resolution; do not finalize a member-priced booking while unresolved. Staff may assist/retry after customer contact.
- Optional future enhancement: after experience, ask owner whether failure volume justifies retries. Do not enable by default.
- Owner cancellation screen shows current/future cycles, paid/refunded amounts and offers immediate/end-cycle effective date. Suggest unused-term refund but owner controls amount; retain original base/tax/fee separately. Do not refund original processing fee. Membership itself is nontaxable under current business classification, so no routine membership-tax reversal. Applicable historical correction tax uses original transaction/rate, with owner exceptional audited override.
- One cancellation email may include refund if processed then. No later separate refund email; no fee-nonrefund sentence. Include remaining benefits through effective date when applicable.
- Staff ordinary sale/renew/add, payment-method updates, assistance/history and allowed obvious date/usage corrections; owner-only rules/prices/manual exceptions/refunds/complimentary/consolidation/nonpurchase benefit grants. Staff **may** perform in-person visit conversion.

## 6. In-person visit-to-membership conversion and customer credit

Owner/staff selects **Apply today's visit toward a membership purchase**, type, count, term, monthly/prepaid and start (default appointment date). No named-child selection. In-person controlled operation, not a customer post-visit self-service flow.

Recalculate eligible children/adult allowances, start benefits for appointment day, consume appropriate free visit (Unlimited uses day's benefit), retain original price/revisions and explanation. Distinguish funds already paid from amounts merely due:

- **Unpaid:** remove covered admissions and related tax, charge adjusted purchase. Do not credit money never collected.
- **Already paid:** reverse replaced admission and tax, apply actual payment plus associated reversed tax toward membership. Keep original processing fee nonrefundable; a further card charge has its own fee and owner may not waive that second fee. Treatment of tax on that retained original fee remains explicitly pending in [OPEN_DECISIONS.md](OPEN_DECISIONS.md).
- Excess is **customer credit**, usable for ordinary/supervised admission, clubs, socks, parties and gift-card purchases. If unused by next installment, apply then. Prepaid/no-next-installment credit remains until spent. Alert owner when membership expires with credit left. Owner may correct/remove credit with audit.
- Credit ledger is not a physical gift-card balance ledger. Preserve allocation/redemption history and prevent concurrent double spending.

| New purchase at visit, benefits available | Pretax amount before fee/tax |
|---|---:|
| 2 children +2 adults, buy 2 Subscription places monthly | **$35.98** |
| 3 children +2 adults, buy 2 Subscription places monthly (1 ordinary child remains) | **$50.98** |
| 5 children +2 adults, buy 2 Subscription places monthly (3 ordinary children remain) | **$80.98** |
| 3 children +3 adults, buy 1 Subscription place monthly | **$52.99** (17.99+30+5) |
| 2 children +2 adults, buy 2 Unlimited places monthly | **$79.98** |
| 2 children +2 adults, prepay 3 months for 2 Subscription places | **$107.94** |

These monthly examples are first installments under the three-month commitment, not one-month initial purchases. Fees/tax and online payment timing: [PAYMENTS.md](PAYMENTS.md). Never use the old unapproved $5.98 “credit for uncharged admission” example.
