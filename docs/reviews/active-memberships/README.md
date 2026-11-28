# Active memberships — review gallery

Draft [PR #37](https://github.com/MonkeyDo-Site/MonkeyDoWebsiteNewCode/pull/37). These are actual application pages with fictional review data, captured at 1440px desktop and 390px phone widths. All names, card references and payment outcomes are synthetic. No card was charged and no customer email was delivered.

Purchases, booking benefits, payment resolution and customer credit use the existing combined screens. Membership features and scheduled collection remain **off by default**, and PR #37 remains a draft while the remaining scope is implemented. Actual Banquest hosted fields and processor outcomes remain unverified; provider areas in samples 13, 68, 133 and 134 are explicitly labelled placeholders.

| Review area | Samples |
| --- | --- |
| Purchases, additions, renewals and cards | 01–03, 08–17, 67–72 |
| Bookings, arrival and owner exceptions | 04–07, 18–19, 40–42 |
| Cancellation and actual refunds | 20–25 |
| Customer credit and original funding | 26–32, 39, 44–45 |
| Search, exports and notices | 33–38, 43 |
| Membership purchase with arrival and recovery | 46–66 |
| Scheduled installment review | 73–74 |
| Physical gift card and an owner-comped visit | 75–76 |
| Customer review and reservation of a released Unlimited benefit | 77–78 |
| Split visit payments and a separate membership receipt | 79–80 |
| Separate membership Zelle during arrival | 81–82 |
| Customer credit on arrival and the private receipt | 83–85 |
| Credit with a partial cancellation fee | 86–87 |
| Split the membership first payment | [88–89](#88--split-the-membership-payment-on-the-same-purchase-page) |
| Received membership split during arrival | [90–91](#90--received-membership-split-and-visit-on-one-page) |
| Apply recorded booking Zelle to membership | [92–93](#92--assign-recorded-zelle-between-membership-and-visit) |
| Membership card remainder during arrival | [94–96](#94--split-membership-receipts-and-card-with-arrival) |
| Received visit funds while membership card is pending | [97–99](#97--received-visit-funds-with-a-pending-membership-card) |
| Record an unused visit-fund return and review the remaining payment | [100–102](#100--record-an-actual-unused-visit-fund-return) |
| Gift-card goods payment with a separate cancellation fee | [103–104](#103--gift-card-covers-goods-and-the-card-covers-the-cancellation-fee) |
| Stop a funded arrival while keeping the booking and membership | [105–106](#105--stop-an-arrival-and-keep-the-booking-and-membership) |
| Return unused visit funds while membership payment is unresolved | [107–108](#107--unused-visit-funds-with-an-unconfirmed-membership-payment) |
| Stop arrival after a recorded membership cancellation | [109–110](#109--stop-only-the-arrival-after-membership-cancellation) |
| Actual arrival funds and audited downloads | [111–112](#111--export-actual-arrival-funds-without-counting-applications-twice) |
| **New: buy a first membership using a paid visit** | **[113–116](#113--apply-a-paid-visit-toward-a-first-membership)** |
| **New: paid-visit purchase with received split payments** | **[117–118](#117--paid-visit-purchase-with-received-split-payments)** |
| **New: card remainder, uncertain result and safe owner stop** | **[119–124](#119--paid-visit-membership-with-a-card-remainder)** |
| **New: retry a known failed paid-visit card remainder** | **[125–128](#125--explicitly-request-the-card-remainder-again)** |
| **New: release original visit funds after membership cancellation** | **[129–132](#129--cancelled-membership-with-a-refund-still-due)** |
| **New: enter a card for the remaining first payment** | **[133–135](#133--enter-a-new-card-for-the-original-remainder)** |
| **New: record a received replacement payment on the same page** | **[136–138](#136--record-a-received-replacement-after-a-known-card-failure)** |
| **New: recorded bank details and paid-visit history download** | **[139–140](#139--recorded-bank-details-on-the-existing-payment-page)** |
| **New: paid early-renewal review and owner reminder** | **[141–142](#141--paid-early-renewal-with-an-earlier-payment-needing-review)** |
| **New: combined cash/check renewals and partial/type selection** | **[143–145](#143--renew-several-memberships-on-one-page)** |
| **New: find another renewal while keeping selected details** | **[146](#146--find-another-renewal-without-losing-selected-details)** |
| **New: one verified Zelle transfer across separate renewals** | **[147–149](#147--review-one-zelle-transfer-for-several-renewals)** |
| **New: correct unused membership dates on the same page** | **[150–152](#150--review-corrected-dates-without-another-page)** |
| **New: received portion plus an exact card remainder after failure** | **[153–156](#153--split-a-known-failed-remainder-on-the-same-page)** |

Each sample includes desktop and phone images. Start with the purchase, membership overview and booking/arrival examples above; the later samples cover specific payment and recovery cases. New samples **143–149** show combined cash/check/Zelle renewals, separate recorded allocations, split type/term choices and finding additional records while retaining selected details. Samples 147–149 show one shared bank transfer and its original receipt details. Samples 150–152 show date review, saved history under the same membership number and readable history while updates are paused. Samples 153–156 show a received portion with a smaller card remainder, preserved receipts during interruptions and the completed paid-visit application. See the [owner testing guide](../../ACTIVE_MEMBERSHIP_OWNER_TESTING.md) for expected results and the explicit unfinished scope.

## 01 — Purchase membership on one page

Customer, membership places, term, payment choice, amount due today, remaining installment dates, accepted agreement and final purchase action stay together. Two Subscription places billed monthly: $35.98 + $1.08 card processing fee = **$37.06 today**. Membership and its fee are not taxable. Changes require reviewing the current terms again. Owner exceptions stay collapsed.

| Desktop | Phone |
| --- | --- |
| [![Purchase membership, desktop](01-purchase-desktop.png)](01-purchase-desktop.png) | [![Purchase membership, phone](01-purchase-phone.png)](01-purchase-phone.png) |

## 02 — Active membership after confirmed payment

A successful simulated provider outcome records $37.06 received. The overview separates actual money from the next $37.06 installment. Membership dates, current month, saved card, included benefits and available/reserved/used counts are together; installment details and accepted history expand underneath. No automatic renewal beyond the purchased term.

| Desktop | Phone |
| --- | --- |
| [![Active membership overview, desktop](02-active-desktop.png)](02-active-desktop.png) | [![Active membership overview, phone](02-active-phone.png)](02-active-phone.png) |

## 03 — First payment not yet confirmed

One Subscription place: **$18.53 due**. No received funds or active benefits are claimed while the card outcome is pending. The payment record opens from the overview. This sample has not been submitted to Banquest.

| Desktop | Phone |
| --- | --- |
| [![Pending membership payment, desktop](03-pending-desktop.png)](03-pending-desktop.png) | [![Pending membership payment, phone](03-pending-phone.png)](03-pending-phone.png) |

## 04 — Member-aware booking on the existing combined page

Three children, two adults and one pair of socks; two Subscription places cover two children and both adults. One ordinary child admission remains: $15.00 + $1.99 socks + $0.51 card fee + $1.02 tax = **$18.52 at arrival**. Membership information sits above the existing attendee/price, waiver and card controls. Capacity counts, the 30-minute temporary reservation, session blocking, owner pricing and waiver-link choice remain visible. No member benefit is reserved by the unfinished draft itself.

The card setup shown here was simulated. Its configuration warning belongs to the isolated review environment and does not diagnose the deployed Banquest setup. No actual hosted card fields were verified.

| Desktop | Phone |
| --- | --- |
| [![Member booking, desktop](04-member-booking-desktop.png)](04-member-booking-desktop.png) | [![Member booking, phone](04-member-booking-phone.png)](04-member-booking-phone.png) |

## 05 — Edit member booking

The estimate includes member admissions before saving. A count or timing change recalculates the applicable membership month/day and atomically transfers reservations when saved. Current capacity controls remain in place.

| Desktop | Phone |
| --- | --- |
| [![Edit member booking, desktop](05-member-edit-desktop.png)](05-member-edit-desktop.png) | [![Edit member booking, phone](05-member-edit-phone.png)](05-member-edit-phone.png) |

## 06 — Member arrival

The existing combined arrival page shows two free member admissions, one ordinary admission and socks. Waiver coverage and the selected payment action are reviewed before the single final confirmation. Only confirmation records usage and requests payment.

| Desktop | Phone |
| --- | --- |
| [![Member arrival, desktop](06-member-arrival-desktop.png)](06-member-arrival-desktop.png) | [![Member arrival, phone](06-member-arrival-phone.png)](06-member-arrival-phone.png) |

## 07 — One fewer child arrives

Two member-covered children attend, along with two adults and one pair of socks. The revised total is **$5.14**: $1.99 socks + $3 cancellation fee + $0.15 card fee. The adjustment explains the original **$18.52**, the **$15 ordinary admission removed**, the fee/tax adjustments and the cancellation fee. No attendance or payment is recorded in these review captures.

| Desktop | Phone |
| --- | --- |
| [![Reduced member arrival, desktop](07-member-reduced-arrival-desktop.png)](07-member-reduced-arrival-desktop.png) | [![Reduced member arrival, phone](07-member-reduced-arrival-phone.png)](07-member-reduced-arrival-phone.png) |

## 08 — Renew existing places

Two Subscription places change to Unlimited after their original term ends. The qualifying one-month renewal starts **February 26**, with **$82.38 due today** including the card fee. The original membership keeps its dates, price and history. The start date is fixed by the original expiry; a partial renewal also leaves the unrenewed places available for a later explicit purchase. Pending card outcomes count toward renewed places so another click cannot sell them twice.

| Desktop | Phone |
| --- | --- |
| [![Renew membership, desktop](08-renewal-desktop.png)](08-renewal-desktop.png) | [![Renew membership, phone](08-renewal-phone.png)](08-renewal-phone.png) |

## 09 — Add places with their own term

One additional Unlimited place costs **$41.19 today**, with the two remaining installments visible. The new place has its own dates and payment schedule; the original two Subscription places keep theirs. The new three-month minimum and the accepted card authorization apply to this purchase. These captures stop before confirmation and do not request payment.

| Desktop | Phone |
| --- | --- |
| [![Add membership places, desktop](09-addition-desktop.png)](09-addition-desktop.png) | [![Add membership places, phone](09-addition-phone.png)](09-addition-phone.png) |

## 10 — Resolve a declined installment with cash

Two Subscription places have a declined **$37.06** card installment. The same overview shows the actual first **$35.98 received**, the overdue installment and its payment history. Opening the controls keeps the amount and final action together. Choosing cash previews **$35.98**, removing the uncharged **$1.08** card fee for this installment. The owner/staff verifies receipt before recording it. Changing the membership card is alongside this control and requests no charge by itself.

| Desktop | Phone |
| --- | --- |
| [![Record installment cash, desktop](10-installment-cash-desktop.png)](10-installment-cash-desktop.png) | [![Record installment cash, phone](10-installment-cash-phone.png)](10-installment-cash-phone.png) |

## 11 — Uncertain outcome blocks another collection

The first **$18.53** card outcome is unknown. Received funds remain **$0.00**, benefits stay pending and the previous payment record remains accessible. The payment controls explain that its outcome must be checked first. Another card charge or manual receipt is blocked even after changing the membership card. The collection button is visibly inactive.

| Desktop | Phone |
| --- | --- |
| [![Uncertain payment, desktop](11-uncertain-payment-desktop.png)](11-uncertain-payment-desktop.png) | [![Uncertain payment, phone](11-uncertain-payment-phone.png)](11-uncertain-payment-phone.png) |

## 12 — Installment resolved, benefits active again

The cash-only fictional browser scenario was completed once. **$71.96 total money received** represents two actual **$35.98** recorded cash payments. The failed card attempt remains in history and adds no received funds. Benefits are active again with **four free child visits available** this membership month; the next installment remains **$37.06** on its accepted date. The persistent payment notice clears. No successful-installment customer email is queued.

| Desktop | Phone |
| --- | --- |
| [![Installment paid, desktop](12-installment-paid-desktop.png)](12-installment-paid-desktop.png) | [![Installment paid, phone](12-installment-paid-phone.png)](12-installment-paid-phone.png) |

## 13 — New card on the combined membership purchase

Choose Enter a new card alongside the same membership, term and **$37.06 due today**. Staff records Yes/No for retaining it for unrelated future visits. **Confirm membership and charge card** securely saves the card first, then submits the explicit purchase once. Card storage and membership acceptance have their own evidence; no booking payment/cancellation consent is fabricated. The new source is restricted to this reviewed purchase unless future use was chosen.

**Provider limitation:** the pictured field area is explicitly labelled **synthetic browser test**. It verifies the surrounding page, nonce handoff and controls. It does not show or verify Banquest's real hosted-field rendering or processor behavior. The end-to-end scenario uses fake provider responses, creates one queued payment and leaves funds/benefits pending. A separate uncertain-save scenario reloads the page without another provider POST or membership purchase.

| Desktop | Phone |
| --- | --- |
| [![New membership card, desktop](13-new-membership-card-desktop.png)](13-new-membership-card-desktop.png) | [![New membership card, phone](13-new-membership-card-phone.png)](13-new-membership-card-phone.png) |

## 14 — Verify a private renewal link

An owner/staff-created private link asks for phone number and last name before showing membership details. No staff login or public customer search is exposed. The link lasts 30 days; each verified browser session lasts 20 minutes. Link validity does not extend the seven-day renewal grace rule. The pictured details are fictional, and no private link is published in this gallery.

| Desktop | Phone |
| --- | --- |
| [![Renewal verification, desktop](14-renewal-verification-desktop.png)](14-renewal-verification-desktop.png) | [![Renewal verification, phone](14-renewal-verification-phone.png)](14-renewal-verification-phone.png) |

## 15 — Customer renewal on one page

After verification, the customer reviews membership type, places, term, card, **$82.38 due today** and accepted terms together. Two Unlimited places start after the original Subscription term ends; the original dates and payment history stay intact. The final button explicitly requests the renewal and its card payment. The same form supports new secure-card entry; provider responses in this review are simulated.

| Desktop | Phone |
| --- | --- |
| [![Customer renewal, desktop](15-customer-renewal-desktop.png)](15-customer-renewal-desktop.png) | [![Customer renewal, phone](15-customer-renewal-phone.png)](15-customer-renewal-phone.png) |

## 16 — Renewal submitted, payment pending

The fictional browser confirmation creates exactly one customer-accepted renewal and one queued initial payment. **$0.00 received** and the pending message accurately describe that state; no active benefit or completed charge is claimed. Checking status reads the existing result. A second verified browser returns this same renewal instead of collecting again. A separate uncertain new-card save survives reload without another provider exchange or purchase.

| Desktop | Phone |
| --- | --- |
| [![Customer renewal pending, desktop](16-customer-renewal-pending-desktop.png)](16-customer-renewal-pending-desktop.png) | [![Customer renewal pending, phone](16-customer-renewal-pending-phone.png)](16-customer-renewal-pending-phone.png) |

## 17 — Replace a membership card on the overview

Staff can enter a replacement card alongside the existing payment details. The customer’s future-visit Yes/No choice is separate from authorization for the remaining accepted membership payments. **Save and use membership card** saves the source and updates its mandate once; it requests no payment or retry. The fictional confirmation preserves **$71.96 received**, the original installment dates and every earlier transaction’s card. Changing the billing details invalidates an older review.

The field area is visibly labelled **synthetic browser test**. A separate uncertain-save scenario verifies Check card setup and reload do not repeat the exchange or update the mandate. Real Banquest hosted-field rendering remains unverified.

| Desktop | Phone |
| --- | --- |
| [![Replace membership card, desktop](17-replacement-membership-card-desktop.png)](17-replacement-membership-card-desktop.png) | [![Replace membership card, phone](17-replacement-membership-card-phone.png)](17-replacement-membership-card-phone.png) |

## 18 — Honor reserved benefits for one overdue booking

The owner reviews the existing counts, selects **Honor reserved membership benefits for this booking**, and records a readable reason on the same arrival page. Two child admissions remain covered and **$0.00 is due for this visit**. The membership installment is still unpaid; this is an exception for the reviewed booking/session, preserving normal quota and cancellation-fee rules. It does not grant benefits to other bookings or extend the membership term.

The fictional phone scenario confirms arrival with the first click after typing the reason, records two used benefits and creates no payment operation. Waivers and capacity checks remain in place. The earlier reservation history is retained.

| Desktop | Phone |
| --- | --- |
| [![Owner honors reserved benefits, desktop](18-owner-honor-benefits-desktop.png)](18-owner-honor-benefits-desktop.png) | [![Owner honors reserved benefits, phone](18-owner-honor-benefits-phone.png)](18-owner-honor-benefits-phone.png) |

## 19 — Choose ordinary prices before arrival

On Edit booking, the owner chooses ordinary admission prices and records a reason. Two children cost **$30.00 + $1.98 tax = $31.98**, with cash selected and no card fee. The adjustment explains the change from the saved **$0.00** member price. Ordinary pricing continues to recalculate when counts change. The existing visible capacity, session-blocking and navigation controls stay on the page.

The fictional phone scenario saves this edit and releases the reserved benefits. It collects no money and leaves membership dues unpaid. Save changes and Cancel stay together on the phone layout. These controls are limited to the owner and affected bookings.

| Desktop | Phone |
| --- | --- |
| [![Owner selects ordinary prices, desktop](19-owner-ordinary-pricing-desktop.png)](19-owner-ordinary-pricing-desktop.png) | [![Owner selects ordinary prices, phone](19-owner-ordinary-pricing-phone.png)](19-owner-ordinary-pricing-phone.png) |

## 20 — Cancel membership on the existing overview

Two prepaid Subscription places originally cost **$215.88** for six months. The owner selects the end of the current membership month, **December 13**, and reviews a suggested **$71.96** unused-period refund. The owner controls the refund amount and explicitly chooses whether to send a cancellation email. Original funds, payment sources, dates and the final action stay together. Initial-commitment cancellation shows an additional owner approval only when needed.

The fictional phone scenario confirms cancellation once and records **refund due**, without claiming any return or requesting a card transaction. Opening or changing the review creates no cancellation. Earlier dues and existing bookings remain separate.

| Desktop | Phone |
| --- | --- |
| [![Owner cancellation review, desktop](20-owner-cancellation-review-desktop.png)](20-owner-cancellation-review-desktop.png) | [![Owner cancellation review, phone](20-owner-cancellation-review-phone.png)](20-owner-cancellation-review-phone.png) |

## 21 — Refund due is separate from money actually returned

After cancellation is recorded, **$71.96 remains due and $0.00 has been returned**. The original receipt remains **$215.88**. Benefits remain available until the selected end when required dues are paid. The owner can record a completed cash return directly here, including a partial amount; the screen requires confirmation that the money was actually returned.

| Desktop | Phone |
| --- | --- |
| [![Refund due, desktop](21-refund-due-desktop.png)](21-refund-due-desktop.png) | [![Refund due, phone](21-refund-due-phone.png)](21-refund-due-phone.png) |

## 22 — Partial refund, with actual totals

The fictional owner records **$20.00 actually returned in cash**. The overview shows **$215.88 originally received**, **$20.00 in recorded refunds**, and **$195.88 held after refunds**. The approved refund is still **$71.96**, so **$51.96 remains due**. The original purchase and payment evidence remain in history. Recording a return creates no new receipt and no separate later refund email.

| Desktop | Phone |
| --- | --- |
| [![Partial refund recorded, desktop](22-partial-refund-recorded-desktop.png)](22-partial-refund-recorded-desktop.png) | [![Partial refund recorded, phone](22-partial-refund-recorded-phone.png)](22-partial-refund-recorded-phone.png) |

## 23 — Persistent owner Dashboard reminder

The **$51.96** remaining refund links back to the membership. A partial return keeps the reminder; confirmed completion clears it. Bookings whose reserved membership benefits end before their session have a separate review reminder. Cancellation neither cancels those bookings nor silently changes their saved prices.

| Desktop | Phone |
| --- | --- |
| [![Refund Dashboard reminder, desktop](23-refund-dashboard-desktop.png)](23-refund-dashboard-desktop.png) | [![Refund Dashboard reminder, phone](23-refund-dashboard-phone.png)](23-refund-dashboard-phone.png) |

## 24 — Requested card refund is still pending

The owner explicitly requests a **$50.00** refund against the original Visa ending **4242**. The screen shows **$0.00 returned and $50.00 still due** until a successful provider outcome is recorded. The original card processing fee is excluded. A pending or uncertain refund blocks another attempt; no automatic retry is made.

This fictional review queues work only. No worker sent the refund to Banquest, and no external funds moved. Gateway behavior is developer-tested using simulated responses; real processor refund verification remains outstanding.

| Desktop | Phone |
| --- | --- |
| [![Card refund pending, desktop](24-card-refund-pending-desktop.png)](24-card-refund-pending-desktop.png) | [![Card refund pending, phone](24-card-refund-pending-phone.png)](24-card-refund-pending-phone.png) |

## 25 — Record a card refund already completed in Banquest

Synthetic provider evidence reports a **$5.00** external return. The unstarted outgoing refund stops before any provider POST. The owner enters the completed refund reference and confirms it was already returned. **Verify and record completed Banquest refund — $5.00** reads and verifies the existing provider transaction; it sends no new refund. The reference must match the original payment, exact amount and successful refund outcome. Partial imports leave the rest due, and the same provider refund cannot be recorded twice.

These captures stop before verification, using a fictional reference. Developer tests exercise verified import with mock GET responses and assert no refund/void POST. Actual Banquest verification has not been performed. A whole-provider void that includes retained fees needs separate owner correction review; this action does not substitute a void for a net-only refund.

| Desktop | Phone |
| --- | --- |
| [![Record completed Banquest refund, desktop](25-record-completed-card-refund-desktop.png)](25-record-completed-card-refund-desktop.png) | [![Record completed Banquest refund, phone](25-record-completed-card-refund-phone.png)](25-record-completed-card-refund-phone.png) |

## 26 — Apply existing customer credit on the membership overview

An unused **$16.02** credit can cover part of a **$17.99** Subscription installment. The same page shows the amount to apply, **$1.97** of membership principal remaining, and **$0.06** in processing fee if that remainder is paid by card: **$2.03**. Changing the credit amount refreshes the review. Only **Apply customer credit — $16.02** spends it; this action collects no money and sends no card charge.

The fictional member already paid **$17.99 cash** for the first membership month. A separate fully paid same-day card visit was reconciled against that same-day purchase, creating credit from the replaced admission. This sample shows that unused credit in the later installment month. The combined purchase-and-conversion checkout and automatic installment producer are still being built; this is an explicit staff application of already recorded funds.

| Desktop | Phone |
| --- | --- |
| [![Customer credit review, desktop](26-customer-credit-review-desktop.png)](26-customer-credit-review-desktop.png) | [![Customer credit review, phone](26-customer-credit-review-phone.png)](26-customer-credit-review-phone.png) |

## 27 — Credit applied, with the remaining balance still clear

After one fictional confirmation, **$16.02 customer credit applied** is separate from **$17.99 actual money received**. **$2.03 remains due** if paid by card. No second payment was recorded and no payment job was created by applying the credit. The membership remains overdue until its remaining balance is settled. Existing payment controls handle that remainder; the credit does not become another cash receipt.

Developer tests cover full and partial use, exact remaining fees, duplicate confirmations, stale reviews, uncertain payments, and simultaneous spending. Reported source returns hold unspent credit and pause affected funded benefits/collection for owner review, preserving receipts and saved booking prices. Applying credit stops an unstarted request for the old full charge; it cannot race a dispatch that has already started. Returning applied credit during membership cancellation remains a separate unfinished flow, so cancellation of such a term is currently blocked for credit-return review.

| Desktop | Phone |
| --- | --- |
| [![Customer credit applied, desktop](27-customer-credit-applied-desktop.png)](27-customer-credit-applied-desktop.png) | [![Customer credit applied, phone](27-customer-credit-applied-phone.png)](27-customer-credit-applied-phone.png) |

## 28 — Original visit funds and the accountant's card example

The original card receipt is **$16.47**: $15 admission, $0.45 fee and $1.02 combined tax. Reconciliation reverses the replaced admission, its $0.99 tax and the $0.03 tax on the retained fee, making **$16.02 customer credit**. The original **$0.45 processing fee remains**. The booking shows the original receipt and transfer separately, the admission covered by membership, and the exact price adjustment. It records normal benefit usage and preserves original waivers, prices, receipt and tax components.

This source was prepared through the trusted reconciliation service using fictional confirmed funds. It demonstrates reconciliation against an already paid same-day membership. It does not show the still-unfinished combined first-purchase checkout or claim a real Banquest transaction/refund. Unpaid visits create no credit, and the same original funds cannot also be refunded.

| Desktop | Phone |
| --- | --- |
| [![Converted visit funds, desktop](28-converted-visit-funds-desktop.png)](28-converted-visit-funds-desktop.png) | [![Converted visit funds, phone](28-converted-visit-funds-phone.png)](28-converted-visit-funds-phone.png) |

## 29 — Customer credit balance and recent history

The customer page keeps issued/applied credit history and links to the source booking and target membership. After the **$16.02** is used, **$0.00 is available**, with both entries retained. Credit is neither a physical gift-card balance nor new money received. Unspent credit carries beyond membership expiry; a persistent owner reminder identifies credit left from an ended term and clears when spent.

| Desktop | Phone |
| --- | --- |
| [![Customer credit history, desktop](29-customer-credit-history-desktop.png)](29-customer-credit-history-desktop.png) | [![Customer credit history, phone](29-customer-credit-history-phone.png)](29-customer-credit-history-phone.png) |

## 30 — Owner correction with the resulting balance visible

On the existing customer page, expand **Owner: correct unused credit**. This fictional customer has **$16.02** available. Removing **$5.00** leaves **$11.02**. The amount, reason, before/after balances and one final action stay together. Review creates no correction; the owner must confirm. Staff cannot perform this action, and used or source-held credit cannot be removed.

| Desktop | Phone |
| --- | --- |
| [![Owner credit removal review, desktop](30-owner-credit-removal-review-desktop.png)](30-owner-credit-removal-review-desktop.png) | [![Owner credit removal review, phone](30-owner-credit-removal-review-phone.png)](30-owner-credit-removal-review-phone.png) |

## 31 — Removed credit retained in the customer history

After confirmation, **$11.02** is available. The expandable history keeps the owner, time, amount and reason; the full customer history remains accessible. The original **$16.47** card receipt and **$16.02** credit issue remain unchanged. Removing unused credit neither returns money nor changes an already applied amount.

| Desktop | Phone |
| --- | --- |
| [![Owner credit correction history, desktop](31-owner-credit-correction-history-desktop.png)](31-owner-credit-correction-history-desktop.png) | [![Owner credit correction history, phone](31-owner-credit-correction-history-phone.png)](31-owner-credit-correction-history-phone.png) |

## 32 — Restore only a specific earlier removal

The owner chooses the earlier **$5.00** removal and reviews restoring **$2.00**, leaving **$13.02** available. Restoration cannot exceed the amount still unrestored from that specific removal or create additional unsupported credit. If the original source later needs payment review, restored funds remain held; they do not become spendable. A second explicit confirmation records the restoration with its own reason and history.

Both fictional actions were completed in browser checks. No external payment, refund or email was sent.

| Desktop | Phone |
| --- | --- |
| [![Owner credit restoration review, desktop](32-owner-credit-restoration-review-desktop.png)](32-owner-credit-restoration-review-desktop.png) | [![Owner credit restoration review, phone](32-owner-credit-restoration-review-phone.png)](32-owner-credit-restoration-review-phone.png) |

## 33 — Membership search, status and expiry together

The membership list keeps all history available by default, with one compact filter area for customer/M-number search, type, actual payment status and expiry. Phone/email matching and labelled possible name matches reuse the existing staff search rules. Type/status/date changes apply immediately; text search uses Enter or Apply filters. Clear expiry preserves the other choices. Existing row-size and page navigation remain.

The fictional rows include active, future and overdue memberships. Status filtering uses actual receipts, adjusted obligations and applied credit, with source-held credit shown for review; a saved card or accepted purchase alone is not payment. Scheduled cancellation uses the effective last benefit day while preserving the original end date.

CSV downloads stay collapsed on the same page. Owners have access; staff need an explicitly assigned export permission, plus payment/booking viewing rights for the corresponding report. That export permission is not selected for new staff by default. The staff editor now also preserves normal membership sale/view/update permissions that were already available through the default staff group.

| Desktop | Phone |
| --- | --- |
| [![Membership filters and exports, desktop](33-membership-list-and-exports-desktop.png)](33-membership-list-and-exports-desktop.png) | [![Membership filters and exports, phone](33-membership-list-and-exports-phone.png)](33-membership-list-and-exports-phone.png) |

## 34 — Expiring memberships and a matching CSV

**Active + Next 5 days** narrows the list to the fictional complimentary membership ending **November 30**. The same filters apply to every exported row across all result pages. The downloaded [fictional sample CSV](34-expiring-memberships-sample.csv) contains that single membership; pagination does not limit the export.

The available operational reports are membership details, payment transactions and benefit history. Payment requests retain their outcome and requested amount separately from successfully recorded principal, fee and taxes, with distinct service, manual-receipt, completion and reported settlement dates. Credit applications create no incoming-money row. Benefit history includes each reserved/used/released event alongside its current state. Sensitive card-storage references, signed waivers and staff comments are excluded. These are operational CSVs; final accountant-report presentation remains separate.

| Desktop | Phone |
| --- | --- |
| [![Expiring memberships, desktop](34-expiring-memberships-desktop.png)](34-expiring-memberships-desktop.png) | [![Expiring memberships, phone](34-expiring-memberships-phone.png)](34-expiring-memberships-phone.png) |

## 35 — Owner export history

Each prepared CSV records its report, exact row count, filters, staff member and New York time. The owner can page through all export history; ordinary staff cannot open this history even when permitted to export. CSV preparation is recorded before returning the download, and untrusted spreadsheet text is protected from formula interpretation. No additional owner password prompt is introduced.

Desktop and phone browser checks actually changed filters and downloaded/read the one-row fictional CSV. No membership, benefit reservation or payment was changed by filtering or exporting.

| Desktop | Phone |
| --- | --- |
| [![Membership export history, desktop](35-membership-export-history-desktop.png)](35-membership-export-history-desktop.png) | [![Membership export history, phone](35-membership-export-history-phone.png)](35-membership-export-history-phone.png) |

## 36 — Five days before expiry

The approved expiry wording uses the actual cohort's remaining unrenewed places and end date. The branded **Renew membership** button opens the protected renewal link. It creates no renewal or charge. The owner-removed lapse sentence stays out of this email; the underlying gap/eligibility rule remains.

This fictional snapshot is dated **November 25**, five days before the **November 30** end date. It was rendered from the queued immutable message; no email was sent. The original logo and previously reviewed email design are retained.

| Desktop | Phone |
| --- | --- |
| [![Five-day expiry email, desktop](36-expiry-email-desktop.png)](36-expiry-email-desktop.png) | [![Five-day expiry email, phone](36-expiry-email-phone.png)](36-expiry-email-phone.png) |

## 37 — One day before the seven-day grace window ends

This fictional cohort ended **November 19**. Its approved notice is due **November 25**, saying the renewal window ends tomorrow, **November 26**. The renewed term starts on the actual renewal date. The link lasts 30 days, while a renewal after the seven-day window normally requires three months; link lifetime does not extend grace or restore benefits during the gap.

Desktop/phone browser checks opened this system-created link without a staff session, confirmed that it revealed no customer details before phone/name verification, and reached the one-month grace renewal selection after matching those details. No card was entered or payment requested.

| Desktop | Phone |
| --- | --- |
| [![Grace-period email, desktop](37-grace-email-desktop.png)](37-grace-email-desktop.png) | [![Grace-period email, phone](37-grace-email-phone.png)](37-grace-email-phone.png) |

## 38 — Notice dates and actual history on the membership overview

The existing overview keeps an expandable **Renewal notices** section with the due dates and actual queued/sent/withdrawn history. Viewing it creates no message. Automated notices have scoped system evidence, with no fake staff attribution. Private verification and explicit customer acceptance still authorize any later purchase.

The bounded producer prepares only the approved due-day notices. It rechecks payment review, current contact, remaining places, cancellation and link validity before dispatch. A partial renewal/contact correction supersedes only an unsent snapshot; full renewal, cancellation or a stale notice day withdraws it. Sent, unknown or failed delivery is not automatically repeated. A known unrecorded original card return also suppresses notice sending. The two approved emails add no appointment reminders or customer failed-installment emails.

| Desktop | Phone |
| --- | --- |
| [![Renewal-notice history, desktop](38-renewal-notice-history-desktop.png)](38-renewal-notice-history-desktop.png) | [![Renewal-notice history, phone](38-renewal-notice-history-phone.png)](38-renewal-notice-history-phone.png) |

## 39 — Membership payment needs reconciliation

A fictional prepaid membership has **$111.18 in recorded receipts** and a reported **$1 external card return** that has not yet been recorded as a completed refund. The overview shows **Review**, unavailable benefits and the original receipt together. Renewal and further collection wait for owner reconciliation; no zero-dollar collection or paid-in-full claim appears. Existing booking prices and benefit history stay intact.

A return reported after a later charge was queued also stops that charge before any financial provider request. Recording the actual return clears the reconciliation hold, but any resulting unpaid installment still needs resolution. These screenshots use local synthetic evidence; they do not verify a live Banquest return.

| Desktop | Phone |
| --- | --- |
| [![Membership funding review, desktop](39-membership-funding-review-desktop.png)](39-membership-funding-review-desktop.png) | [![Membership funding review, phone](39-membership-funding-review-phone.png)](39-membership-funding-review-phone.png) |

## 40 — Owner booking with inline renewal choices

**Renew**, **Not now** and **Email me later** appear beside the customer's existing membership summary. The existing attendee estimate, visible capacity counts, 30-minute temporary reservation, closure/override controls, custom price, waivers, card and final booking button stay on the same page.

Renew opens the existing combined renewal form in another tab. Actual browser checks return to the original page with **2 children and 1 pair of socks preserved**, and the same hold expiry. Opening renewal or choosing a reminder confirms no booking and makes no membership purchase. The card-configuration warning belongs to this isolated review environment; it does not describe the deployed provider setup.

| Desktop | Phone |
| --- | --- |
| [![Owner booking renewal choices, desktop](40-booking-renewal-owner-desktop.png)](40-booking-renewal-owner-desktop.png) | [![Owner booking renewal choices, phone](40-booking-renewal-owner-phone.png)](40-booking-renewal-owner-phone.png) |

## 41 — Customer booking near membership expiry

The same optional choices appear within five days of the cohort's expiry. **Not now** does not interrupt booking. That response is remembered across bookings; one further prompt may appear on a later booking at least 30 days after expiry. Displaying a prompt and choosing an action are separate immutable facts. Merely loading a page records neither; the visible prompt is acknowledged by a CSRF-protected request.

A customer who chooses Renew still verifies phone and name on the private renewal page before accessing its checkout. The booking profile proof does not authorize a financial action. The customer booking's existing 20-minute limit stays in place.

| Desktop | Phone |
| --- | --- |
| [![Customer booking renewal choices, desktop](41-booking-renewal-customer-desktop.png)](41-booking-renewal-customer-desktop.png) | [![Customer booking renewal choices, phone](41-booking-renewal-customer-phone.png)](41-booking-renewal-customer-phone.png) |

## 42 — Expired membership and a requested reminder

This fictional membership ended **November 15**, and the review booking is on **November 25**. The page correctly shows a **new three-month minimum**. Email me later requests the next morning, **November 26 at 9 a.m. New York time**, and explains that the reminder does not preserve the shorter renewal minimum. No past expiry-relative reminder date is offered.

The actual phone interaction requests the reminder while leaving the entered counts and socks intact. No visit is confirmed. If an existing profile has no saved email yet, only the validated pending booking email can enable the choice, with an instruction to finish booking; delivery uses the actual saved contact, never an uncommitted address.

| Desktop | Phone |
| --- | --- |
| [![Expired membership renewal choice, desktop](42-booking-expired-renewal-desktop.png)](42-booking-expired-renewal-desktop.png) | [![Expired membership renewal choice, phone](42-booking-expired-renewal-phone.png)](42-booking-expired-renewal-phone.png) |

## 43 — Requested renewal email, prepared the following morning

This is the actual frozen email queued from sample 42's request at the following fictional morning, **November 26, 9 a.m. New York time**. It uses appropriate past/future wording and the current three-month minimum, with the protected **Renew membership** button. It was prepared locally and **not sent**.

The private link lasts 30 days from its creation and does not extend the seven-day renewal deadline. Remaining places, payments, cancellation, current contact and link validity are checked again before delivery. Obsolete messages are withdrawn; changed content has a new immutable snapshot. An unknown or failed delivery is not automatically repeated. An isolated reminder-preparation failure does not stop unrelated accepted jobs.

| Desktop | Phone |
| --- | --- |
| [![Requested renewal email, desktop](43-requested-renewal-email-desktop.png)](43-requested-renewal-email-desktop.png) | [![Requested renewal email, phone](43-requested-renewal-email-phone.png)](43-requested-renewal-email-phone.png) |

## 44 — Apply existing credit during the initial purchase

The existing combined purchase form now shows available customer credit and a **Use available credit** action. This fictional three-month prepaid Subscription costs **$53.97**. Applying **$13.02** leaves **$40.95 cash due**, with no card fee. The price, credit, remaining payment, receipt confirmation and accepted terms stay on one page. This is use of existing backed credit; it is separate from the still-unfinished combined visit-conversion checkout.

Card-funded balances receive their own fee only on remaining principal. Application tests cover **$17.99 − $16.02 credit = $1.97**, plus **$0.06**, for a **$2.03** new card request. Later monthly installment prices/dates stay unchanged. A credit-funded first month still needs its accepted future card mandate; a fully credit-funded prepaid term needs no card or zero-dollar receipt.

| Desktop | Phone |
| --- | --- |
| [![Initial purchase using credit, desktop](44-initial-credit-purchase-desktop.png)](44-initial-credit-purchase-desktop.png) | [![Initial purchase using credit, phone](44-initial-credit-purchase-phone.png)](44-initial-credit-purchase-phone.png) |

## 45 — Confirmed purchase keeps credit separate from new money

The actual local browser checkout confirms **$40.95 cash received** and applies **$13.02 existing credit**. The resulting membership is active and prepaid. Its overview shows those amounts separately, rather than claiming another $53.97 receipt. No card or external financial action was involved, and the confirmation email remains queued without delivery.

Changed credit sources, price/terms or card authorization require review before purchase. Concurrent owner credit correction cannot spend the same funds or deadlock a purchase; that is checked with actual PostgreSQL sessions. Unknown card outcomes still wait for reconciliation, and ordinary retries require explicit confirmation. Public private-renewal checkout does not accept unscoped credit input.

| Desktop | Phone |
| --- | --- |
| [![Initial credit-funded purchase confirmed, desktop](45-initial-credit-paid-desktop.png)](45-initial-credit-paid-desktop.png) | [![Initial credit-funded purchase confirmed, phone](45-initial-credit-paid-phone.png)](45-initial-credit-paid-phone.png) |

## 46 — Buy a membership and complete arrival together

Three children and two adults arrive without paying admission first. The same page selects two Subscription places, three monthly installments and the accepted future card. Two child admissions and both adults become included. **$35.98 membership + $15.99 adjusted visit = $51.97 cash received today.** The final button records both purchases together; previewing creates no membership, receipt or benefit usage. Existing count, capacity, waiver, paper-waiver and payment controls remain. The credit-funded and positive-first-payment card variants are shown below. Paid-visit first-purchase conversion remains in progress.

| Desktop | Phone |
| --- | --- |
| [![Combined membership purchase and arrival, desktop](46-combined-membership-arrival-desktop.png)](46-combined-membership-arrival-desktop.png) | [![Combined membership purchase and arrival, phone](46-combined-membership-arrival-phone.png)](46-combined-membership-arrival-phone.png) |

## 47 — Completed visit links to its new membership

The visit shows its own **$15.99 received**, with the new membership linked immediately underneath. The combined confirmation records **$51.97 new money**, separated into $35.98 membership and $15.99 visit. Membership adult allowances are labelled as benefit adjustments, without claiming adults cancelled. Existing booking history and the earlier booking-confirmation record remain intact.

| Desktop | Phone |
| --- | --- |
| [![Completed combined purchase, desktop](47-combined-membership-completed-desktop.png)](47-combined-membership-completed-desktop.png) | [![Completed combined purchase, phone](47-combined-membership-completed-phone.png)](47-combined-membership-completed-phone.png) |

## 48 — One combined membership and visit email

The actual queued fictional confirmation presents the visit, membership, benefit usage, itemized amounts received and next scheduled installment together. There is no Book a visit button for an already booked visit. A normal membership-only email is suppressed only for an accepted combined purchase with its protected pending intent or completed arrival; the combined paid email waits for confirmed funds. This email remains unsent. Earlier Zelle and existing credit, when used, are shown separately from new money; confirmed coverage avoids an unnecessary waiver section.

| Desktop | Phone |
| --- | --- |
| [![Combined membership and visit email, desktop](48-combined-membership-email-desktop.png)](48-combined-membership-email-desktop.png) | [![Combined membership and visit email, phone](48-combined-membership-email-phone.png)](48-combined-membership-email-phone.png) |

## 49 — Existing credit pays membership; card pays the remaining visit

Two children and two adults attend. The first membership month is fully funded by **$17.99 of existing, ledger-backed customer credit**. One child admission remains: **$15.00 + $0.45 card fee + $1.02 tax = $16.47**. One final action purchases the membership and requests only that visit charge. The future monthly card mandate stays explicit. No cash-received acknowledgment or zero-dollar membership card charge is created. A positive first membership card payment is now shown in samples 53–56.

| Desktop | Phone |
| --- | --- |
| [![Credit-funded membership and visit card, desktop](49-credit-membership-card-visit-desktop.png)](49-credit-membership-card-visit-desktop.png) | [![Credit-funded membership and visit card, phone](49-credit-membership-card-visit-phone.png)](49-credit-membership-card-visit-phone.png) |

## 50 — Uncertain visit-card result

The simulated response is uncertain: **$0.00 new money is confirmed**, with **$16.47 requiring review**. The membership's $17.99 credit stays separately recorded. No paid combined confirmation is queued, no replacement collection is allowed, and dispatch cannot repeat the same financial POST. The ordinary booking confirmation in history predates arrival; it is not a receipt.

| Desktop | Phone |
| --- | --- |
| [![Uncertain combined visit-card payment, desktop](50-credit-card-uncertain-desktop.png)](50-credit-card-uncertain-desktop.png) | [![Uncertain combined visit-card payment, phone](50-credit-card-uncertain-phone.png)](50-credit-card-uncertain-phone.png) |

## 51 — Reconciled payment, without another charge

A mocked provider GET confirms the original transaction. The visit now shows **$16.47 received** and links the membership purchased with credit. Applying $17.99 credit is never counted as new money. This is a local simulated provider result; no actual Banquest financial POST occurred. Superseded unsent message snapshots remain in history; only the current queued version can be sent.

| Desktop | Phone |
| --- | --- |
| [![Reconciled combined visit payment, desktop](51-credit-card-confirmed-desktop.png)](51-credit-card-confirmed-desktop.png) | [![Reconciled combined visit payment, phone](51-credit-card-confirmed-phone.png)](51-credit-card-confirmed-phone.png) |

## 52 — Combined credit/card confirmation

The actual queued, unsent email separates the $17.99 applied credit, $0.00 newly received for membership and $16.47 newly received for the visit. It includes the actual next scheduled installment. Current payment/contact changes supersede an unattempted stale email; attempted or unknown delivery never automatically sends another confirmation.

| Desktop | Phone |
| --- | --- |
| [![Credit and visit-card combined email, desktop](52-credit-card-combined-email-desktop.png)](52-credit-card-combined-email-desktop.png) | [![Credit and visit-card combined email, phone](52-credit-card-combined-email-phone.png)](52-credit-card-combined-email-phone.png) |

## 53 — Review both card payments on the existing arrival page

Three children and two adults attend with two new Subscription places. The first membership month is **$35.98 + $1.08 card fee = $37.06**. The remaining visit is **$15.00 + $0.45 fee + $1.02 tax = $16.47**. The page identifies both cards and the **$53.53 total** before its one final action. Only the membership payment is initially requested; no unpaid membership benefits are used.

| Desktop | Phone |
| --- | --- |
| [![Both card payments reviewed, desktop](53-membership-first-card-review-desktop.png)](53-membership-first-card-review-desktop.png) | [![Both card payments reviewed, phone](53-membership-first-card-review-phone.png)](53-membership-first-card-review-phone.png) |

## 54 — Uncertain first payment preserves the reviewed visit

The same arrival URL shows the saved review, **$0.00 membership payment received**, **$37.06 balance**, and that the visit charge has not been requested. Checking status is read-only and cannot retry a card or extend the reservation. The original booking retains its places; extra attendees have a fixed 30-minute reservation. A paid membership and current, unchanged visit are required before continuation. Expired or changed details stop for owner review. Once membership funding is confirmed, the fresh owner review in samples 57–60 can complete the current visit.

| Desktop | Phone |
| --- | --- |
| [![Uncertain first membership payment, desktop](54-membership-first-uncertain-desktop.png)](54-membership-first-uncertain-desktop.png) | [![Uncertain first membership payment, phone](54-membership-first-uncertain-phone.png)](54-membership-first-uncertain-phone.png) |

## 55 — Confirmed funding completes the dependent visit once

GET-only simulated reconciliation confirms the original **$37.06** membership receipt. A separate worker transaction rechecks the accepted visit, capacity, waivers, actor, prices and payment source before requesting its **$16.47** charge. After both fictional approvals, the booking shows **$53.53 new payment received**, split into membership and visit. Replaying acceptance or overlapping completion cannot create another purchase, benefit use or visit charge. A first decline can instead be repaired by an explicit verified payment; the original purchase is retained.

| Desktop | Phone |
| --- | --- |
| [![Membership-first arrival completed, desktop](55-membership-first-completed-desktop.png)](55-membership-first-completed-desktop.png) | [![Membership-first arrival completed, phone](55-membership-first-completed-phone.png)](55-membership-first-completed-phone.png) |

## 56 — One confirmation includes both actual card fees

The actual queued fictional email separates **$35.98 membership principal**, visit items, **$1.53 combined processing fees**, **$1.02 sales tax**, and **$53.53 received**. Its future monthly schedule remains distinct. No paid confirmation was prepared during uncertainty or before the dependent visit payment succeeded. This email remains unsent; all provider results were simulated locally.

| Desktop | Phone |
| --- | --- |
| [![Membership-first combined email, desktop](56-membership-first-combined-email-desktop.png)](56-membership-first-combined-email-desktop.png) | [![Membership-first combined email, phone](56-membership-first-combined-email-phone.png)](56-membership-first-combined-email-phone.png) |

## 57 — Expired reservation keeps the actual membership receipt

The first membership payment is confirmed, but the original extra-attendee reservation has expired after 30 minutes. The status shows **$37.06 received**, **$0.00 membership balance**, and no visit charge. The owner can choose **Review current arrival**. Opening or checking the status does not renew the reservation, request a payment or buy another membership.

| Desktop | Phone |
| --- | --- |
| [![Expired arrival with confirmed membership funds, desktop](57-expired-arrival-review-desktop.png)](57-expired-arrival-review-desktop.png) | [![Expired arrival with confirmed membership funds, phone](57-expired-arrival-review-phone.png)](57-expired-arrival-review-phone.png) |

## 58 — Current owner review on the existing arrival page

Starting this explicit owner action pauses the earlier automatic continuation. The same combined arrival page shows the paid membership and dates, current attendee counts, reason, active/paper waivers, price adjustments and payment choice. Two children now attend: both membership admissions are included, and the existing **$3.00 partial cancellation fee + $0.09 card fee = $3.09** remains clearly itemized. The final button approves only this remaining visit payment. Card/waiver returns retain this private draft; the owner rechecks current capacity and coverage.

| Desktop | Phone |
| --- | --- |
| [![Fresh current arrival review, desktop](58-owner-current-arrival-review-desktop.png)](58-owner-current-arrival-review-desktop.png) | [![Fresh current arrival review, phone](58-owner-current-arrival-review-phone.png)](58-owner-current-arrival-review-phone.png) |

## 59 — Re-reviewed arrival retains both payment records

After the synthetic visit approval, the booking shows the revised two-child visit, **$3.09 visit payment**, and **$40.15 combined new money**, including the original **$37.06 membership receipt**. There is still one membership purchase. The new immutable owner approval identifies its current actor, reason, checkout and request; the original accepted intent, actor, terms and receipt remain intact. Change history shows who approved the re-review and why. Competing owners and an old waiting worker cannot create a second visit payment.

| Desktop | Phone |
| --- | --- |
| [![Owner-approved revised arrival, desktop](59-owner-reviewed-arrival-completed-desktop.png)](59-owner-reviewed-arrival-completed-desktop.png) | [![Owner-approved revised arrival, phone](59-owner-reviewed-arrival-completed-phone.png)](59-owner-reviewed-arrival-completed-phone.png) |

## 60 — Accurate confirmation after owner recovery

The actual unsent confirmation reflects the current two-child visit, unchanged purchased membership, **$3.00 cancellation fee**, **$1.17 total processing fees**, **$0.00 visit tax**, and **$40.15 received**. The earlier $37.06 is counted once. No paid email was prepared before the visit result was confirmed. All records/provider outcomes in this example are fictional; nothing was charged or delivered externally.

| Desktop | Phone |
| --- | --- |
| [![Owner-reviewed combined confirmation, desktop](60-owner-reviewed-combined-email-desktop.png)](60-owner-reviewed-combined-email-desktop.png) | [![Owner-reviewed combined confirmation, phone](60-owner-reviewed-combined-email-phone.png)](60-owner-reviewed-combined-email-phone.png) |

## 61 — Enter a new membership card on the arrival page

The membership card selector now offers **Enter a new card** alongside available saved cards. The same page retains counts, waivers, the adjusted visit price and final confirmation. Staff records the customer's explicit future-visit Yes/No choice. **No — membership payments only** keeps this card for the accepted membership obligations without replacing the customer's future-visit preference. The hosted inputs here are **visibly labelled provider test doubles**; this screenshot does not verify Banquest's actual field layout.

| Desktop | Phone |
| --- | --- |
| [![New membership card during arrival, desktop](61-arrival-new-membership-card-desktop.png)](61-arrival-new-membership-card-desktop.png) | [![New membership card during arrival, phone](61-arrival-new-membership-card-phone.png)](61-arrival-new-membership-card-phone.png) |

## 62 — Uncertain card storage preserves the entered visit

One synthetic card-storage exchange has an uncertain outcome. Reload and **Check card setup** inspect its existing record without another exchange, purchase or payment request. Counts, membership selection, accepted terms and the explicit future-use choice remain on the private arrival draft. The final action stays unavailable while the required card outcome is unresolved.

| Desktop | Phone |
| --- | --- |
| [![Uncertain card storage during arrival, desktop](62-arrival-card-storage-uncertain-desktop.png)](62-arrival-card-storage-uncertain-desktop.png) | [![Uncertain card storage during arrival, phone](62-arrival-card-storage-uncertain-phone.png)](62-arrival-card-storage-uncertain-phone.png) |

## 63 — Saved card ready, with both payment sources identified

GET-only simulated reconciliation identifies the saved card. No membership has yet been purchased and no payment requested. The reviewed page identifies **membership card ending in 1111: $37.06** and the separately authorized **visit card ending in 4242: $16.47**. Only a new explicit final confirmation can proceed. Changing membership terms requires fresh current card authority, using provider reads of the known source rather than exchanging its nonce again. A separate browser exercise changes capacity during that authorization and verifies that no purchase or payment is created; the owner must review the changed visit.

| Desktop | Phone |
| --- | --- |
| [![Recovered card ready for explicit confirmation, desktop](63-arrival-new-card-ready-desktop.png)](63-arrival-new-card-ready-desktop.png) | [![Recovered card ready for explicit confirmation, phone](63-arrival-new-card-ready-phone.png)](63-arrival-new-card-ready-phone.png) |

## 64 — One purchase, distinct membership and visit receipts

After the explicit final action, the existing staged payment flow requests the membership payment first. Its synthetic success permits the separate visit charge after current facts are checked. The completed booking records **$37.06 membership + $16.47 visit = $53.53 received**, with one membership purchase and one card-storage exchange. The membership keeps card 1111 for its accepted schedule; the visit keeps its original card 4242. The accurate combined confirmation remains queued and unsent. No external card was charged.

| Desktop | Phone |
| --- | --- |
| [![Completed arrival using distinct cards, desktop](64-new-card-arrival-completed-desktop.png)](64-new-card-arrival-completed-desktop.png) | [![Completed arrival using distinct cards, phone](64-new-card-arrival-completed-phone.png)](64-new-card-arrival-completed-phone.png) |

## 65 — Known card saved, but its review expired

The original 20-minute card review has ended. The same arrival page retains the counts, selected card and current total while clearing the terms acceptance. A status check reads the existing outcome; it creates no authorization or payment and does not extend the old expiry. The customer must accept the current terms again before the final action can authorize this same known source. Unknown storage remains blocked, and the original browser/customer/actor scope remains required.

| Desktop | Phone |
| --- | --- |
| [![Known saved card with expired review, desktop](65-expired-known-card-review-desktop.png)](65-expired-known-card-review-desktop.png) | [![Known saved card with expired review, phone](65-expired-known-card-review-phone.png)](65-expired-known-card-review-phone.png) |

## 66 — Fresh approval, with payment still pending

The explicit fresh review checks the existing card through **one simulated metadata GET**, without a new nonce or storage exchange. The original authorization still expires at **12:20 p.m.**; a distinct current authorization expires at **12:41 p.m.** The confirmed purchase now requests its first **$37.06** payment, with **$0.00 received**. The visit payment remains unrequested until actual membership funding is confirmed. Polling never renews authority, an already recorded purchase cannot obtain another initial checkout authorization, and a changed or missing private scope requires a new reviewed checkout.

| Desktop | Phone |
| --- | --- |
| [![Fresh card review with truthful pending payment, desktop](66-fresh-card-review-payment-pending-desktop.png)](66-fresh-card-review-payment-pending-desktop.png) | [![Fresh card review with truthful pending payment, phone](66-fresh-card-review-payment-pending-phone.png)](66-fresh-card-review-payment-pending-phone.png) |

## 67 — Customer membership purchase on one page

After the existing phone/name/email verification, the customer reviews membership type, count, term, monthly/prepaid billing, chosen start, card, current price, installment dates and agreement together. This returning fictional family selects two Subscription memberships: **$37.06 today**, with two later scheduled installments. The final action obtains exact card authorization and records one purchase/payment request; it creates no visit or admission hold.

| Desktop | Phone |
| --- | --- |
| [![Public membership checkout, desktop](67-public-membership-checkout-desktop.png)](67-public-membership-checkout-desktop.png) | [![Public membership checkout, phone](67-public-membership-checkout-phone.png)](67-public-membership-checkout-phone.png) |

## 68 — Brand-new customer and new membership card

The same page supports a newly created, verified customer. With no saved card, new-card entry is selected automatically. One Unlimited membership prepaid for three months shows **$119.97 + $3.60 fee = $123.57**. The phone date field spans the form width. The provider area explicitly displays a placeholder: **these screenshots do not verify Banquest's hosted fields or a real card exchange**. Application-level new-customer storage/purchase is separately tested with local gateway doubles.

| Desktop | Phone |
| --- | --- |
| [![New customer membership checkout, desktop](68-new-customer-membership-checkout-desktop.png)](68-new-customer-membership-checkout-desktop.png) | [![New customer membership checkout, phone](68-new-customer-membership-checkout-phone.png)](68-new-customer-membership-checkout-phone.png) |

## 69 — Initial payment outcome still needs checking

A simulated uncertain first payment keeps the membership unconfirmed and displays **$0.00 received**. Checking the page does not create another purchase or repeat a charge. The customer is directed to check status or contact MonkeyDo before another attempt; an accepted purchase or uncertain card save cannot be discarded through Start again.

| Desktop | Phone |
| --- | --- |
| [![Uncertain public membership payment, desktop](69-public-membership-payment-uncertain-desktop.png)](69-public-membership-payment-uncertain-desktop.png) | [![Uncertain public membership payment, phone](69-public-membership-payment-uncertain-phone.png)](69-public-membership-payment-uncertain-phone.png) |

## 70 — Confirmed membership receipt

A later simulated successful result records **$37.06 once**, confirms the membership and queues one branded confirmation email. The receipt shows the purchased term, actual received amount and Book a visit action. No visit is created by the membership purchase. The outcome and all funds here are fictional; no Banquest charge or email delivery occurred.

| Desktop | Phone |
| --- | --- |
| [![Confirmed public membership, desktop](70-public-membership-confirmed-desktop.png)](70-public-membership-confirmed-desktop.png) | [![Confirmed public membership, phone](70-public-membership-confirmed-phone.png)](70-public-membership-confirmed-phone.png) |

## 71 — Reopen a receipt after checkout verification expires

After the original twenty-minute checkout expires, the same private browser can verify the purchasing customer using **one form: phone plus last name or email**. The receipt remains hidden until those details match the original purchase customer. Existing spelling, previous-phone and conflicting-profile confirmation steps remain available when needed. This verification cannot create a customer, purchase or payment.

| Desktop | Phone |
| --- | --- |
| [![Verify existing receipt, desktop](71-reverify-existing-membership-receipt-desktop.png)](71-reverify-existing-membership-receipt-desktop.png) | [![Verify existing receipt, phone](71-reverify-existing-membership-receipt-phone.png)](71-reverify-existing-membership-receipt-phone.png) |

## 72 — Existing receipt reopened without another payment

Fresh verification opens the original receipt, visibly labelled **No new payment was requested**. The fictional $37.06 receipt, accepted purchase, card authorization and original financial deadline are unchanged. Receipt access is separate from payment permission; it cannot save another card, retry a charge or extend the expired checkout. This browser exercise made no provider calls and delivered no email. Lost original private purchase context still requires assistance.

| Desktop | Phone |
| --- | --- |
| [![Reopened membership receipt, desktop](72-reverified-membership-receipt-desktop.png)](72-reverified-membership-receipt-desktop.png) | [![Reopened membership receipt, phone](72-reverified-membership-receipt-phone.png)](72-reverified-membership-receipt-phone.png) |

## 73 — Owner review before an installment request

A fictional unattempted preparation is blocked for owner review. Family, membership, month and due date remain together, with a direct link to the membership and the current **$37.06 card estimate**. **Resume this installment** is available only for a current, eligible, unattempted preparation. It does not bypass an existing declined or uncertain charge. This is a simulated local queue interruption; no installment request was created while viewing the page.

| Desktop | Phone |
| --- | --- |
| [![Unattempted installment review, desktop](73-scheduled-installment-owner-review-desktop.png)](73-scheduled-installment-owner-review-desktop.png) | [![Unattempted installment review, phone](73-scheduled-installment-owner-review-phone.png)](73-scheduled-installment-owner-review-phone.png) |

## 74 — Missed scheduled date uses explicit payment controls

On the following fictional day, the same preparation cannot resume as a catch-up charge. The owner can open the membership's existing payment controls and close the technical task. The page explicitly states that closing it **does not record payment**; the unpaid installment remains due. Both samples are actual GET-only application captures with no new financial record or provider call.

| Desktop | Phone |
| --- | --- |
| [![Missed installment review, desktop](74-missed-installment-owner-review-desktop.png)](74-missed-installment-owner-review-desktop.png) | [![Missed installment review, phone](74-missed-installment-owner-review-phone.png)](74-missed-installment-owner-review-phone.png) |

## 75 — One verified gift card for membership and arrival

The same arrival page shows **$35.98 membership + $15.99 visit = $51.97** paid with a physically presented gift card. One verification covers the combined amount; there is no duplicate cash-received checkbox. Monthly installments still require the separately accepted saved card, while prepaid gift-card purchases need no future card. Changing the amount or including/removing the membership clears the gift verification before another confirmation.

These actual desktop/phone captures use a disposable fictional test database. The browser exercise previewed without creating a purchase, then confirmed once and verified two constituent gift-card receipts with no provider calls. This records a staff-verified tender; it does not claim a gift-card balance service or permit gift cards for cancellation/no-show fees.

| Desktop | Phone |
| --- | --- |
| [![Gift-card membership arrival, desktop](75-gift-card-membership-arrival-desktop.png)](75-gift-card-membership-arrival-desktop.png) | [![Gift-card membership arrival, phone](75-gift-card-membership-arrival-phone.png)](75-gift-card-membership-arrival-phone.png) |

## 76 — Paid membership during an owner-comped visit

The visit remains **$0.00**, and two monthly Subscription places cost **$35.98 cash today**. The existing payment selector offers membership tenders only while Buy a membership with this visit is selected. Removing that purchase restores Owner-comped booking — no payment; adding it again requires fresh acceptance. The phone billing and saved-card fields span the form so their selected text and last four digits remain readable.

The actual disposable-database browser exercise confirms one membership receipt, no visit receipt, no benefit consumption and no provider calls. Separate service checks cover verified prepaid gift-card funding and a simulated $37.06 membership-card payment whose confirmed outcome completes the $0 arrival without a second charge. The original complimentary visit decision, waiver checks and original email remain intact.

| Desktop | Phone |
| --- | --- |
| [![Membership during comped visit, desktop](76-comped-visit-membership-desktop.png)](76-comped-visit-membership-desktop.png) | [![Membership during comped visit, phone](76-comped-visit-membership-phone.png)](76-comped-visit-membership-phone.png) |

## 77 — Review an available benefit on the original booking receipt

One Unlimited place became available after another booking released it. This customer's original private receipt still shows its saved **$16.47** estimate and offers a reviewed **$0.00** booking price. The updated itemization and original-to-adjusted explanation expand on that page. One clear button confirms the new price; no new waiver, attendee or card form is needed. The booking keeps its already reserved capacity.

Viewing this screen writes no quote or benefit reservation. The original twenty-minute private booking verification is not extended. Another booking taking the benefit, changed verification, staff pricing decisions or started arrival/payment prevent the old review from completing. New customers can use a later funded membership even when their ordinary booking was created without membership metadata.

| Desktop | Phone |
| --- | --- |
| [![Customer benefit review, desktop](77-public-benefit-review-desktop.png)](77-public-benefit-review-desktop.png) | [![Customer benefit review, phone](77-public-benefit-review-phone.png)](77-public-benefit-review-phone.png) |

## 78 — Confirm the new price without recording a payment or visit

The original **$16.47** quote remains in history. The new quote explains **−$15.00 membership benefit, −$0.45 uncharged card fee and −$1.02 tax estimate = $0.00**. One daily benefit is **reserved**, with attendance and use still pending. The actual browser confirmation preserves the original card binding, waiver record, payment/posting/email counts and deadline. Reloading creates nothing again.

Recorded Zelle is displayed separately from the booking estimate and remains available for staff arrival reconciliation; this action never records another receipt or a completed refund. The unchanged original confirmation stays in history, with no automatic replacement email. Historical ordinary quotes also keep adult allowances distinct from actual cancelled admissions. All data and funds here are fictional; no provider request or email delivery occurred.

| Desktop | Phone |
| --- | --- |
| [![Customer benefit reserved, desktop](78-public-benefit-applied-desktop.png)](78-public-benefit-applied-desktop.png) | [![Customer benefit reserved, phone](78-public-benefit-applied-phone.png)](78-public-benefit-applied-phone.png) |

## 79 — Split visit payments and a membership on the same arrival page

Two monthly Subscription places cost **$35.98**, paid by cash. The visit's split rows contain **$10.00 cash**, leaving **$6.17 on the booking card** including its $0.17 processing fee. The combined summary and final button show **$45.98 cash + $6.17 visit card = $52.15**. The accepted card for later membership installments remains separate. Counts, waivers and the existing arrival controls stay on the same page.

Preview creates no purchase, receipt or benefit usage. Choosing physical gift card for the membership shows the verification control even when the visit has no gift-card part; changing the amount or removing the membership clears verification. A positive membership payment requires its own actual tender choice. Splitting that membership payment itself or using recorded Zelle to fund it remains in development.

| Desktop | Phone |
| --- | --- |
| [![Split visit and manual membership review, desktop](79-split-visit-membership-review-desktop.png)](79-split-visit-membership-review-desktop.png) | [![Split visit and manual membership review, phone](79-split-visit-membership-review-phone.png)](79-split-visit-membership-review-phone.png) |

## 80 — Actual funds after one combined confirmation

The fictional browser scenario confirms once, initially recording **$45.98 cash** and leaving the **$6.17 visit card pending**. No paid combined email is queued in that pending state. A simulated successful outcome on that same card operation then produces **$52.15 actual combined new funds**: **$35.98 membership + $16.17 visit**. The visit's own cash/card rows remain readable, alongside the linked membership and one queued combined confirmation. No actual provider request or email delivery occurred.

All-manual visit splits, strict gift/Zelle verification, actual Zelle bank dates, earlier recorded Zelle, prepaid membership, fully credit-funded membership and known/unknown visit-card recovery are developer-tested. Repeated or overlapping confirmations cannot create another membership, receipt set or card remainder. Cash/check collected at arrival uses today's date even when a separate visit Zelle part was received earlier.

| Desktop | Phone |
| --- | --- |
| [![Split visit and membership actual funds, desktop](80-split-visit-membership-received-desktop.png)](80-split-visit-membership-received-desktop.png) | [![Split visit and membership actual funds, phone](80-split-visit-membership-received-phone.png)](80-split-visit-membership-received-phone.png) |

## 81 — Separate membership Zelle alongside the visit payment

The same arrival page shows **$35.98 separate membership Zelle + $10.00 visit cash + $6.17 visit card = $52.15**. Only choosing the membership's separate Zelle transfer reveals its bank sender/date and verification. The cash/check acknowledgment is hidden. Monthly future installments retain their accepted card; the visit remainder stays on the booking card.

Staff verifies that these membership funds have not already been recorded for this booking. This does not allocate existing booking Zelle to membership or check a bank account automatically. Actual bank date/sender enter the accepted combined history. Changes clear stale receipt verification; the remaining-balance control preserves any newer typed amount when its response arrives late.

| Desktop | Phone |
| --- | --- |
| [![Separate membership Zelle review, desktop](81-separate-membership-zelle-review-desktop.png)](81-separate-membership-zelle-review-desktop.png) | [![Separate membership Zelle review, phone](81-separate-membership-zelle-review-phone.png)](81-separate-membership-zelle-review-phone.png) |

## 82 — Separate bank funds and the confirmed visit result

The membership's fictional **$35.98 Zelle** keeps its actual **March 8** bank receipt date; the **$10 visit cash** is recorded at arrival on **March 9**. Initially **$45.98** is received and the card is pending. After a simulated successful outcome on the same **$6.17** operation, the page shows **$52.15 combined new funds** and **$16.17 visit funds**, with the separate membership bank details alongside the link. One combined confirmation is queued, with none delivered externally.

Developer checks also cover separate visit/member bank proofs and dates, existing booking Zelle, duplicate submissions, prepaid/card-free membership, full credit, a zero-dollar member visit and atomic rollback. No actual provider or bank request occurred. Reallocation of already recorded booking Zelle and splitting the membership's own first payment remain unfinished.

| Desktop | Phone |
| --- | --- |
| [![Separate membership Zelle recorded, desktop](82-separate-membership-zelle-received-desktop.png)](82-separate-membership-zelle-received-desktop.png) | [![Separate membership Zelle recorded, phone](82-separate-membership-zelle-received-phone.png)](82-separate-membership-zelle-received-phone.png) |

## 83 — Apply existing credit on the arrival page

This visit has one included member admission and one ordinary child admission. Staff reviews **$10.00 existing credit + $6.17 remaining card payment = $16.17**. Only that remaining card portion has a processing fee. The original-to-adjusted price, credit, payment choice, waivers and final confirmation stay on the existing page. **Use available credit** caps the chosen amount at the eligible visit balance; changing financial amounts clears an earlier gift/Zelle receipt verification.

This is a review capture: no credit is spent and no visit payment exists yet. The source is a fictional earlier $16.47 card receipt converted through the existing reconciliation service: $0.45 retained original processing fee and $16.02 available credit. That source receipt is not recreated as new money. The completed example below changes the selection to full credit before confirmation.

| Desktop | Phone |
| --- | --- |
| [![Visit credit review, desktop](83-visit-credit-review-desktop.png)](83-visit-credit-review-desktop.png) | [![Visit credit review, phone](83-visit-credit-review-phone.png)](83-visit-credit-review-phone.png) |

## 84 — A fully credit-funded visit is separate from money received

In the same fictional browser flow, staff uses the available-credit shortcut and explicitly confirms **$15.99 existing credit**. There is no new payment, card operation, financial posting or email. **$0.03 credit remains** for future use. The booking shows **Covered by customer credit**, **Total received: $0.00** and **Existing customer credit applied: $15.99**. The original booking estimate stays in history; its uncharged fee/tax adjustments explain the current total.

Ordinary/supervised admission and socks are developer-tested. Recorded visit Zelle applies first; any actual new cash/check/card/gift/Zelle remainder stays separate. Source holds stop new spending and unstarted card dispatch. Simultaneous source use, repeated confirmation, runtime permissions, exact component budgets and migration reversal are guarded. Samples 86–87 add credit alongside partial cancellation fees. Simultaneous new membership/visit credit allocation and credit returns remain in development.

| Desktop | Phone |
| --- | --- |
| [![Visit credit completed, desktop](84-visit-credit-completed-desktop.png)](84-visit-credit-completed-desktop.png) | [![Visit credit completed, phone](84-visit-credit-completed-phone.png)](84-visit-credit-completed-phone.png) |

## 85 — The original private customer receipt shows the reviewed funds

The customer's original verified receipt now shows the reviewed **$15.99 visit total**, **$15.99 credit applied**, **$0.00 new money** and **No remaining visit payment is due**. It does not promise another arrival charge. This is the same original private booking context and deadline, with no public wallet balance or underlying source identifiers. Reloading creates no new application, payment or message, and the original queued booking confirmation remains unchanged in history.

| Desktop | Phone |
| --- | --- |
| [![Private credit receipt, desktop](85-private-credit-receipt-desktop.png)](85-private-credit-receipt-desktop.png) | [![Private credit receipt, phone](85-private-credit-receipt-phone.png)](85-private-credit-receipt-phone.png) |

## 86 — Credit covers admission; the cancellation fee remains payable

Three children were booked and two arrive. One member admission is included. The available-credit action chooses **$15.99 admission/tax credit**, leaving the itemized **$3.00 partial cancellation fee + $0.09 card fee = $3.09**. The adjusted visit total is **$19.08**, with **$0.03 credit left after confirmation**. The card-funded portion is nontaxable, so it has no additional processing-fee tax. Counts, waivers, the price adjustment, credit and remaining payment stay on the original page.

A $10 credit selection instead leaves $9.26 on the card; cash for the full eligible-credit example is only $3. Preview creates no payment or credit application. Earlier recorded Zelle reduces the eligible credit first; it is not a second receipt. The maximum-credit action excludes the cancellation fee rather than filling the entire visit total.

| Desktop | Phone |
| --- | --- |
| [![Credit with cancellation review, desktop](86-credit-with-cancellation-review-desktop.png)](86-credit-with-cancellation-review-desktop.png) | [![Credit with cancellation review, phone](86-credit-with-cancellation-review-phone.png)](86-credit-with-cancellation-review-phone.png) |

## 87 — Actual received money after the remaining card result

The same fictional flow confirms **$15.99 credit** and queues one **$3.09 card** request. The booking initially reports **$0.00 received**, with that card pending. A simulated approval of the same operation changes it to **$3.09 received + $15.99 existing credit = $19.08 funded**. The original-to-adjusted price and cancellation fee remain visible. The booking-card obligation closes; future membership obligations and accepted history remain intact. No actual provider request or extra email occurs.

The database still forbids moving credit onto a cancellation-fee line. Developer checks cover every credit cent in this mixed example, exact component totals, safe bank-first allocation, a known decline resolved by $3 cash, malformed funding data, native/JSON caps, unchanged historical pricing and release compatibility. Whole cancellation/no-show fees continue to use the original card/Zelle rules.

| Desktop | Phone |
| --- | --- |
| [![Credit with cancellation received, desktop](87-credit-with-cancellation-received-desktop.png)](87-credit-with-cancellation-received-desktop.png) | [![Credit with cancellation received, phone](87-credit-with-cancellation-received-phone.png)](87-credit-with-cancellation-received-phone.png) |

## 88 — Split the membership payment on the same purchase page

Two monthly Subscription places: **$35.98 principal + $0.57 card fee = $36.55 first payment**. The actual received amounts are **$10 cash + $5 check + $2 verified Zelle**, leaving **$19.55 on the accepted card**. Only its $18.98 principal receives a processing fee. Amounts, bank date/sender, source proofs, saved card, terms, current total and final action stay on the existing page. Preview records no purchase or money.

The accepted card also covers later **$37.06** installments on their original dates. Source/amount changes clear old receipt verification and acceptance. Gift-card proof appears only for a positive gift amount. Fully manual prepaid hides the card; prepaid with a positive card remainder still requires its current authority. This sample uses a fictional saved card, with no hosted-field verification or provider call.

| Desktop | Phone |
| --- | --- |
| [![First membership split review, desktop](88-first-membership-split-review-desktop.png)](88-first-membership-split-review-desktop.png) | [![First membership split review, phone](88-first-membership-split-review-phone.png)](88-first-membership-split-review-phone.png) |

## 89 — Four actual tenders, one membership and its next installment

After one confirmation, the fictional membership initially has **$17 received**, one **$19.55 card request pending**, and pending benefits. A simulated success of that same card operation then gives **$36.55 received**, active benefits and one queued unsent customer confirmation. The overview retains cash/check/Zelle/card amounts, the **October 30** bank receipt date/sender, and the next **$37.06 November 30** installment. Future dates, accepted terms and receipt history are preserved.

Developer checks also cover cash/check/gift prepaid splits, monthly manual-first/future-card rules, backed credit, strict proofs, actual receipt dates, stale reviews, atomic rollback, known-decline recovery, unknown outcomes, source holds, concurrent confirmations/source spending, public rejection, migration reversal and release compatibility. This first-payment split is available on the standalone staff purchase/renewal/addition page. Fully received manual splits also work during arrival (samples 90–91). Samples 94–96 add a membership card remainder with a later visit card; samples 97–99 add received manual visit funds to that sequence. No actual financial POST or external email occurs.

| Desktop | Phone |
| --- | --- |
| [![First membership split received, desktop](89-first-membership-split-received-desktop.png)](89-first-membership-split-received-desktop.png) | [![First membership split received, phone](89-first-membership-split-received-phone.png)](89-first-membership-split-received-phone.png) |

## 90 — Received membership split and visit on one page

Two monthly Subscription places are funded by **$10 cash + $5 check + $20.98 separately verified Zelle = $35.98**. The visit separately receives **$10 cash** and requests **$6.17 from its booking card**. The combined review shows **$20 cash + $5 check + $20.98 Zelle to record**, the visit card remainder and **$52.15 total**. The membership bank receipt keeps its actual March 8 date; cash/check use the March 9 visit date.

Counts, membership choices, original-to-adjusted visit price, waivers, receipt proofs and the final confirmation stay on the existing arrival page. A private draft reload retains the entered membership and visit amounts. Changing amounts clears cash/bank/gift proofs and requires reviewing terms again. Monthly membership still needs its accepted future-installment card; that card is separate from the booking's visit card.

Samples 92–93 add an explicit allocation of already recorded booking Zelle between membership and visit. Samples 94–96 support a membership card balance when the visit uses only card and/or those prior bank funds. Samples 97–99 also record new manual visit funds immediately while the first membership card is pending. Samples 100–102 add returns/reallocation after confirmed membership funding. Returns before funding is confirmed and terminal unfinished-visit closure remain guarded work.

| Desktop | Phone |
| --- | --- |
| [![Combined received membership split review, desktop](90-combined-received-membership-split-review-desktop.png)](90-combined-received-membership-split-review-desktop.png) | [![Combined received membership split review, phone](90-combined-received-membership-split-review-phone.png)](90-combined-received-membership-split-review-phone.png) |

## 91 — One purchase, separate received amounts and one combined confirmation

One final confirmation records **$45.98 actually received**, one membership, its three manual receipts and the visit's separate cash/card records. Membership benefits are active because the full $35.98 first payment was received. The combined paid email waits while the $6.17 visit card remains pending. A simulated success of that same operation gives **$52.15 new received funds**, including **$16.17 visit funds**, and one queued unsent combined confirmation. The separate membership bank receipt/date/sender remain visible beside its membership link.

Developer checks cover strict independent cash/bank/gift proofs, old booking Zelle without double counting, backed existing credit, prepaid no-card funding, monthly future-card requirements, stale amount/date/sender reviews, late rollback, concurrent repeated confirmation and private new-card authority. Actual hosted-field rendering and processor outcomes are not verified by this saved-card scenario. No provider request or external email delivery occurs.

| Desktop | Phone |
| --- | --- |
| [![Combined received membership split complete, desktop](91-combined-received-membership-split-complete-desktop.png)](91-combined-received-membership-split-complete-desktop.png) | [![Combined received membership split complete, phone](91-combined-received-membership-split-complete-phone.png)](91-combined-received-membership-split-complete-phone.png) |

## 92 — Assign recorded Zelle between membership and visit

The fictional customer already transferred **$25** on **March 7**. Staff explicitly assign **$20** of that original receipt to membership, leaving **$5** for the visit. Two monthly Subscription places total **$35.98**, so new membership money is **$10 cash + $5.98 check = $15.98**. The visit totals **$15.99**, with **$10.99 new cash** after its $5 bank allocation. New money to record is **$26.97**; the earlier $25 remains separate.

The amount selection lives on the same arrival page, alongside counts, member choices, original-to-adjusted visit price, waivers, accepted future card and final confirmation. The visit's **Use remaining balance** shortcut subtracts only its remaining $5 bank allocation. Changing the membership bank assignment clears old cash proof/terms. A private draft reload retains the explicit assignment. Review allocates nothing and creates no receipt.

| Desktop | Phone |
| --- | --- |
| [![Recorded booking Zelle membership review, desktop](92-recorded-zelle-membership-review-desktop.png)](92-recorded-zelle-membership-review-desktop.png) | [![Recorded booking Zelle membership review, phone](92-recorded-zelle-membership-review-phone.png)](92-recorded-zelle-membership-review-phone.png) |

## 93 — Original transfer once, accurate new funds and reusable bank history

One final confirmation records one membership and **$26.97 new cash/check funds**, and applies the same original $25 once across both invoices. There is still **one original bank receipt**, with **$20 membership + $5 visit** allocations. No additional bank transfer or card charge is claimed. The completed booking separates the $15.99 visit funding, new membership/visit amounts and the prior membership bank allocation, retaining its original date/sender. One combined confirmation is queued, with none delivered externally. Later membership installments keep their original **$37.06** amount and dates.

Developer checks cover exact source/customer/booking/invoice scope, original-date FIFO across multiple receipts, partial/full first-payment funding, stale receipt reviews, atomic rollback, repeated/concurrent confirmation, fresh nonretained future-card authority and unused-balance refunds. PostgreSQL serializes the original receipt budget across allocations and refunds; immutable metadata ties membership use to its accepted first installment and actual combined booking. A used migration/release cannot be reversed into code that loses those source facts. Samples 94–96 extend this original-bank allocation to a first membership card remainder while keeping its bank assignment separate from new receipts.

| Desktop | Phone |
| --- | --- |
| [![Recorded booking Zelle membership complete, desktop](93-recorded-zelle-membership-complete-desktop.png)](93-recorded-zelle-membership-complete-desktop.png) | [![Recorded booking Zelle membership complete, phone](93-recorded-zelle-membership-complete-phone.png)](93-recorded-zelle-membership-complete-phone.png) |

## 94 — Split membership receipts and card with arrival

Two monthly Subscription places have **$35.98 principal**. Membership receives **$10 cash + $5 check**; its remaining $20.98 principal attracts only **$0.63 fee**, so the first membership card request is **$21.61** and the membership total is **$36.61**. The separate visit card is **$16.47**, payable only after membership funding. New payments total **$53.08**. Counts, receipts, waivers, both exact card amounts, original-to-adjusted visit price and the final action stay on the existing page.

Preview records nothing. Monthly terms retain the accepted future card and original **$37.06** installments. A partially manual prepaid purchase needs its card only for the remainder; fully manual prepaid hides it. This saved-card sample does not verify real Banquest fields.

| Desktop | Phone |
| --- | --- |
| [![First card split arrival review, desktop](94-first-card-split-arrival-review-desktop.png)](94-first-card-split-arrival-review-desktop.png) | [![First card split arrival review, phone](94-first-card-split-arrival-review-phone.png)](94-first-card-split-arrival-review-phone.png) |

## 95 — Received membership money while its card is pending

One confirmation records **$15 actually received** and queues the one **$21.61 membership card** request. Benefits and attendance remain pending. The separate **$16.47 visit card has not been requested**. Checking status reads the original request; it does not charge again or extend the original thirty-minute extra-capacity hold.

Developer checks also cover $25 earlier booking Zelle assigned as $20 membership/$5 visit, plus $10 new membership cash and its $6.16 card remainder. Prior bank funds and new money remain separate. Restoring the saved intent after a database reload neither subtracts that bank assignment twice nor wrongly rejects its original source identity. An unknown first-card result preserves received funds and blocks replacement collection. A confirmed decline permits explicit remaining-principal collection, removing only the uncharged card fee.

| Desktop | Phone |
| --- | --- |
| [![First card split arrival pending, desktop](95-first-card-split-arrival-pending-desktop.png)](95-first-card-split-arrival-pending-desktop.png) | [![First card split arrival pending, phone](95-first-card-split-arrival-pending-phone.png)](95-first-card-split-arrival-pending-phone.png) |

## 96 — Funded membership, then the separately confirmed visit

A simulated success of that same membership card request makes **$36.61 membership funds** received. Current counts, sources, capacity, waivers and benefits are rechecked before arrival and the **$16.47 visit card** request. The paid combined email still waits for that visit result. Its simulated success yields **$53.08 new funds**, split into **$36.61 membership + $16.47 visit**, and one queued unsent combined confirmation. No actual provider call or email delivery occurs.

Samples 97–99 extend this pending membership-card sequence to new manual visit cash/check/verified Zelle/gift receipts. They are saved immediately and applied once when the same reviewed arrival completes. Samples 100–102 add returns/reallocation after confirmed membership funding; earlier unconfirmed funding and terminal unfinished-visit closure remain in development. Fully received manual membership splits and card-only visits retain their existing paths.

| Desktop | Phone |
| --- | --- |
| [![First card split arrival complete, desktop](96-first-card-split-arrival-complete-desktop.png)](96-first-card-split-arrival-complete-desktop.png) | [![First card split arrival complete, phone](96-first-card-split-arrival-complete-phone.png)](96-first-card-split-arrival-complete-phone.png) |

## 97 — Received visit funds with a pending membership card

The membership receives **$10 cash + $5 check**, with its **$21.61 card** remainder first. The visit separately receives **$3 cash + $2 check + $1 verified Zelle + $1 physically verified gift card = $7**. Only its remaining **$9.26** goes on the visit card after membership funding. First membership total **$36.61**, visit **$16.26**, new combined money **$52.87**. Review creates no purchase, receipt or charge.

The original combined page retains counts, terms, waivers, original-to-adjusted visit price, bank date/sender, independent proofs and one final confirmation. Changing a received amount clears old receipt verification, including visit Zelle when no customer-credit wallet exists. Changed membership payment terms require renewed acceptance; changing only the visit amount does not invent different membership terms.

| Desktop | Phone |
| --- | --- |
| [![Pending visit receipt review, desktop](97-pending-visit-receipts-review-desktop.png)](97-pending-visit-receipts-review-desktop.png) | [![Pending visit receipt review, phone](97-pending-visit-receipts-review-phone.png)](97-pending-visit-receipts-review-phone.png) |

## 98 — Actual visit money remains visible before arrival

One confirmation saves **$22 actual funds**, separately **$15 membership + $7 visit**, and queues only the first membership card request. The four original visit receipts survive reload with their source, amount, collecting staff member and original date. Cash/check/gift are dated **March 9**; verified visit Zelle keeps **March 8** and its sender. The pending page and booking identify the received visit funds without claiming active benefits, completed attendance or a paid visit.

A declined, uncertain or expired first-card sequence preserves these receipts and directs the owner to review. It never silently records the same manual money later as another receipt or sends a visit charge before confirmed membership funding. The original thirty-minute extra-capacity reservation remains fixed.

| Desktop | Phone |
| --- | --- |
| [![Pending visit receipts saved, desktop](98-pending-visit-receipts-saved-desktop.png)](98-pending-visit-receipts-saved-desktop.png) | [![Pending visit receipts saved, phone](98-pending-visit-receipts-saved-phone.png)](98-pending-visit-receipts-saved-phone.png) |

## 99 — Original tenders applied once, then the exact remaining card

Simulated membership funding permits current arrival validation, applies the four original visit receipts to its invoice once with their original dates, and requests only **$9.26** on its booking card. The paid combined email still waits for that visit result. Its simulated success gives **$52.87 received**, split into **$36.61 membership + $16.26 visit**, with one queued unsent combined confirmation. Source records and invoice applications describe the same funds; they are not counted twice.

Developer checks also combine one earlier bank receipt with new manual visit receipts, preserve source attribution when a different owner completes fresh review, and force concurrent confirmation, late rollback and direct database forgery attempts. **Remaining boundary:** changing these accepted manual amounts, returning them or closing the unfinished visit requires the still-in-progress owner return/reallocation flow. Current checks stop those changes without losing receipts or collecting a replacement. These fictional saved-card outcomes do not verify Banquest hosted fields or processor behavior.

| Desktop | Phone |
| --- | --- |
| [![Pending visit receipts applied, desktop](99-pending-visit-receipts-applied-desktop.png)](99-pending-visit-receipts-applied-desktop.png) | [![Pending visit receipts applied, phone](99-pending-visit-receipts-applied-phone.png)](99-pending-visit-receipts-applied-phone.png) |

## Checked so far

The complete **1,456-test PostgreSQL suite passes** (521.824s), including thirteen new source/owner/browser-context cases, three actual PostgreSQL concurrency/reversal cases and one release-compatibility case. Exact original tenders/dates, earlier bank versus new money, owner attribution, source immutability, deferred completeness, rollback, unknown outcomes, all-card membership funding and an entirely received visit are covered. An older test expecting this newly supported split combination to fail has been updated; the final full suite includes its corrected expectation and the additional payment/source edge cases.

The final actual desktop/phone scenario passes in **9.972s**. Four visit sources ($7) and membership manual funds ($15) remain visible while the first $21.61 card is pending; their original dates survive reload. After simulated funding, four source applications and only a $9.26 visit card follow. Final funds total $52.87, with one membership/eight operations and one queued unsent combined confirmation. It checks current proof/terms reset, the explicit pending card remainder, no overflow/JavaScript errors and no bank/provider/storage/nonce/mail requests. All six final samples 97–99 were recaptured and visually inspected.

All **99 desktop/phone pairs**, 198 image links, Ruff/format (527 Python files), model drift, JavaScript syntax, whitespace and **53 reviewed migration hashes** pass. All 52 prior hashes remain unchanged. Used migration/release guards preserve original pending receipt/application evidence. Feature switches remain off and the same PR stays draft. This checkpoint preceded samples 100–102. Returns before confirmed membership funding and terminal unfinished-visit closure, plus the other explicitly listed scope, remain in progress. No merge, deployment or live financial action is included.


## 100 — Record an actual unused visit-fund return

After the first membership payment is confirmed, the owner chooses **Review current arrival or unused funds**. This pauses automatic arrival before any manual return is handled. On that same arrival page, **Record returned visit funds** expands only when usable original receipts exist. It records a return already completed using the original payment method; it sends no bank transfer, changes no gift-card balance and does not refund membership.

The fictional visit originally received **$3 cash + $2 check + $1 Zelle + $1 gift card**. The owner records **$2 actually returned from the original cash receipt**. The original $3 record stays intact, with its collecting staff member and date. The actual return has its own owner/date/history. Changed amount/source/date clears the return confirmation. Before membership funding is confirmed, this action is unavailable.

| Desktop | Phone |
| --- | --- |
| [![Record actual unused visit-fund return, desktop](100-pending-visit-return-record-desktop.png)](100-pending-visit-return-record-desktop.png) | [![Record actual unused visit-fund return, phone](100-pending-visit-return-record-phone.png)](100-pending-visit-return-record-phone.png) |

## 101 — Review the remaining funds and exact card balance together

Recording the return keeps entered attendee counts on the same page. **Original cash $3, returned $2, remaining $1** appears beside the other original receipts, with **$5 total visit funds remaining**. Received funds apply automatically; **Add another payment** permits genuinely new money above each held amount. Existing verified Zelle/gift funds do not need to be entered or verified again. New amounts require their own verification and actual bank date.

The owner reviews the current **$16.32 visit total** and explicitly chooses **apply received visit funds $5.00 and charge card $11.32**. Returning $2 changes how the visit is funded: its card fee rises from $0.25 to $0.31. The original reviewed $9.26 card amount is no longer authorized. Stale source balances, stale arrival reviews and competing application/return requests cannot reuse the returned money. Original membership payment, term, future installments and original bank receipt dates stay intact.

| Desktop | Phone |
| --- | --- |
| [![Review remaining received funds and card balance, desktop](101-pending-visit-return-review-desktop.png)](101-pending-visit-return-review-desktop.png) | [![Review remaining received funds and card balance, phone](101-pending-visit-return-review-phone.png)](101-pending-visit-return-review-phone.png) |

## 102 — Completed arrival shows net received money and return history

One arrival confirmation applies **$1 cash + $2 check + $1 Zelle + $1 gift card**, then requests only the reviewed **$11.32 visit card**. After a simulated approval of that exact operation, the booking shows **$16.32 visit received + $36.61 membership = $52.93 received after the recorded $2 visit return**. The return and original source history remain readable. One combined confirmation is queued only after the visit funds are confirmed; none is delivered externally. The fixture also has its original queued booking confirmation.

Repeating the same return or arrival confirmation creates no second return/application. This is an unused, uninvoiced visit-source return during an unfinished arrival. It does not provide ordinary cash change, refund an already completed visit, cancel membership, move money to customer credit or resolve the still-guarded unconfirmed-funding cases.

| Desktop | Phone |
| --- | --- |
| [![Completed arrival after actual unused-fund return, desktop](102-pending-visit-return-completed-desktop.png)](102-pending-visit-return-completed-desktop.png) | [![Completed arrival after actual unused-fund return, phone](102-pending-visit-return-completed-phone.png)](102-pending-visit-return-completed-phone.png) |

## Current unused-fund return verification checkpoint

The final complete **1,476-test PostgreSQL suite passes in 553.752s**, with all final application, schema, template, JavaScript and test changes present before it started. Thirteen new source/native cases, six actual PostgreSQL concurrency/reversal cases and one release-compatibility case cover exact budgets, actual dates, explicit owner pause, partial/full returns, genuinely new same-tender receipts, stale reviews, immutable history, duplicate submissions and private-draft preservation. The final real desktop/phone browser scenario passes in **8.118s**, preserving entered counts, applying four source remainders once and showing $52.93 after a simulated $11.32 visit-card approval and a recorded fictional $2 cash return. All six final samples 100–102 were visually inspected; no overflow, duplicate field IDs, JavaScript errors or external bank/gift/provider/storage/nonce/mail calls occur.

Ruff/format (**532 Python files**), model drift, JavaScript syntax, whitespace, all **204 image links / 102 desktop–phone pairs** and **54 reviewed migration hashes** pass. All 53 prior hashes remain unchanged. The same PR remains draft and membership/collection switches remain off. Returns before confirmed membership funding, terminal unfinished-visit closure and the other listed Stage 3 scope remain in progress. No merge, deployment or live financial action is included.


## 103 — Gift card covers goods and the card covers the cancellation fee

Two children were booked and one arrives. The current visit contains **$15 admission + $0.99 sales tax + $3 partial cancellation fee**. The gift card can cover only the **$15.99 admission/tax**. The cancellation fee remains on the booking card: **$3 + $0.09 processing fee = $3.09**, with no tax on that nontaxable fee or its processing fee. The adjusted visit total is **$19.08**.

**Use remaining balance** fills **$15.99** for the gift row. It also recovers from an excessive $16 entry without including the cancellation fee. Changing a financial amount clears the physical-gift verification; this works even without a membership purchase or available customer-credit field. Counts, waivers, the original-to-adjusted price and one final confirmation remain on the same page. No item allocation is requested from staff.

Cash/check/new Zelle can instead cover the $3 fee without a card charge. Existing credit and gift cards share the eligible admissions/socks balance; neither can cover a cancellation fee. Original recorded Zelle is applied first, separately from new money. A gift-card amount above the remaining eligible balance is refused before any receipt or card request.

| Desktop | Phone |
| --- | --- |
| [![Gift goods and separate cancellation fee review, desktop](103-gift-admission-and-fee-review-desktop.png)](103-gift-admission-and-fee-review-desktop.png) | [![Gift goods and separate cancellation fee review, phone](103-gift-admission-and-fee-review-phone.png)](103-gift-admission-and-fee-review-phone.png) |

## 104 — Completed visit separates actual gift funds and the fee card

One explicit arrival confirmation records **$15.99 verified gift-card funds** and requests one **$3.09 card payment**. While that card is pending, only the gift money is received. A simulated approval of that exact card operation makes **$19.08 total received**. The payment card lists both sources under the total, and the saved breakdown retains the original estimate, removed admission, tax/fee adjustments and $3 cancellation fee. No processor request, gift-card balance API or external email occurs in this fictional scenario.

The receipt, remaining-payment service and database constraint all refuse a new gift receipt on any cancellation-fee component. The existing single-method remaining-payment page requires another eligible method while a fee is outstanding; gift payment still works when only eligible goods remain. Historical paid gift records stay unchanged, including their original actor/date/allocation. A pending legacy invalid gift request cannot become a successful receipt; existing owner correction of an actual historic receipt through its original tender remains available. No automatic historical correction or ordinary refund program is introduced.

| Desktop | Phone |
| --- | --- |
| [![Paid gift goods and separate cancellation fee, desktop](104-gift-admission-and-fee-paid-desktop.png)](104-gift-admission-and-fee-paid-desktop.png) | [![Paid gift goods and separate cancellation fee, phone](104-gift-admission-and-fee-paid-phone.png)](104-gift-admission-and-fee-paid-phone.png) |

## Current gift-card fee-scope verification checkpoint

The final complete **1,498-test PostgreSQL suite passes in 546.725s**, with all final application, schema, JavaScript, template and test changes present before it started. Twenty-two new pricing/native/legacy cases cover all fee components, eligible gift/credit budgets, actual source dates and money, partial-cancellation card fee/tax, 1,599 exact gift-cent values, verified receipt refusal, pending source return, remaining payments and historical replay/correction. The final related **101 cases pass in 65.893s**.

The final real desktop/phone browser scenario passes in **5.388s**, recovering an excessive gift entry with the $15.99 shortcut, resetting proof after an amount change and recording one gift receipt plus only the $3.09 card request. The simulated successful card outcome yields $19.08 received. All four final 103–104 images were visually inspected, with no overflow, duplicate field IDs, JavaScript errors or external provider/storage/nonce/gift/bank/mail calls.

Ruff/format (**536 Python files**), model drift, JavaScript syntax, whitespace, **208 image links / 104 desktop–phone pairs** and **55 reviewed migration hashes** pass; all 54 prior hashes remain unchanged. Membership/collection features remain off by default and the same PR stays draft while the separately listed Stage 3 work continues. Actual Banquest hosted fields and processor outcomes remain unverified; no merge, deployment or live financial action is included.


SQLite development-backend limit: full application tests stop during an older renewal-link table alteration because the existing core_membershippublicacceptance_scope trigger references core_membershiprenewallink while that table is being remade. Migration 0081 is not reached in that setup. The new SQLite gift constraint itself passes 18 isolated SQL checks, covering all four fee components, valid goods, legacy pending/final states, original-tender correction and reverse/reinstall. This does not establish complete SQLite application support; PostgreSQL is the fully verified backend for this increment.


## 105 — Stop an arrival and keep the booking and membership

After the first membership installment has a confirmed successful outcome, the owner can pause the unfinished arrival and record any actual returns of its unused visit funds. **Stop this arrival; keep booking** then opens a compact control on that same arrival screen. It names the original booking counts and explains that the membership and its agreed installment schedule continue. A reason and explicit confirmation are required.

Stopping does not cancel the booking, undo the membership, charge a fee, send a refund or record attendance. Only the additional temporary places held for this attempt are released; the original booking capacity and any separate session blocks remain. Unsaved attendee edits are not saved by the stop action. A later arrival starts with a fresh review from booking details. Cancellation and no-show remain explicit separate booking actions.

This fictional example has **$36.61 received for membership**, and all **$7 of unused new visit funds already returned and recorded**. It creates no visit card request or visit invoice. Unknown/unpaid membership funding, a cancelled membership, unresolved funding or unreturned new visit funds continue to block this action. Original unused booking Zelle stays attached to the booking and is not returned or recorded twice.

| Desktop | Phone |
| --- | --- |
| [![Stop pending arrival while keeping the booking and membership, desktop](105-stop-arrival-review-desktop.png)](105-stop-arrival-review-desktop.png) | [![Stop pending arrival while keeping the booking and membership, phone](105-stop-arrival-review-phone.png)](105-stop-arrival-review-phone.png) |

## 106 — Upcoming booking with stopped-arrival history

The saved booking still shows its original **3 children, 1 adult and 0 babies**, even though an unsaved baby count was entered before stopping. The payment card has a collapsed **Stopped arrivals** history with the stopping owner, time, reason, membership link and first membership payment received when stopped. Those first-payment funds are separate from visit payments. The same history lists the unused visit funds actually returned before stopping: $3 cash, $2 check, $1 gift card and $1 Zelle. Membership terms, dates, receipts and future installment amounts are unchanged.

The original send-confirmation choice is retained. Where it calls for an email, one membership-purchase confirmation is queued, with no claim that this visit was completed. No email is delivered by this review. Repeated clicks reuse the original stop record; older review tabs, private drafts and queued continuation jobs cannot complete the stopped attempt. A stale status poll returns to the current booking.

| Desktop | Phone |
| --- | --- |
| [![Upcoming booking and stopped-arrival membership history, desktop](106-stopped-arrival-booking-desktop.png)](106-stopped-arrival-booking-desktop.png) | [![Upcoming booking and stopped-arrival membership history, phone](106-stopped-arrival-booking-phone.png)](106-stopped-arrival-booking-phone.png) |

## Current stopped-arrival verification checkpoint

The complete **1,522-test PostgreSQL suite passed in 589.464s**, with all financial, service, schema and recovery-hold changes present. After clarifying the first-payment label and showing returned visit sources in the retained history, the final **37 focused checks passed in 63.790s**, including the actual desktop/phone browser scenario and PostgreSQL overlap/reversal checks. The earlier related 111-case run also passed in 113.766s.

The browser records exactly one stop, leaves the original booking Upcoming at 3 children/1 adult/0 babies, keeps $36.61 in first membership funds and its three existing operations, and creates no visit invoice or new card request. All $7 of unused new visit funds are already returned and remain visible by tender. Only the extra hold is released; one membership-purchase email is queued and no visit-completion email is created. The four final 1440px/390px images were visually inspected. No overflow, duplicate IDs, nested forms, JavaScript errors or external financial/storage/nonce/gift/bank/mail actions occur.

Ruff/format (**541 Python files**), model drift, JavaScript syntax, whitespace, all **212 image links / 106 desktop–phone pairs** and **56 reviewed migration hashes** pass; all 55 earlier hashes are unchanged. All four GitHub checks passed for the preceding 979df52 revision; checks for this new commit run after publication. Membership/collection flags remain off, the PR stays draft and the remaining scope is still in progress. No merge or deployment is included.


## 107 — Unused visit funds with an unconfirmed membership payment

The first membership payment has **$15 confirmed cash/check funds** and an existing **$21.61 card request with an unknown outcome**. Separately, staff already received **$7 for the visit**: $3 cash, $2 check, $1 gift card and $1 new Zelle. Those visit receipts remain independent of the membership invoice.

The owner chooses **Review unused visit funds** on this same page. Arrival is explicitly paused before any return is recorded. The owner then records only an amount actually returned by its original method; here it is **$2 returned from the original $3 visit cash receipt**. The unknown membership card keeps its existing operation and provider reference. No replacement charge, membership cancellation, refund request, attendance, benefit usage or completed-visit email is created.

The original unstarted conditional membership card request must first be handled through its existing payment/purchase controls. The visit-return action does not implicitly cancel it. A request already sending or with an unknown outcome remains for reconciliation. Staff cannot create the owner pause or return, and a stale pause button cannot target another intent.

| Desktop | Phone |
| --- | --- |
| [![Owner records a real visit cash return while membership card outcome is unconfirmed, desktop](107-unconfirmed-member-visit-return-desktop.png)](107-unconfirmed-member-visit-return-desktop.png) | [![Owner records a real visit cash return while membership card outcome is unconfirmed, phone](107-unconfirmed-member-visit-return-phone.png)](107-unconfirmed-member-visit-return-phone.png) |

## 108 — Return recorded; membership outcome still unconfirmed

The original visit cash receipt stays **$3**, with **$2 returned** and **$1 remaining**. Across the four visit sources, **$5 remains**. Membership confirmed funds stay **$15**, the original card outcome stays **unknown**, and the same three membership operations remain. There is no visit invoice or applied visit receipt yet. The earlier reviewed visit price is labelled as such; an updated price/card balance needs a fresh arrival review after membership funding is resolved.

The browser test later simulates success of that same membership operation. The owner pause remains in place: no visit card request, receipt application or attendance is created automatically. A new owner review can then apply only the remaining original sources and explicitly confirm the revised price. All financial/card/provider outcomes in this gallery are fictional, and no external request or email delivery occurs.

Original booking Zelle stays separately available to its booking. A membership cancellation and its refund due also stay separate: returning unused visit cash does not pay or reduce that membership refund liability. Samples 109–110 add that stop after a recorded cancellation, with its refund liability preserved.

| Desktop | Phone |
| --- | --- |
| [![Unused visit cash return retained with the original unresolved membership payment, desktop](108-unconfirmed-member-return-recorded-desktop.png)](108-unconfirmed-member-return-recorded-desktop.png) | [![Unused visit cash return retained with the original unresolved membership payment, phone](108-unconfirmed-member-return-recorded-phone.png)](108-unconfirmed-member-return-recorded-phone.png) |

## Current unconfirmed-payment visit-return verification checkpoint

The complete **1,536-test PostgreSQL suite passed in 593.362s**, with all final application, template and test changes present before it started. Eleven new native cases and three actual PostgreSQL overlap cases cover original receipt budgets, sending/unknown/unstarted outcomes, roles and stale intents, duplicate returns, late funding, first-payment/visit separation, explicit membership cancellation/refund due, original bank balances and return versus continuation. All prior financial/closure/migration tests also pass.

The final actual desktop/phone browser scenario passed in **5.825s**, after the full suite, and captured all four final 107–108 images. All four were visually inspected. It preserves the unknown original membership card/reference and its three operations, records one actual $2 visit return, leaves $5 original visit funds, and creates no visit invoice/application/attendance or customer confirmation. A later simulated success still leaves arrival paused until fresh owner review. No overflow, duplicate IDs, nested forms, JavaScript errors or external provider/storage/nonce/gift/bank/mail actions occur.

Ruff/format (**544 Python files**), model drift, JavaScript syntax, whitespace, all **216 unique PNG links / 108 desktop–phone pairs** and all **56 unchanged reviewed migration hashes** pass. No new schema, runtime grant or capability format is introduced. All four GitHub checks passed for the preceding db38c5b checkpoint; the new commit starts its own checks after publication. Feature switches remain off, PR37 stays draft, and the remaining Stage 3 scope continues. No release, merge or deployment is included.


## 109 — Stop only the arrival after membership cancellation

This membership purchase was separately cancelled before its original card request was sent. Its **$15 cash/check payment remains received and $15 is due back** on the membership record. The owner has already returned and recorded all **$7 of unused visit funds** by their original methods. These two amounts remain separate.

On the same pending-arrival page, the owner reviews **Stop this arrival; keep booking**. It shows the cancellation's effective date and **membership refund due when reviewed: $15**. The checkbox keeps the original booking and explicitly leaves the membership cancellation/refund on its existing record. A reason and final confirmation stop only this arrival attempt. They do not cancel the booking, send a refund, change accepted terms or request another payment.

If there are no new visit receipts, **Review stopping this arrival** still opens the owner's review. If unused visit money remains, actual original-method returns must be recorded first. End-current-cycle cancellations retain their recorded effective date; the screen does not claim they already ended today. Unconfirmed incoming membership receipts still need reconciliation before this stop.

| Desktop | Phone |
| --- | --- |
| [![Stop an arrival after membership cancellation while preserving its refund due, desktop](109-cancelled-member-arrival-stop-review-desktop.png)](109-cancelled-member-arrival-stop-review-desktop.png) | [![Stop an arrival after membership cancellation while preserving its refund due, phone](109-cancelled-member-arrival-stop-review-phone.png)](109-cancelled-member-arrival-stop-review-phone.png) |

## 110 — Booking kept; membership refund remains on its own record

The booking remains **Upcoming**, at its original **3 children and 1 adult**. Only the extra temporary arrival hold is released. The **Stopped arrivals** history identifies the recorded membership cancellation, its effective date, **$15 membership refund due when arrival stopped**, first membership payment received, and the already returned visit funds. It links to the membership for the current refund status; the historical amount is not rewritten when a later refund is recorded.

The same **$15 refund liability remains on the dashboard**. No visit invoice, attendance, benefit usage, new payment or refund request is created. A previously queued/sending/unconfirmed membership refund retains its existing operation and remains for separate handling. The original cancellation-email choice stays in place; stopping creates no membership-purchase or completed-visit email. Repeating the confirmation reuses the same stop record.

Samples 105–106 have also been recaptured with the common **Stopped arrivals** history label, verifying that keeping a funded membership still works. The additive cancellation reference preserves earlier stop evidence. Once used, it requires compatible code and refuses schema reversal; it cannot be silently interpreted as a kept membership by older code.

| Desktop | Phone |
| --- | --- |
| [![Upcoming booking with retained cancellation and membership refund history, desktop](110-cancelled-member-arrival-stopped-desktop.png)](110-cancelled-member-arrival-stopped-desktop.png) | [![Upcoming booking with retained cancellation and membership refund history, phone](110-cancelled-member-arrival-stopped-phone.png)](110-cancelled-member-arrival-stopped-phone.png) |

## Current cancellation-linked arrival-stop verification checkpoint

Final developer verification: the complete PostgreSQL application suite passed **1,555 tests in 630.202 seconds**, with all final application/schema/template changes included. After adding one further test for an already-unknown outgoing membership refund, the final focused run passed **15 tests in 18.126 seconds**, including all 13 cancellation-linked stop cases and both actual desktop/phone browser scenarios. The final test inventory is 1,556; a complete local 1,556-test run is not claimed. Earlier targeted verification also passed 55 related migration, concurrency and compatibility checks. Both browser runs confirm one stopped intent, original booking/counts, released extra hold, zero visit invoices/attendance/provider calls/delivered emails and no overflow, duplicate IDs, nested forms or JavaScript errors. The cancelled scenario retains the $15 membership refund and both dashboard refund plans; the kept-purchase scenario retains its $36.61 funding and one queued, unsent membership confirmation. All eight final desktop/phone images for samples 105–106 and 109–110 were visually inspected. The gallery has 110 pairs/220 unique PNGs. Ruff/formatting (547 Python files), migration drift, JavaScript syntax, whitespace and all 57 reviewed migration pins pass; all 56 previously published migration hashes are unchanged. The previous published commit dc63883 passed all four GitHub checks. Checks for this update will be assessed after publication. Feature/collection switches remain off by default; PR #37 stays draft, with no merge, deployment or live financial/email action.


## 111 — Export actual arrival funds without counting applications twice

The existing **Export filtered memberships** control now offers **Arrival funds** (one row per original separately received visit receipt) and **Arrival fund history** (one row per actual receipt, unused-fund return or invoice application). Both retain the current membership filters across every results page. The new reports require explicit export, financial-view and booking-view permissions.

This fictional stopped-arrival example has four original sources totalling **$7 received**, four actual original-tender returns totalling **$7**, **$0 applied** and **$0 unapplied**. The separate **$15 membership refund due** is not described as a visit return. The actual downloaded [four-row balances CSV](111-arrival-funds-sample.csv) and [eight-row event CSV](111-arrival-fund-events-sample.csv) are included for review.

Original receipt IDs, dates, collecting actors and Zelle sender remain in evidence. Application rows have zero new money received. Unknown first membership payments do not erase actual visit receipts. Stopped/completed status, linked applications and separately recorded membership cancellation stay identifiable. Original booking Zelle and later invoice refunds remain in their own payment records; these reports do not claim to include them.

| Desktop | Phone |
| --- | --- |
| [![Arrival funds export, desktop](111-arrival-fund-export-desktop.png)](111-arrival-fund-export-desktop.png) | [![Arrival funds export, phone](111-arrival-fund-export-phone.png)](111-arrival-fund-export-phone.png) |

## 112 — Existing export history records both downloads

The actual browser download prepares exactly four balance rows and eight event rows. Existing owner export history records the report, matching customer filter, row count and actor. Downloading changes no financial facts and makes no gateway or email call. CSV contact/sender text uses the existing spreadsheet-formula protection; card-storage references, signed evidence, stop reasons and private financial snapshots are excluded.

| Desktop | Phone |
| --- | --- |
| [![Arrival fund export history, desktop](112-arrival-fund-export-history-desktop.png)](112-arrival-fund-export-history-desktop.png) | [![Arrival fund export history, phone](112-arrival-fund-export-history-phone.png)](112-arrival-fund-export-history-phone.png) |

Developer verification for this read-only reporting increment: The final combined run passed **20 tests in 12.908 seconds**, covering the nine new source-report cases, all ten existing reporting cases and the actual desktop/phone browser/download scenario, including four/eight-row CSV checks, unchanged three payment operations, exact audit rows and no overflow, JavaScript errors, duplicate IDs, nested forms, provider calls or external delivery. All four final 111–112 images were visually inspected. Source balances use one query for receipt/return/application facts; event history prefetches returns in bounded chunks. Existing filtered selection, spooled generation, formula protection and required audit-before-download remain. There is no migration or financial mutation in this increment. The last full local suite is the 1,555-test cancellation-stop checkpoint above, followed by its 15 focused checks; no complete local 1,565-test run is claimed. The PR remains draft and the remaining Stage 3 work continues.


## 113 — Apply a paid visit toward a first membership

From today's paid arrived booking, **Apply today's visit toward a membership purchase** opens one combined page. The known customer is reused. Membership places/term, the original paid visit, amount applied, new payment, future installment dates, saved-card selection and accepted agreement stay together.

The fictional card-paid visit received **$16.47**. Its **$0.45 original processing fee stays on the visit**; the replaced admission and both original taxes supply **$16.02** toward the **$17.99 first membership month**. Only **$1.97 new cash/check** is recorded. A saved card is authorized for the two remaining **$18.53** installments, without another immediate card charge. This sample uses a cash/check remainder; samples 117–118 add received Zelle, verified physical gift cards and manual combinations. For a separately authorized card remainder, see samples 119–124; mixed manual/card remainders remain in progress.

| Desktop | Phone |
| --- | --- |
| [![Paid visit and first membership review, desktop](113-paid-visit-membership-review-desktop.png)](113-paid-visit-membership-review-desktop.png) | [![Paid visit and first membership review, phone](113-paid-visit-membership-review-phone.png)](113-paid-visit-membership-review-phone.png) |

## 114 — First membership funded without a duplicate visit receipt

The actual final confirmation creates one membership and one conversion, applies the existing $16.02 and records only $1.97 new cash. The original transaction remains unchanged. The membership overview shows **$16.02 credit applied**, **$1.97 money received**, the next installment and **one free visit used / one available** this month. Return to converted visit leads directly back.

Purchase, actual-fund transfer, new receipt and benefit usage share one transaction. A late error rolls them back together. Repeated POSTs and recovery reloads return to the existing purchase; a different confirmation cannot convert the visit twice. No original receipt is also refunded.

| Desktop | Phone |
| --- | --- |
| [![Paid visit membership active, desktop](114-paid-visit-membership-active-desktop.png)](114-paid-visit-membership-active-desktop.png) | [![Paid visit membership active, phone](114-paid-visit-membership-active-phone.png)](114-paid-visit-membership-active-phone.png) |

## 115 — Original booking and its financial evidence stay visible

The visit remains arrived with its original attendees and waiver records. The saved price shows the membership admission adjustment and **$1.02 original tax reversal**, leaving the **$0.45 retained fee**. Payment history still shows the original **$16.47 card receipt**, the **$16.02 transfer** and the linked membership's separate **$1.97 new payment**. Conversion does not create another booking, capacity change or visit receipt.

One combined customer update accurately separates the original payment, retained fee, applied funds, new money, unused credit and next installment. It is queued locally and **not sent**. A changed contact refreshes an unattempted snapshot; an attempted/unknown message never automatically queues another copy. The original booking confirmation remains historical.

| Desktop | Phone |
| --- | --- |
| [![Converted paid visit booking, desktop](115-paid-visit-converted-booking-desktop.png)](115-paid-visit-converted-booking-desktop.png) | [![Converted paid visit booking, phone](115-paid-visit-converted-booking-phone.png)](115-paid-visit-converted-booking-phone.png) |

## 116 — Excess becomes customer credit, with no zero-dollar receipt

The second actual browser scenario starts from **$37.31 cash already paid** for two children/two adults. **$35.98** funds two Subscription places for their first month and **$1.33** remains customer credit. No new cash/check receipt or immediate card charge is created. Both child benefits are consumed; future installment dates and their accepted amounts remain unchanged.

These browser scenarios select only an existing synthetic saved card. SDK initialization is stubbed without any card-entry fields, all external browser requests are blocked, and gateway/storage methods are mocked. They do not verify actual Banquest hosted fields or processor behavior.

| Desktop | Phone |
| --- | --- |
| [![Paid visit excess credit review, desktop](116-paid-visit-excess-credit-review-desktop.png)](116-paid-visit-excess-credit-review-desktop.png) | [![Paid visit excess credit review, phone](116-paid-visit-excess-credit-review-phone.png)](116-paid-visit-excess-credit-review-phone.png) |

The complete **1,588-test PostgreSQL suite passed in 673.174s**. After the final receipt-proof reset, **70 focused checks passed in 73.378s**, covering the new conversion, real PostgreSQL overlap/reversal races, affected public/card/deployment paths and three actual Chromium scenarios. A changed server price clears both accepted terms and every old receipt-verification checkbox, including without JavaScript; it cannot convert the visit using proof of an older, smaller amount. The browser checks cover the $1.97 remainder, $1.33 excess credit and stale-price refusal with original funds untouched. All eight final 113–116 desktop/phone images were visually inspected, with no overflow, JavaScript errors, duplicate IDs or nested forms. All 553 Python files pass lint/format checks; model drift, both affected JavaScript syntax checks, diff whitespace, all 232 PNGs and all 58 migration pins pass. The final native inventory is 1,589; a complete local run of that later inventory is not claimed. No external provider/storage request, delivered email, merge or deployment occurred. The same PR37 remains draft with default-off features.


## 117 — Paid-visit purchase with received split payments

Choose **Split** for one or more new cash, check, Zelle or physical gift-card receipts. Enter only the remaining membership payment. The original paid visit is already applied and must not be entered again. Monthly purchases retain separate accepted saved-card authority for their future installments; prepaid fully manual purchases need no card.

This fictional example applies **$16.02** from the **$16.47 original card receipt**, retaining its **$0.45 fee**. The remaining **$1.97** is received as **$0.50 cash + $0.50 check + $0.47 Zelle + $0.50 physical gift card**. Each used source requires its own verification. Zelle retains its **March 8** bank receipt date and sender; cash/check/gift keep **March 9**. A physical gift card is presented and verified manually; no gift-card API debit is implied.

Before the whole balance is entered, the price card shows the actual unallocated amount and confirmation stays disabled. There is no hypothetical new card fee or implied card charge. Excess entries, missing proof, missing sender and future bank dates are rejected before any purchase/conversion. Changing the review clears old terms and receipt proof.

| Desktop | Phone |
| --- | --- |
| [![Paid visit received split review, desktop](117-paid-visit-received-split-review-desktop.png)](117-paid-visit-received-split-review-desktop.png) | [![Paid visit received split review, phone](117-paid-visit-received-split-review-phone.png)](117-paid-visit-received-split-review-phone.png) |

## 118 — Actual receipts and the funded membership

One confirmation records four distinct new receipts totalling **$1.97**, applies the source **$16.02**, funds the first membership month and uses one visit benefit. The original **$16.47** receipt remains on its booking. No new card charge, zero-dollar receipt or separate original-source refund is created. The next two accepted installments remain **$18.53** each.

The overview shows applied credit separately from total new money received and lists all four payment methods. One queued combined update describes the original payment, retained fee, applied funds and new receipt total. Repeated confirmation cannot duplicate the membership, conversion or any individual receipt. Late failures roll back every new receipt together with the conversion; an incomplete split never consumes the original funds or benefits.

| Desktop | Phone |
| --- | --- |
| [![Paid visit received split active, desktop](118-paid-visit-received-split-active-desktop.png)](118-paid-visit-received-split-active-desktop.png) | [![Paid visit received split active, phone](118-paid-visit-received-split-active-phone.png)](118-paid-visit-received-split-active-phone.png) |

The final affected-path run passed **102 checks in 88.755s**, including 98 native PostgreSQL cases and four actual Chromium scenarios. It covers all 11 new received-split cases, four new real concurrency/reversal cases, existing paid-visit and first-split behavior, public/card checkout and the reviewed additive upgrade/capability guard. After shortening the selected dropdown label for phones, the final 12-case check passed in 11.845s and the final browser capture passed again in 6.213s. All 12 final 113–118 desktop/phone images were visually inspected, with no overflow, JavaScript errors, duplicate IDs or nested forms. Lint/format (556 Python files), model drift, affected JavaScript syntax, whitespace, all 236 PNGs/links and all 59 migration pins pass; all 58 published migration files/hashes remain unchanged. The prior complete local PostgreSQL suite was 1,588 tests before this increment; the final native inventory is 1,605, and a complete local run of that later inventory is not claimed. The prior published commit passed all four GitHub checks; new CI awaits publication. No external provider/storage call, delivered email, merge or deployment occurred.

These are fictional local application screenshots. Provider/storage gateways were mocked and all non-local browser requests blocked. Actual Banquest fields/outcomes, external email delivery and gift-card API verification are not demonstrated. Samples 119–124 add the durable conditional workflow for a card-only remainder. Mixed manual/card remainder and further recovery paths remain guarded. Default-off features and the same draft PR remain; no merge or deployment is included.


## 119 — Paid-visit membership with a card remainder

The same purchase page can now request only the card remainder after reserving the paid visit funds. The fictional **$16.47** original card receipt supplies **$16.02** toward the **$17.99** first membership month. Its original **$0.45 fee stays on the visit**. The new card base is only **$1.97**, with **$0.06 new membership card fee**, so the final button explicitly requests **$2.03**. The next two accepted installments remain **$18.53** each. Membership and its fee are not taxable.

The price card and accepted terms identify these as **reserved original funds**, applied after the separate card result is confirmed. Opening the review creates no purchase or financial operation. Source counts, waivers and capacity stay on the original already-arrived booking.

| Desktop | Phone |
| --- | --- |
| [![Paid visit card review, desktop](119-paid-visit-card-review-desktop.png)](119-paid-visit-card-review-desktop.png) | [![Paid visit card review, phone](119-paid-visit-card-review-phone.png)](119-paid-visit-card-review-phone.png) |

## 120 — Card requested; original visit remains paid and unchanged

One confirmation records the accepted membership, a durable source reservation and **one $2.03 card request**. New money received is **$0.00** until the result is known. No source credit is issued or applied, and no membership visit benefit is used. The original invoice and receipt remain **$16.47**. The page links the original booking and the existing card record without offering a second generic collection of the full membership invoice.

While pending, a refund, price adjustment or other conversion of that original visit is paused. The source reservation does not expire merely because a card result is uncertain. An unattempted dispatch has a 30-minute acceptance window; expiry cancels that unattempted request for review and retains the source reservation until a safe explicit resolution.

| Desktop | Phone |
| --- | --- |
| [![Paid visit card pending, desktop](120-paid-visit-card-pending-desktop.png)](120-paid-visit-card-pending-desktop.png) | [![Paid visit card pending, phone](120-paid-visit-card-pending-phone.png)](120-paid-visit-card-pending-phone.png) |

## 121 — Uncertain card outcome does not trigger another charge

An unknown/action result keeps the original visit intact and its funds reserved. The page says to check the **existing payment**. The stop action is unavailable while that outcome is uncertain; generic collection cannot charge the original reserved amount again. A dashboard notice remains until this application is completed or safely stopped.

The browser check changes a fictional result from unknown to independently recorded success. The actual **$2.03 receipt is saved first**, while the original visit is still unchanged and source credit remains zero. Applying the original funds is a separate operation; a failure there cannot erase the already recorded card result or resubmit its financial POST.

| Desktop | Phone |
| --- | --- |
| [![Paid visit card unknown, desktop](121-paid-visit-card-unknown-desktop.png)](121-paid-visit-card-unknown-desktop.png) | [![Paid visit card unknown, phone](121-paid-visit-card-unknown-phone.png)](121-paid-visit-card-unknown-phone.png) |

## 122 — Known card result; source application completed once

After known success, the ordinary worker can complete the accepted source application. The same page also offers **Continue applying this visit** when completion is eligible and needs resuming. This action requests **no new card payment**.

Completion atomically records the exact source reversals, **$16.02 backed credit application**, fully funded **$18.05 first membership invoice** and one actual visit benefit used. The original receipt remains **$16.47**, its adjusted invoice is **$0.45**, and the membership shows **$2.03 new money received** separately from applied credit. One free benefit remains. The application notice clears, one combined update is queued without delivery, and replay cannot create another receipt or conversion.

| Desktop | Phone |
| --- | --- |
| [![Paid visit card completed, desktop](122-paid-visit-card-completed-desktop.png)](122-paid-visit-card-completed-desktop.png) | [![Paid visit card completed, phone](122-paid-visit-card-completed-phone.png)](122-paid-visit-card-completed-phone.png) |

## 123 — Declined card; an explicit owner stop

A declined card creates no new received money or visit credit. The rare stop action stays collapsed. When the existing result is known and no new money remains held, the owner can enter a reason and choose **Stop applying this visit**. An unattempted ready request is cancelled locally before its source funds are released. A sending/unknown/action request or unresolved money prevents this action.

This stop releases the source application; it does not claim a refund, cancel the original booking, or silently cancel membership terms. Same-purchase card retry/replacement, alternative-tender recovery and fresh approval for later-date/source changes are still being completed and remain guarded.

| Desktop | Phone |
| --- | --- |
| [![Paid visit card declined owner stop, desktop](123-paid-visit-card-declined-stop-desktop.png)](123-paid-visit-card-declined-stop-desktop.png) | [![Paid visit card declined owner stop, phone](123-paid-visit-card-declined-stop-phone.png)](123-paid-visit-card-declined-stop-phone.png) |

## 124 — Stop recorded; original paid visit retained

The stopped page states that the original visit and its payment are unchanged and no longer reserved for this application. In this declined example, the original invoice and receipt remain **$16.47**, membership new money and applied credit remain **$0.00**, and no benefit or conversion was recorded. The source-application dashboard notice clears. The accepted membership/purchase and declined operation remain in history; any separate membership-term or retained-fee/refund resolution needs its own reviewed action.

| Desktop | Phone |
| --- | --- |
| [![Paid visit card stopped, desktop](124-paid-visit-card-stopped-desktop.png)](124-paid-visit-card-stopped-desktop.png) | [![Paid visit card stopped, phone](124-paid-visit-card-stopped-phone.png)](124-paid-visit-card-stopped-phone.png) |

Developer verification: the complete PostgreSQL suite passed **1,629 tests in 707.227 seconds**. After the final future-card binding and replay-handling fixes, **69 focused checks passed in 39.458 seconds**, including 22 paid-visit card cases, five real PostgreSQL concurrency/reversal cases, existing billing/card/collection cases and two actual Chromium scenarios. Changing a future billing card preserves the original accepted first request; a stale continuation after completion or owner stop cannot repeat funds or falsely report a transfer. The final native inventory is 1,633; a complete local 1,633-test run is not claimed. All 12 final desktop/phone images for samples 119–124 were visually inspected. Browser checks report no overflow, JavaScript errors, duplicate IDs or nested forms, with zero external provider/storage calls and zero delivered emails. All 561 Python files pass lint/format checks; migration drift, affected JavaScript syntax, diff whitespace, all 248 PNGs/gallery links and all 60 migration pins pass. All 59 previously published migration files/hashes remain unchanged. The previous published commit passed all four GitHub checks; checks for this increment will run after publication. Features remain off by default and PR #37 remains draft; no merge, deployment or live financial action occurred.

All financial data and card outcomes above are fictional local application checks. Provider/storage gateways were mocked and non-local browser requests blocked; the hosted SDK stub initialized no fields and only an existing synthetic saved card was selected. Actual Banquest card fields, processor outcomes, external email delivery and live financial actions are not verified here. The same draft PR remains default-off with no release included. Mixed manual/card remainders, further payment/date recovery, multi-cohort checkout and the remaining owner/credit/reporting scope continue independently.

The pending panel identifies the original session date/time directly. Changing a future billing card preserves the already accepted original request and its recorded card outcome; it does not retarget or retry that payment.


## 125 — Explicitly request the card remainder again

Staff open **Try a card payment again** on the same membership page after the original $2.03 request is definitively declined. They choose the eligible saved card ending 6789 and confirm customer authorization for exactly **$2.03**, including its existing $0.06 fee. The card for future installments remains 1234. The original terms, purchased dates, first failed request and $16.47 paid visit remain in place.

| Desktop | Phone |
| --- | --- |
| [![Explicitly request the card remainder again, desktop](125-paid-visit-recovery-review-desktop.png)](125-paid-visit-recovery-review-desktop.png) | [![Explicitly request the card remainder again, phone](125-paid-visit-recovery-review-phone.png)](125-paid-visit-recovery-review-phone.png) |


## 126 — Replacement request pending

The same membership has one new ready $2.03 request on card 6789. The previous request remains declined. The panel names the card for this payment, separately from the future membership card. Original funds of **$16.02 remain reserved**; **recorded new money is $0.00**, with no conversion, customer-credit application or benefit usage. No automatic retry or second purchase is created.

| Desktop | Phone |
| --- | --- |
| [![Replacement request pending, desktop](126-paid-visit-recovery-pending-desktop.png)](126-paid-visit-recovery-pending-desktop.png) | [![Replacement request pending, phone](126-paid-visit-recovery-pending-phone.png)](126-paid-visit-recovery-pending-phone.png) |


## 127 — Uncertain replacement outcome

A simulated unknown result keeps the exact existing request and original source funds. Staff cannot request another payment or stop/release the source while the outcome is uncertain. **Check existing card payment** opens that request; reloading does not charge again. Zero recorded receipts does not establish that the processor made no charge.

| Desktop | Phone |
| --- | --- |
| [![Uncertain replacement outcome, desktop](127-paid-visit-recovery-unknown-desktop.png)](127-paid-visit-recovery-unknown-desktop.png) | [![Uncertain replacement outcome, phone](127-paid-visit-recovery-unknown-phone.png)](127-paid-visit-recovery-unknown-phone.png) |


## 128 — Known replacement funds complete the original application

After the simulated $2.03 outcome is confirmed, a separate pure continuation applies the original $16.02 and uses one visit benefit. The original receipt remains **$16.47**, with its original invoice reduced to **$0.45**. The membership shows **$2.03 new money received**, **$16.02 credit applied**, one used/one available benefit and future **$18.53** installments still on card 1234. Card 6789 paid this remainder only. One combined email is queued but not sent.

| Desktop | Phone |
| --- | --- |
| [![Known replacement funds complete the original application, desktop](128-paid-visit-recovery-completed-desktop.png)](128-paid-visit-recovery-completed-desktop.png) | [![Known replacement funds complete the original application, phone](128-paid-visit-recovery-completed-phone.png)](128-paid-visit-recovery-completed-phone.png) |


This is an explicit recovery after customer contact, never an automatic retry. Each recovery records its own actor, selected card, previous known failed request, exact frozen amount/allocation, accepted review and 30-minute unattempted deadline. Repeated confirmation returns that existing request; two different reviews cannot both replace one failure. A later confirmed decline permits another fresh review. Expiry before dispatch cancels only that unattempted request, retaining the source reservation for review. An owner stop cancels the latest ready request locally; it cannot race with dispatch and leave a released source supporting a sending request.

Samples 119–124 are refreshed with the active payment card and the **Recorded money received** pending label. Previously completed/paid overviews continue to show **Total money received**. These tests use synthetic already-saved cards; new-card hosted fields and real Banquest outcomes remain unverified. Manual alternatives, mixed manual/card remainders, general later-day/date exceptions remain in development. The bounded retained-fee cancellation release is covered in samples 129–132. Features stay off and PR37 stays draft.

The Dashboard notice opens the same paid-visit membership panel and cannot be dismissed while its source application is unresolved. Completion or a safe owner stop clears it. A new failure also creates fresh attention after an older historical acknowledgment. Later scheduled installments retain their own amount, date and payment authority; they do not reuse this first-payment recovery check.

Developer verification: the complete PostgreSQL suite passed **1,656 tests in 736.241 seconds**. After the final first-invoice dispatch and persistent Dashboard-notice corrections, **133 checks passed in 72.767 seconds**, including 19 new recovery cases, six real PostgreSQL concurrency/reversal/runtime cases, existing card/billing/collection/funding checks and three actual Chromium scenarios. Later scheduled installments retain their own payment authority; source notices link to the application, resist premature dismissal and reopen after historical acknowledgment when a new failure occurs. The final native inventory is 1,659; a complete local 1,659-test run is not claimed. Earlier expanded verification passed 68 checks, and the final screenshot capture passed 25 checks. All 20 final new/refreshed images for samples 119–128 were visually inspected; the final browser run repeated behavior/overflow/DOM checks without overwriting those PNGs. There is no overflow, JavaScript error, duplicate ID or nested form in those browser scenarios. All 565 Python files pass lint/format checks; migration drift, diff whitespace, all 256 PNGs/gallery links and all 61 migration pins pass. All 60 previously published migration files/hashes remain unchanged. All four GitHub checks passed for the prior published commit; checks for this increment run after publication. No external provider/storage request, delivered customer email, merge or deployment occurred. Features remain off by default and PR #37 stays draft.


## 129 — Cancelled membership with a refund still due

The first membership card payment is known received: **$2.03 on card 6789**. Before the original visit funds were applied, the owner recorded an immediate membership cancellation and approved a **$1.97 principal refund**, retaining its **$0.06 card fee**. The original visit remains paid **$16.47**, with **$16.02 reserved**. The same overview shows the cancellation and existing refund controls; releasing the original funds is unavailable until the chosen refund is known complete. Future card 1234 and the original accepted purchase remain in history.

| Desktop | Phone |
| --- | --- |
| [![Cancelled membership with a refund still due, desktop](129-cancelled-paid-visit-refund-due-desktop.png)](129-cancelled-paid-visit-refund-due-desktop.png) | [![Cancelled membership with a refund still due, phone](129-cancelled-paid-visit-refund-due-phone.png)](129-cancelled-paid-visit-refund-due-phone.png) |


## 130 — Unknown refund keeps the original funds reserved

The simulated **$1.97 refund has an unknown outcome**. It is labelled as a refund in payment history and is not subtracted from actual received funds yet. Staff check the existing refund; no automatic retry, replacement payment or source release is offered. The Dashboard keeps attention on the unresolved refund and original paid-visit application.

| Desktop | Phone |
| --- | --- |
| [![Unknown refund keeps the original funds reserved, desktop](130-cancelled-paid-visit-refund-unknown-desktop.png)](130-cancelled-paid-visit-refund-unknown-desktop.png) | [![Unknown refund keeps the original funds reserved, phone](130-cancelled-paid-visit-refund-unknown-phone.png)](130-cancelled-paid-visit-refund-unknown-phone.png) |


## 131 — One owner action after the chosen refund is complete

After a known **$1.97 refund to its actual receipt card 6789**, the membership retains **$0.06**. The owner enters a reason and selects **Release original visit funds** on this same page. This cancels only the **$16.02 membership amount never collected** and releases its reservation against the original visit. It sends no refund, creates no new receipt and does not convert the original visit into credit or activate benefits.

| Desktop | Phone |
| --- | --- |
| [![One owner action after the chosen refund is complete, desktop](131-cancelled-paid-visit-release-review-desktop.png)](131-cancelled-paid-visit-release-review-desktop.png) | [![One owner action after the chosen refund is complete, phone](131-cancelled-paid-visit-release-review-phone.png)](131-cancelled-paid-visit-release-review-phone.png) |


## 132 — Original visit retained and membership application closed

The original visit keeps its **$16.47 invoice and $16.47 recorded payment**, attendance, waiver and price history. The membership shows **$2.03 received**, **$1.97 refunded**, **$0.06 retained**, and the **$16.02 uncollected amount cancelled**. Its cancellation, purchased dates, old failed attempt and actual refund remain in history. The source notice clears only after this release commits. No customer credit, conversion or membership benefit is created; reopening or repeated confirmation cannot repeat the adjustment.

| Desktop | Phone |
| --- | --- |
| [![Original visit retained and membership application closed, desktop](132-cancelled-paid-visit-released-desktop.png)](132-cancelled-paid-visit-released-desktop.png) | [![Original visit retained and membership application closed, phone](132-cancelled-paid-visit-released-phone.png)](132-cancelled-paid-visit-released-phone.png) |

The chosen cancellation refund remains the owner's separate decision. A partial or zero refund retains the approved remaining membership money; it does not silently refund more. Pending/unknown funds, a future-effective cancellation, changed original-source facts, already-applied credit/benefits and an unmatched refund all prevent this release. This covers retained-fee cancellation before source application, including later closure after an effective cancellation; full external voids returning fees, historical tax corrections and general date exceptions remain guarded. Simulated outcomes verify application behavior only; no actual provider request, refund or email delivery occurred.

Developer verification: the complete PostgreSQL suite passed **1,683 tests in 782.583 seconds** with the final financial/service/schema changes. The final copy clarification then passed **18 checks in 19.205 seconds**, including all 17 new native cancellation-source cases and the actual Chromium refund/release scenario; it changes only the heading/success message to distinguish reserved funds from the booking. Earlier final-focused verification passed **88 checks in 81.639 seconds**, including six new real PostgreSQL concurrency/reversal/runtime-grant cases and existing cancellation/deployment checks. All eight final desktop/phone images for samples 129–132 were visually inspected. Browser assertions report no overflow, JavaScript errors, duplicate IDs or nested forms, with zero external provider/storage calls and zero delivered emails. All 569 Python files pass lint/format checks; migration drift, diff whitespace, all 264 PNGs/gallery links and all 62 migration pins pass. All 61 previously published migration files/hashes remain unchanged. All four GitHub checks passed for the prior published commit; checks for this increment run after publication. Membership and collection features remain off by default and PR37 remains draft. No merge, deployment or live financial action occurred.


## 133 — Enter a new card for the original remainder

After a definite decline, staff select **Enter a new card** within **Try a card payment again** on the same membership page. They record the customer's future-visit retention choice and authorize the exact **$2.03** remainder, including its existing **$0.06 fee**. **Save and request card payment** saves first, then submits the separately reviewed request once. Card **1234 for future membership installments stays unchanged**. The hosted-field area is explicitly simulated; this image does not verify Banquest's actual iframe.

| Desktop | Phone |
| --- | --- |
| [![Enter a new card for the original remainder, desktop](133-paid-visit-new-card-review-desktop.png)](133-paid-visit-new-card-review-desktop.png) | [![Enter a new card for the original remainder, phone](133-paid-visit-new-card-review-phone.png)](133-paid-visit-new-card-review-phone.png) |


## 134 — Uncertain card storage survives reload

The original $2.03 request is known declined, but the new card save has an unknown outcome. **Check card setup** reads that existing setup, including after a reload. Another payment, another save and release of the original visit funds remain blocked. The $16.47 original visit is unchanged, $16.02 stays reserved and new membership money is $0.00. Existing owner reconciliation can identify a known saved card through provider lookup without another card-save POST; a missing/ambiguous provider result still requires review.

| Desktop | Phone |
| --- | --- |
| [![Uncertain card storage survives reload, desktop](134-paid-visit-new-card-unknown-desktop.png)](134-paid-visit-new-card-unknown-desktop.png) | [![Uncertain card storage survives reload, phone](134-paid-visit-new-card-unknown-phone.png)](134-paid-visit-new-card-unknown-phone.png) |


## 135 — One request on the new card, with future billing preserved

The simulated save returns card **6789**, and the final reviewed form creates exactly one ready **$2.03** payment request. Saving and a ready request are not received funds: **new money received is $0.00**, no source credit or benefit is used, and the original visit remains paid **$16.47**. Future installments still use **1234**. A later known payment follows the existing pure source-application completion; no new purchase or automatic retry is created.

| Desktop | Phone |
| --- | --- |
| [![One request on the new card, with future billing preserved, desktop](135-paid-visit-new-card-requested-desktop.png)](135-paid-visit-new-card-requested-desktop.png) | [![One request on the new card, with future billing preserved, phone](135-paid-visit-new-card-requested-phone.png)](135-paid-visit-new-card-requested-phone.png) |

A card saved only for this payment remains protected while its source application is unresolved. Once closed, normal disposal can remove an unwanted card without deleting financial history. A future-visit Yes choice replaces the previous future-visit card only when the payment is explicitly requested; it never replaces the future membership mandate. An abandoned unconfirmed choice does not replace the old future-visit card. Unknown saves are not discarded or retried automatically.

Developer verification: the complete PostgreSQL suite passed **1,704 tests in 801.772 seconds** before the final retained-card selector and scoped hidden-control CSS corrections. After those corrections, **57 focused checks passed in 38.556 seconds**, including the new future-visit selection case, all 16 new storage cases, existing saved-card/card-setup behavior and two actual Chromium scenarios. The final native inventory is 1,705; a complete local 1,705-test run is not claimed. Earlier expanded verification passed **113 checks in 62.633 seconds**, including five new real PostgreSQL concurrency/reversal/runtime cases, cancellation, scheduled collection, disposal and deployment checks. All six final 1440px/390px images for samples 133–135 were visually inspected. Actual browser assertions cover payment-action/authorization visibility during uncertain storage, reload and no repeated exchange, with no overflow, JavaScript errors, duplicate IDs or nested forms. All 573 Python files pass lint/format checks; model drift, affected JavaScript syntax, diff whitespace, all 270 PNGs/gallery links and all 63 migration pins pass. All 62 previously published migration files/hashes remain unchanged. Provider/storage calls were mocked, external requests blocked, and no customer email delivered; actual hosted fields and processor behavior remain unverified. Prior-commit GitHub checks are recorded separately; checks for this increment run after publication. Features and scheduled collection remain off by default, PR37 stays draft, and no merge, deployment or live financial action occurred.


## 136 — Record a received replacement after a known card failure

After a definite card failure, the existing membership panel offers **Record received payment instead**. This fictional example reviews $1.97 actually received, removal of the unused $0.06 card fee, and $16.02 reserved original visit funds. Zelle alone asks for a bank receipt date and sender; cash/check use today, and gift card requires physical verification. Nothing shown here is a live bank or provider receipt.

| Desktop | Phone |
| --- | --- |
| [![Record a received replacement after a known card failure, desktop](136-paid-visit-manual-review-desktop.png)](136-paid-visit-manual-review-desktop.png) | [![Record a received replacement after a known card failure, phone](136-paid-visit-manual-review-phone.png)](136-paid-visit-manual-review-phone.png) |


## 137 — Received money and the original visit applied once

One confirmation recorded fictional cash $1.97 and completed the original visit application. The first membership total is $17.99, with $16.02 applied as converted visit credit and $1.97 new money. The original $16.47 receipt remains in its history, its retained $0.45 fee stays on the visit invoice, and one membership visit is used. Future installments and card 1234 remain unchanged. No extra card payment or successful-installment receipt email is sent.

| Desktop | Phone |
| --- | --- |
| [![Received money and the original visit applied once, desktop](137-paid-visit-manual-applied-desktop.png)](137-paid-visit-manual-applied-desktop.png) | [![Received money and the original visit applied once, phone](137-paid-visit-manual-applied-phone.png)](137-paid-visit-manual-applied-phone.png) |


## 138 — Known receipt retained while the visit application needs review

A simulated local conversion failure leaves a real recorded fictional check receipt of $1.97 and its unused-fee adjustment intact. Original visit funds remain reserved, no credit or benefit is applied, and the pending page says **Do not collect it again**. Staff can continue applying this visit after resolving the source issue; that action records no second payment. The actual browser scenario then completes successfully using the same receipt.

| Desktop | Phone |
| --- | --- |
| [![Known receipt retained while the visit application needs review, desktop](138-paid-visit-manual-known-receipt-desktop.png)](138-paid-visit-manual-known-receipt-desktop.png) | [![Known receipt retained while the visit application needs review, phone](138-paid-visit-manual-known-receipt-phone.png)](138-paid-visit-manual-known-receipt-phone.png) |


Developer verification: the complete PostgreSQL suite passed **1,730 tests in 841.103 seconds** before the final manual-only cancellation-source safeguard and removal of the redundant application checkbox. After those changes, **111 focused checks passed in 133.077 seconds**, including all 18 manual-receipt cases, seven real PostgreSQL concurrency/reversal/runtime cases, existing card/storage/cancellation behavior, reviewed deployment and two actual Chromium scenarios. The final native inventory is 1,731; a complete local 1,731-test run is not claimed. All six final 1440px/390px images for samples 136–138 were visually inspected. Browser checks cover conditional bank fields, exact receipt/application totals and recovery without duplicate money; no overflow, JavaScript errors, duplicate IDs or nested forms were found. All 577 Python files pass lint/format checks; model drift, JavaScript syntax, diff whitespace, all 276 PNGs/gallery links and all 64 migration pins pass. All 63 previously published migration files/hashes remain unchanged. Provider/storage calls were mocked or blocked, and no customer email was delivered. All four GitHub checks passed for the prior published commit; new checks run after publication. Features/collection remain off by default, PR37 stays draft, and no merge, deployment or live financial action occurred.


## 139 — Recorded bank details on the existing payment page

The actual payment page shows the recorded bank receipt date and sender for the fictional $1.97 Zelle remainder. That date is separate from when staff entered the outcome. An earlier receipt applied to an invoice is identified as such; its original reference, recording staff and timestamp are retained in the payment download. Missing evidence stays blank. Card-provider controls appear for card transactions.

| Desktop | Phone |
| --- | --- |
| [![Recorded bank receipt, desktop](139-recorded-membership-bank-receipt-desktop.png)](139-recorded-membership-bank-receipt-desktop.png) | [![Recorded bank receipt, phone](139-recorded-membership-bank-receipt-phone.png)](139-recorded-membership-bank-receipt-phone.png) |

## 140 — Paid-visit history from the existing export controls

Choose **Paid visit application history** from the existing **Export filtered memberships** controls. The actual downloaded [fictional review CSV](140-paid-visit-application-history.csv) keeps original invoice funds, new membership money, returns, converted credit and fee adjustments in separate columns. Source invoices appear once even when a stopped application was followed by a new purchase. Conversion of a visit toward an existing membership does not reclassify that membership's earlier purchase payment as new money.

| Desktop | Phone |
| --- | --- |
| [![Paid-visit history download, desktop](140-paid-visit-history-download-desktop.png)](140-paid-visit-history-download-desktop.png) | [![Paid-visit history download, phone](140-paid-visit-history-download-phone.png)](140-paid-visit-history-download-phone.png) |

Developer verification: **91 focused PostgreSQL/application/browser checks passed in 62.138 seconds** with the final code and compact layout, including all 15 new history/evidence cases, existing payment views/runtime grants, Zelle/source reports and the actual Chromium download scenario. The browser downloaded both CSV reports and verified original invoice funds $16.47, new money $1.97, converted credit created/applied $16.02, unused fee removed $0.06 and retained original fee $0.45. Receipt/posting counts stayed unchanged; two export audits were recorded. All four final 1440px/390px images were visually inspected, with no overflow, JavaScript errors, duplicate IDs or nested forms. All 580 Python files pass lint/format checks; system checks, model drift, diff whitespace, all 280 PNGs/gallery links, the nine-row actual-download review CSV and all 64 migration pins pass. All 64 previously published migration files/hashes are unchanged. All four GitHub checks passed for the prior published commit; the full suite for this new increment runs after publication. External provider requests were blocked/mocked and no customer email was delivered. Actual Banquest hosted fields/processor behavior remain unverified. Features and collection stay off by default; PR37 remains draft with the broader stage still in progress. No merge, deployment or live financial action occurred.


## 141 — Paid early renewal with an earlier payment needing review

The fictional prepaid renewal has its own **$17.99 cash receipt**, preserved accepted dates and installment marked paid. If required payments on the earlier term later become unresolved, the membership shows **Review**, links to that earlier term and holds new benefit use. This protects the unanswered early-renewal policy rather than treating the recorded renewal payment as missing, cancelling it, refunding it or transferring it to the earlier debt. Existing booking prices and reservations stay intact; the established owner-only exception applies to one booking at a time.

| Desktop | Phone |
| --- | --- |
| [![Paid early renewal needing review, desktop](141-paid-early-renewal-review-desktop.png)](141-paid-early-renewal-review-desktop.png) | [![Paid early renewal needing review, phone](141-paid-early-renewal-review-phone.png)](141-paid-early-renewal-review-phone.png) |

## 142 — Owner reminder for the same paid renewal

The Dashboard links directly to each live paid renewal needing this review. Recording the known earlier required payments clears the reminder and restores normal eligibility; the paid renewal still has exactly its original one $17.99 receipt. Future installments that are not due do not create this hold. Owner complimentary renewals and unrelated ordinary purchases keep their existing rules. No automatic charge, retry, refund, booking repricing or new customer notice is introduced.

| Desktop | Phone |
| --- | --- |
| [![Paid renewal owner reminder, desktop](142-paid-renewal-owner-reminder-desktop.png)](142-paid-renewal-owner-reminder-desktop.png) | [![Paid renewal owner reminder, phone](142-paid-renewal-owner-reminder-phone.png)](142-paid-renewal-owner-reminder-phone.png) |

Developer verification: the complete PostgreSQL suite passed **1,756 tests** before the final own-payment eligibility distinction. The final expanded run then passed **103 checks**, including all eleven new paid-renewal review cases, renewals, reporting, benefit reservations with real PostgreSQL concurrency, per-booking owner decisions and collection preparation. An unpaid or known-failed renewal keeps its ordinary pending-payment state and is never labelled paid. The final native inventory is 1,757; a complete local 1,757-test run is not claimed. A separate actual Chromium scenario verified the paid receipt, parent link, Dashboard reminder and its disappearance after known earlier payments were recorded, without a second renewal receipt. All four final 1440px/390px images were visually inspected, with no overflow, JavaScript errors, duplicate IDs or nested forms. All 582 Python files pass lint/format checks; system checks, model drift, whitespace, all 284 PNGs/gallery links and all 64 migration pins pass. All 64 published migration files/hashes and the earlier CSV sample are unchanged. All four GitHub checks passed for the prior published commit; this increment starts its own checks on publication. External requests were blocked/mocked and no customer email was delivered. Provider behavior remains unverified. Features and collection remain off by default; PR37 stays draft, with the broader stage still in progress. No merge, deployment or live financial action occurred.


## 143 — Renew several memberships on one page

From the customer’s **Memberships** card, choose **Renew memberships together**. The same page shows the original records, places available, renewal type/count/term, start dates, accepted terms and combined amount. This fictional example renews one Subscription place for **$17.99** beginning **January 31, 2028**, and one Unlimited place for **$39.99** beginning **March 1, 2028**. Their dates follow their separate original expirations. The live **$57.98** is an amount to record; preview has not recorded received money.

| Desktop | Phone |
| --- | --- |
| [![Combined renewal review, desktop](143-combined-renewal-review-desktop.png)](143-combined-renewal-review-desktop.png) | [![Combined renewal review, phone](143-combined-renewal-review-phone.png)](143-combined-renewal-review-phone.png) |

## 144 — One final received-payment action, separate renewal history

After staff accepts the reviewed terms, verifies the full actual cash/check payment and confirms, the page shows **$57.98 received**, its date, the two allocations and links to each renewed record. Each membership keeps its own accepted terms, dates, prices and history. One confirmation is prepared for the group; it is not marked delivered. Reload and return links create no further receipt. Each record shows the shared confirmation’s actual status.

| Desktop | Phone |
| --- | --- |
| [![Combined renewals recorded, desktop](144-combined-renewals-recorded-desktop.png)](144-combined-renewals-recorded-desktop.png) | [![Combined renewals recorded, phone](144-combined-renewals-recorded-phone.png)](144-combined-renewals-recorded-phone.png) |

## 145 — Split one original record between types or terms

**Split this renewal** creates another entry for the same original record. Here its two available places are selected as one Subscription and one Unlimited place. The combined count cannot exceed the original places still available. The other original record is unselected. Different types/terms are explicit choices, while the original history remains unchanged. This captured preview creates no renewal or payment.

| Desktop | Phone |
| --- | --- |
| [![Split renewal places preview, desktop](145-split-renewal-places-preview-desktop.png)](145-split-renewal-places-preview-desktop.png) | [![Split renewal places preview, phone](145-split-renewal-places-preview-phone.png)](145-split-renewal-places-preview-phone.png) |

This first combined checkout accepts **positive, verified cash or check**. Monthly rows can select an existing permitted card for their own future installments; no card is charged by the grouped received-payment action. Card/Zelle/gift-card/customer-credit funding, new-card storage and a renewal with no payment due use the existing individual workflows for now. Group funding by those methods remains unfinished. Ordinary minimums, owner-only minimum exceptions and the existing earlier-payment review safeguards still apply. No membership records are silently consolidated, and no booking, capacity reservation or waiver is created by this membership-only checkout.

Developer verification: the complete PostgreSQL suite passed **1,795 tests** with the final application code, including all 38 new combined-renewal cases. The preceding focused run passed **84 checks**, covering existing renewals/parent review, actual concurrent submissions, used/unused schema reversal, runtime grants, read-only history and deployment compatibility. A separate final Chromium scenario exercised split preview, distinct start dates, actual form confirmation, reload and return links at 1440px/390px. It recorded fictional $17.99 + $39.99 once, prepared one shared confirmation and left original quotes intact; preview created no payment, booking or benefit usage. All six final images were visually inspected with no overflow, JavaScript errors, duplicate IDs or nested forms. All 589 Python files pass lint/format checks; system checks, model drift, JavaScript syntax, whitespace, all 290 PNGs/gallery links and all 65 migration pins pass. All 64 previously published migration files/hashes and the earlier CSV sample remain unchanged. All four GitHub checks passed for the preceding published commit; new checks run after publication. External requests were blocked/mocked and no customer email was delivered. Provider behavior remains unverified. Features and scheduled collection remain off by default; PR37 stays draft and the broader stage continues. No merge, deployment or live financial action occurred.


## 146 — Find another renewal without losing selected details

For a customer with more available records, search by membership number or type, or choose **Show more memberships** on the same page. Selected renewals retain their counts, types, durations, monthly/pay-in-full choices, future cards and payment method. This fictional example keeps one Subscription place billed monthly for two months, its future card and **$17.99 check** first payment while finding another record. Unselected records show their summary until chosen. Fully renewed places do not hide later available records.

Browsing creates no renewal, receipt, booking or benefit use. The reviewed total refreshes, and staff reviews the current terms and verifies received money again before final confirmation. Incomplete selected details remain visible with their error.

| Desktop | Phone |
| --- | --- |
| [![Find another renewal, desktop](146-search-renewals-keep-selection-desktop.png)](146-search-renewals-keep-selection-desktop.png) | [![Find another renewal, phone](146-search-renewals-keep-selection-phone.png)](146-search-renewals-keep-selection-phone.png) |

Developer verification: the final expanded PostgreSQL run passed **109 checks in 48.736 seconds**, including eight new renewal-list cases, combined and individual renewal services/views, real concurrency, notices and booking renewal prompts. The earlier focused run passed 69 checks. Two actual Chromium scenarios passed in 13.413 seconds: search/show-more retained the selected monthly details, future card, payment method and request identity without recording money; final combined confirmation recorded fictional $17.99 + $39.99 once, with one shared prepared confirmation and no duplicate on reload. All eight refreshed/new desktop/phone images were visually inspected, with no overflow, JavaScript errors, duplicate IDs or nested forms. All 591 Python files pass lint/format checks; system checks, model drift, JavaScript syntax, whitespace, all 292 PNGs/gallery links and all 65 migration pins pass. All 65 published migration files/hashes and the earlier CSV sample remain unchanged. The published baseline passed the complete 1,795-test suite; the current native inventory is 1,803, and a complete local 1,803-test run is not claimed. All four GitHub checks passed for the prior published commit; new checks run after publication. External requests were blocked/mocked and no customer email was delivered. Actual Banquest behavior remains unverified. Features and scheduled collection stay off by default, PR37 stays draft and the broader stage continues. No merge, deployment or live financial action occurred.


## 147 — Review one Zelle transfer for several renewals

On the same combined renewal page, choose **Zelle received**, enter the actual bank receipt date and sender, and review the full amount before final confirmation. This fictional example records one **$57.98** transfer received **October 29**, allocated as **$17.99 Subscription** and **$39.99 Unlimited**. Their separate January 31 and March 1 renewal starts stay intact. Bank details and selected rows survive Show more; preview records no receipt or renewal. Staff explicitly verifies the transfer in the business bank account.

| Desktop | Phone |
| --- | --- |
| [![Combined renewal Zelle review, desktop](147-combined-renewal-zelle-review-desktop.png)](147-combined-renewal-zelle-review-desktop.png) | [![Combined renewal Zelle review, phone](147-combined-renewal-zelle-review-phone.png)](147-combined-renewal-zelle-review-phone.png) |

## 148 — One verified transfer with separate allocations

After one explicit confirmation, the receipt shows **$57.98 received**, its original bank date/sender and each membership allocation. One immutable source backs both allocations. They are portions of the same transfer; there is no additional aggregate financial posting or second bank receipt. Reload creates no duplicate, and one combined confirmation is prepared. Cash/check still use today without another receipt-date step.

| Desktop | Phone |
| --- | --- |
| [![One Zelle transfer allocated, desktop](148-one-zelle-transfer-allocated-desktop.png)](148-one-zelle-transfer-allocated-desktop.png) | [![One Zelle transfer allocated, phone](148-one-zelle-transfer-allocated-phone.png)](148-one-zelle-transfer-allocated-phone.png) |

## 149 — Original transfer visible from either membership payment

The existing payment page identifies **$17.99 allocated from one verified $57.98 transfer**, retains its bank date/sender and links back to the complete transfer and allocations. Payment exports identify the shared source while the additive transaction-money columns contain only the allocated portions. The repeated original-transfer total is explicitly labelled reference-only. Original receipt history remains intact if one allocation is later refunded through the existing owner-confirmed return workflow.

| Desktop | Phone |
| --- | --- |
| [![Zelle allocation original source, desktop](149-zelle-allocation-original-source-desktop.png)](149-zelle-allocation-original-source-desktop.png) | [![Zelle allocation original source, phone](149-zelle-allocation-original-source-phone.png)](149-zelle-allocation-original-source-phone.png) |

This records a manually verified transfer; it does not connect to the bank or send a transfer/refund. A payment already recorded elsewhere stays in its existing application workflow. Card/gift-card/customer-credit/split funding and a group with no payment due remain unfinished, with individual renewal workflows retained. Monthly renewals keep their separately accepted future card schedules.

Developer verification: The complete PostgreSQL suite passed **1,826 tests in 1,028.921 seconds** with the final application code. The final focused run passed **46 checks in 61.324 seconds**, including all 16 new bank-funding cases, five real transaction/concurrency/reversal cases and reviewed deployment compatibility. Three final actual Chromium scenarios passed in 19.880 seconds, covering cash confirmation, same-source split preview, search/show-more with preserved monthly selections, and the new Zelle flow: one fictional $57.98 verified transfer, $17.99/$39.99 allocations, actual October 29 bank date and sender preserved during browsing, one unsent shared confirmation, reload without duplication, shared-source payment links and $57.98 total in transaction exports. All fourteen refreshed/new 1440px/390px images were visually inspected with no overflow, JavaScript errors, duplicate IDs or nested forms. All 594 Python files pass lint/format checks; system checks, model drift, JavaScript syntax, whitespace, all 298 PNGs/gallery links and all 66 migration pins pass. All 65 previously published migration files/hashes and the earlier actual-download CSV sample remain unchanged. All four GitHub checks passed for the prior published commit; new checks run after publication. External provider/storage requests were mocked or blocked, no bank API was called and no customer email was delivered. Actual Banquest behavior remains unverified. Features/collection remain off by default, PR37 stays draft and broader stage work continues. No merge, deployment or live financial action occurred.


## 150 — Review corrected dates without another page

An unused, paid prepaid term is corrected from October 31–January 30 to November 5–February 4. Start date, reason, Yes/No updated-email choice, current/new dates and final save remain on the existing overview. Changing the review clears the customer-agreement checkbox. Preview creates no purchase, payment or correction.

| Desktop | Phone |
| --- | --- |
| [![Membership date review, desktop](150-membership-date-review-desktop.png)](150-membership-date-review-desktop.png) | [![Membership date review, phone](150-membership-date-review-phone.png)](150-membership-date-review-phone.png) |

## 151 — Corrected dates and original evidence together

The same membership number now shows its corrected benefit dates. Expandable date history retains the original term, reason, actor, time and actual update-email state. The $107.94 receipt, original contract, original cycle identities and payment schedule are retained. No additional money is recorded. Future bookings, renewal timing, notices and unused-term refund suggestions use the corrected calendar.

| Desktop | Phone |
| --- | --- |
| [![Corrected membership history, desktop](151-membership-corrected-date-history-desktop.png)](151-membership-corrected-date-history-desktop.png) | [![Corrected membership history, phone](151-membership-corrected-date-history-phone.png)](151-membership-corrected-date-history-phone.png) |

## 152 — Saved history stays available when updates are paused

With membership sales paused, the existing history and recorded funds remain readable. Editing and payment actions remain gated. This sample is an operational history view, not a purchase or charge.

| Desktop | Phone |
| --- | --- |
| [![Membership history while paused, desktop](152-membership-history-during-pause-desktop.png)](152-membership-history-during-pause-desktop.png) | [![Membership history while paused, phone](152-membership-history-during-pause-phone.png)](152-membership-history-during-pause-phone.png) |

This first correction path supports standalone prepaid or complimentary memberships before their effective start and before any booking benefits were assigned. Used, expired, monthly-payment, linked renewal/addition and unresolved-funding cases still require further development; these screenshots do not imply those paths are finished. Updated confirmations are prepared only when explicitly selected, never delivered by these checks. Earlier unattempted date notices are cancelled as retained evidence; attempted or uncertain delivery is not automatically retried.


Developer verification: the complete PostgreSQL suite passed **1,858 tests in 1,106.692 seconds** with the final application code. The related screen/accounting run passed **119 checks in 46.681 seconds**; the final boundary/browser run passed **36 checks in 15.891 seconds**, including actual desktop/phone review, save, reload, safe non-JSON failure/recovery and paused-history navigation; committed correction/reservation races; runtime grants; and used/unused reversal and release compatibility. Tests cover a booking after the original expiry but inside the corrected term, the current customer summary, unchanged original cycle IDs/receipts and credit alerts at corrected expiry without expiring the credit. All six new 1440px/390px images were visually inspected with no overflow, JavaScript errors, duplicate IDs or nested forms. All 602 Python files pass lint/format checks; system checks, model drift, JavaScript syntax, whitespace, all 304 PNGs/gallery links and all 67 migration pins pass. All 66 previously published migration files/hashes and the earlier actual-download CSV remain unchanged. All four GitHub checks passed for the preceding published commit; this update starts its own checks after publication. Provider/storage requests were mocked or blocked and no customer email was delivered. Actual Banquest behavior remains unverified. Features and collection stay off by default, PR37 stays draft and broader stage work continues. No merge, deployment or live financial action occurred.


## 153 — Split a known failed remainder on the same page

After a known failed first-card request, expand **Split the remaining payment** on the membership page. This fictional example applies **$0.97 cash** and requests **$1.00 card principal + $0.03 processing fee**. Only the unused $0.03 of the original fee is removed. The revised first total is **$18.02**. Preview creates no receipt or card request. Changed amounts, cards or bank details require the current review and both confirmations again.

| Desktop | Phone |
| --- | --- |
| [![153 — Split a known failed remainder on the same page, desktop](153-split-remainder-review-desktop.png)](153-split-remainder-review-desktop.png) | [![153 — Split a known failed remainder on the same page, phone](153-split-remainder-review-phone.png)](153-split-remainder-review-phone.png) |


## 154 — Received money stays recorded while the card is pending

The actual **$0.97 cash receipt** is committed before preparing the separate **$1.03 card request**. Both have direct history links. The original **$16.02** visit funds stay reserved; the original visit is unchanged and no membership benefit has yet been used. Reload records nothing again. The future installment card authority remains independent.

| Desktop | Phone |
| --- | --- |
| [![154 — Received money stays recorded while the card is pending, desktop](154-received-portion-card-pending-desktop.png)](154-received-portion-card-pending-desktop.png) | [![154 — Received money stays recorded while the card is pending, phone](154-received-portion-card-pending-phone.png)](154-received-portion-card-pending-phone.png) |


## 155 — Apply the paid visit after exact funding is confirmed

After the simulated card success and completed application, the same record shows **$2.00 total new money received** separately from **$16.02 customer credit applied**. The original $0.45 card fee is retained, original gross receipts remain history, and the visit uses its normal membership benefit once. The declined attempt remains visible without counting as received money. One combined confirmation is prepared, with no customer delivery in this test.

| Desktop | Phone |
| --- | --- |
| [![155 — Apply the paid visit after exact funding is confirmed, desktop](155-split-funded-visit-applied-desktop.png)](155-split-funded-visit-applied-desktop.png) | [![155 — Apply the paid visit after exact funding is confirmed, phone](155-split-funded-visit-applied-phone.png)](155-split-funded-visit-applied-phone.png) |


## 156 — Continue after card preparation was interrupted

An interrupted card preparation leaves the **$0.97 received portion recorded** and states clearly that no remaining card request was created. The next explicit action requests only **$1.03**, never the cash portion again. A known decline permits another explicit remaining-card request; an unknown result requires review of the existing transaction and blocks another request.

| Desktop | Phone |
| --- | --- |
| [![156 — Continue after card preparation was interrupted, desktop](156-received-portion-card-not-requested-desktop.png)](156-received-portion-card-not-requested-desktop.png) | [![156 — Continue after card preparation was interrupted, phone](156-received-portion-card-not-requested-phone.png)](156-received-portion-card-not-requested-phone.png) |

This bounded path accepts one verified cash/check/Zelle/physical-gift portion and a positive eligible saved-card remainder, within the existing same-day paid-visit rules. Zelle retains the actual bank receipt date and sender. Gift cards require staff verification; no gift provider or bank call is made. It does not automatically retry a card or grant future installment consent. Cancellation reconciles only actually received money and removes any never-collected card principal and unused fee without inventing a refund. Broader source/date exceptions and new-card entry within an already-saved split remain unfinished.

Developer verification: the complete PostgreSQL suite passed **1,887 tests in 1190.246 seconds** with the final application code. The related cancellation/recovery/deployment run passed **98 checks in 66.442 seconds**; six actual-commit concurrency/reversal cases passed in **11.097 seconds**. The final **18-check run in 36.627 seconds** includes the 16 split service cases and two actual Chromium desktop/phone scenarios. It verifies read-only preview, changed-consent reset, non-JSON failure/recovery, exact separate receipts, original funds/benefits untouched before full funding, preserved known receipts after interrupted card preparation, explicit remainder-only retries and unknown-outcome blocking. Cancellation tests cover partial/full funding, actual partial refunds and exact unused-fee removal. Raw SQL rejects forged amounts, fee reductions and rewritten evidence. Used schema reversal is refused; unused reversal restores all six prior function definitions and reapplies.

All eight new 1440px/390px images were visually inspected with no overflow, JavaScript errors, duplicate IDs or nested forms. All **609 Python files** pass lint/format checks; system checks, model drift, JavaScript syntax, whitespace, all **312 PNGs/gallery links** and **68 migration pins** pass. All **67 previously published migration files/hashes** and the earlier actual-download CSV remain unchanged. All four GitHub checks passed for the preceding published commit; this update starts new checks after publication. Provider/storage requests were mocked or blocked, no bank or gift-provider API was called and no customer email was delivered. Actual Banquest behavior remains unverified: a fresh public hosted-field SDK GET returned a workspace-proxy 403; its tokenization host is absent from the current allowed-host list. No network settings were changed. Features and scheduled collection remain off by default, PR37 stays draft and broader Stage3 work continues. No merge, deployment or live financial action occurred.
