# Active memberships — review gallery

Draft [PR #37](https://github.com/MonkeyDo-Site/MonkeyDoWebsiteNewCode/pull/37). These are actual application pages with fictional review data, captured at 1440px desktop and 390px phone widths. All names, card references and payment outcomes are synthetic. No card was charged and no customer email was delivered.

Purchases, booking benefits, payment resolution and customer credit use the existing combined screens. Membership features and scheduled collection remain **off by default**, and PR #37 remains a draft while the remaining scope is implemented. Actual Banquest hosted fields and processor outcomes remain unverified; provider areas in samples 13 and 68 are explicitly labelled placeholders.

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
| **New: customer review and reservation of a released Unlimited benefit** | **77–78** |

Each sample includes desktop and phone images. See the [owner testing guide](../../ACTIVE_MEMBERSHIP_OWNER_TESTING.md) for expected actions and the explicit unfinished scope. Combined Zelle/split tenders, multi-cohort checkout, already-paid first-purchase conversion, broader credit returns/redemption and remaining owner corrections are still being implemented.

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

## Checked so far

The complete **1,308-test PostgreSQL suite passes** (423.205s), followed by one final native receipt/history check after its wording-only label update. Eighteen new cases cover private ownership, existing/new customers, current verification, exact prices and actual Zelle, immutable original evidence, native/CSRF boundaries, stale/duplicate confirmation, rollback, historical adult allowances and two real PostgreSQL races. Original financial/queue/migration/runtime checks remain green.

All **78 desktop/phone pairs** have passed browser overflow/JavaScript checks. New samples 77–78 are four actual captures of one read-only price review and explicit confirmation: one reserved unused benefit, no new payment/posting/email/provider action, and unchanged original card, waiver and deadline. Ruff/format (502 Python files), model drift, whitespace, all 156 image links and all 48 unchanged reviewed migration hashes pass. Detailed milestone evidence remains in the [implementation record](../../ACTIVE_MEMBERSHIP_IMPLEMENTATION.md).

Implementation continues while the owner reviews. The [owner testing guide](../../ACTIVE_MEMBERSHIP_OWNER_TESTING.md) identifies functional checks, unfinished scope and provider limitations. No merge, deployment, live financial action or external email delivery is included; release requires explicit authorization.
