# Active memberships — owner testing guide in progress

Draft [PR #37](https://github.com/MonkeyDo-Site/MonkeyDoWebsiteNewCode/pull/37) remains under development. The [gallery](reviews/active-memberships/README.md) uses fictional records and simulated card outcomes; no live payment or email delivery was performed. Review images now. The steps below are for a later authorized staging release, with test customers and Banquest test cards. This is not a deployment or live-payment instruction.

## Start with these representative pages

For a first visual review, the [gallery](reviews/active-memberships/README.md) has direct desktop/phone pairs:

| What to review | Samples |
| --- | --- |
| Staff purchase and the paid overview | [01](reviews/active-memberships/README.md#01--purchase-membership-on-one-page), [02](reviews/active-memberships/README.md#02--active-membership-after-confirmed-payment) |
| Existing combined booking, edit and arrival screens | [04](reviews/active-memberships/README.md#04--member-aware-booking-on-the-existing-combined-page), [05](reviews/active-memberships/README.md#05--edit-member-booking), [06](reviews/active-memberships/README.md#06--member-arrival) |
| Customer membership checkout | [67](reviews/active-memberships/README.md#67--customer-membership-purchase-on-one-page) |
| Renewal and addition | [08](reviews/active-memberships/README.md#08--renew-existing-places), [09](reviews/active-memberships/README.md#09--add-places-with-their-own-term) |
| Apply an already paid visit | [113](reviews/active-memberships/README.md#113--apply-a-paid-visit-toward-a-first-membership) |
| Preserve received money if the remaining card request is interrupted | [153–156](reviews/active-memberships/README.md#153--split-a-known-failed-remainder-on-the-same-page) |

The later samples cover particular accounting and recovery cases. They do not require reviewing the entire gallery before commenting on the main screens. The implementation remains under development; use the detailed scenarios below for later authorized staging tests.

## Public initial membership purchase — samples 67–72

For a later authorized staging test, open **Membership → Choose a membership**. The feature remains disabled by default. Use fictional contact details and provider test cards only after the separate provider verification/release steps.

| Scenario | Actions | Expected result |
| --- | --- | --- |
| Existing customer | Enter phone and verify last name/email. | The approved profile-matching rules apply. Plan, price, card, agreement and final purchase remain on one checkout page. |
| New customer | Enter an unmatched phone and new contact details. | One customer/checkout identity is saved; no booking or payment exists yet. New-card entry is selected automatically when no saved card is available. |
| Conflicting profiles | Enter a phone and another profile's email. | The customer explicitly verifies/selects a profile before checkout. Neither profile is silently overwritten. Duplicate-email recovery stays in the membership flow. |
| Current price and terms | Change type, places, term, billing or start date. | Amount/schedule refresh together. A changed review requires acceptance again. Ordinary public terms remain at least three whole months. |
| Final confirmation | Accept the current agreement and confirm with a saved or new card. Reload/resubmit. | Exact card authorization precedes one purchase and one first-payment request. No visit, admission hold or waiver is created by this membership-only action. |
| Uncertain storage/payment | Interrupt card storage or simulate an uncertain payment. Reload/check status. | No repeated storage/financial POST or new purchase is requested. Unconfirmed funds remain zero; unknown storage blocks discarding the checkout. Actual hosted fields are unverified in the gallery. |
| Known outcome | Confirm a successful provider result through the permitted test workflow. | The membership receipt shows actual received funds, the purchased term and one queued confirmation. A visit is booked separately. |
| Expired accepted checkout | Return after twenty minutes or after verified contact details change. | The same private browser opens one verification form: phone plus last name or email. Only the customer who purchased can reopen the receipt. The page says no new payment was requested; original card/purchase/payment evidence and the expired financial deadline remain unchanged. Another browser without the original private purchase context requires assistance. |

## Current functional scenarios

| Scenario | Actions | Expected result |
| --- | --- | --- |
| New purchase | Select a customer, type, places, whole-month term and monthly/prepaid billing. Review the amount and accepted terms. Change the count before confirming. | The price and schedule update together. A changed selection requires accepting the current terms again. Only final confirmation saves the purchase and requests/records payment. |
| New membership card | On purchase/renew/add, choose Enter a new card and record the customer's Yes/No future-visit choice. Accept the current terms and use the final confirmation. | Secure storage happens first, followed by one explicit purchase. Unknown storage outcomes stop the purchase and survive reload without another exchange. No unrelated booking policy consent is recorded. Actual provider fields still require separate verification. |
| Actual payment truth | Compare pending and paid purchase overviews. | Pending/unknown card outcomes add no money and activate no benefits. Confirmed receipts appear separately from the next installment. |
| Combined member booking | Create a booking for a verified member, change counts and review price, waiver and card controls. | Member prices appear on the existing combined screen. Capacity counts, 30-minute backend holds, closure and owner-price controls remain. Benefit reservations occur only on confirmed booking. |
| Member arrival | Review actual counts, waivers and payment, then confirm arrival. | Included visits create no fabricated receipt. Paid remaining admissions/socks and cancellation fees retain their correct separate treatment. Usage is saved on confirmation. |
| Edit or move | Change attendees or session, including a move to another membership month. | The new estimate appears before saving. Saving transfers benefit reservations and preserves the old quote/history. No silent changes to already paid attendance. |
| Released Unlimited place | Cancel the first same-day booking, then open another already-confirmed booking. | The existing price stays until Apply available Unlimited benefit is explicitly selected and saved. |
| Renewal | Open Renew from an existing membership. Renew fewer places or change type. | Early renewal starts after expiry. Renewal within seven days after expiry starts on the actual date with a one-month minimum; later renewal normally requires three months. Original dates/prices/history remain intact. |
| Customer renewal link | On an existing membership, create its private renewal link. Open it without a staff login and enter the matching phone/last name. Review the renewal, card, amount and terms together. | No customer membership data is displayed before verification. The link lasts 30 days but does not extend the seven-day renewal grace rule. Final confirmation records customer acceptance and requests only this renewal's first payment. |
| Duplicate customer renewal | Submit the same private renewal twice, including from two verified browser sessions. | Both return the original renewal. The same places cannot be renewed twice through different links, and only one initial payment is requested. Pending funds are never described as received. |
| Addition | Open Add membership places. | Additional places have their own term, accepted price, schedule and ordinary three-month initial minimum. |
| Failed installment | Open Resolve payment or update membership card. Choose the installment and card/cash/check/Zelle/verified physical gift card. | Preview creates no payment. The final button states the action and amount. Noncard requires verified receipt and removes only the unused card fee for that balance. |
| Uncertain installment | Open payment controls while an existing outcome is unknown or processing. | A replacement charge and manual receipt are blocked. Open the previous payment for review. Changing a card does not bypass this block. |
| Card update | Select an available customer-owned card or Enter a new card on the membership overview. For new entry, record the customer's Yes/No future-visit choice, authorize the remaining payments, then Save and use membership card. | A new mandate is retained in history. No charge is requested; scheduled dates and earlier payment outcomes remain unchanged. Unknown storage blocks confirmation; Check card setup and reload inspect the existing outcome without another exchange. A changed billing revision requires a fresh review. |
| Owner attention | Resolve an overdue installment, then return to the overview and Dashboard. | Actual funds increase once, benefits become available when all required dues are current, and the settled installment notice clears. No successful-installment customer email is sent. |
| Overdue booking decision | As owner, open Edit booking or Start arrival for a booking with reserved benefits and unpaid membership dues. Choose ordinary admission prices or honor the reserved benefits, and record a reason. | Preview changes no booking or benefit history. Final confirmation records the owner decision. Ordinary prices recalculate with counts; honoring benefits keeps normal quota/fees and applies only to this booking/session. Other bookings and unpaid dues remain separate. Staff cannot create this exception. |
| Confirm after typing | Type the owner reason, wait for the estimate, then click Confirm arrival once. | Leaving unchanged text does not disable the button through a duplicate preview. One confirmation records the reviewed arrival; changed/stale entries still require review. |
| Custom $0 admissions | Set an owner admissions price of $0 without selecting complimentary, with no socks/payment due, then review arrival. | The button and saved payment status say no payment due. The booking is not labelled complimentary and no receipt or membership usage is fabricated. |

## Cancellation and refunds

| Scenario | Actions | Expected result |
| --- | --- | --- |
| Combined cancellation review | On the membership overview, expand Owner: cancel membership and review any refund. Compare immediate/end-current-month dates and change the owner refund amount. | Review changes no records. Actual funds, original processing fees, refund sources, stopped future installments and affected bookings appear together. The suggested unused-period amount can be changed within actual available membership funds. |
| Owner confirmation | Enter the reason, choose email Yes/No, and select refund due or the explicit return action. Confirm once. | One immutable cancellation records the owner/date/reason. An initial-commitment cancellation requires its additional approval. Unknown/in-flight payments stop cancellation for reconciliation. Unstarted payment jobs stop; earlier accepted dues remain separately reviewable. Ordinary staff cannot cancel/refund. |
| Refund due | Choose Record refund due; handle it afterward. | No return or refund POST is claimed. Dashboard and overview show the actual remaining liability until confirmed returns reduce it. Pending/unknown refunds remain due and block a replacement attempt. |
| Partial noncard return | Actually return part of the refund, enter that amount and confirm it was returned. | Record only that amount against its original source. Original receipts, recorded refunds, money held and remaining refund due stay separate. A partial return keeps the Dashboard reminder. Repeating the same confirmation creates no duplicate posting. |
| Card refund | Explicitly request an owner-approved card refund against the original receipt. | Queued/pending funds are not returned funds. A verified successful outcome records one return; original processing fees are retained. A definite decline permits a new explicit owner attempt; unknown outcomes require reconciliation and never automatic retry. |
| Refund already in Banquest | Choose Record a refund already completed in Banquest. Enter its exact amount/reference and confirm completion. | A GET verifies the successful refund, original transaction and amount; no new financial POST is sent. Duplicate references and mismatches are rejected. Only the imported amount reduces the liability. Unknown existing attempts must be reconciled through their own record first. |
| External return reported | Compare a known external return with an unstarted outgoing refund. | The outgoing refund stops before dispatch. The overview requests recording the completed return. A later distinct unrecorded return reopens owner attention; a notification for an already recorded refund does not invent a new issue. |
| Existing member booking | Cancel a membership with a future reserved visit, then open that booking. | Its original quote and reservation remain intact and Dashboard requests review. Staff cannot silently reprice it. An owner may explicitly select ordinary prices; an earlier honor-overdue decision cannot extend benefits beyond the cancellation date. |
| Cancellation email | Choose Yes and compare refund due, partial return and completed return before delivery. | One delivered cancellation notice reports the actual status. An unsent notice can be superseded by a fresh accurate snapshot; earlier text remains in history. After sending begins, a later refund creates no separate refund-only email. Choosing No queues none. |

## Customer credit

| Scenario | Actions | Expected result |
| --- | --- | --- |
| Review available credit | Open a membership with recorded customer credit and an unpaid due installment. Expand Apply customer credit to a due installment; change the amount. | Unpaid membership principal, available credit, selected credit, remaining principal and remaining card fee stay on one page. Preview spends nothing. |
| Apply credit once | Confirm the reviewed amount, then repeat the same submission. | One immutable application allocates existing funds. Actual money received does not increase and no card charge or new receipt is created. Duplicate confirmation returns the same result. |
| Partial credit | Apply $16.02 to $17.99 of unpaid membership principal. | $1.97 remains, plus $0.06 if paid by card: $2.03. Only the still-unpaid card fee is adjusted. Existing payment controls collect the actual remainder separately. |
| Full installment covered | Apply enough credit to cover the unpaid membership principal. | The installment is settled without inventing a payment. Unpaid card fees on the credit-funded amount disappear; paid earlier fees remain. Benefits return only when all required dues are current. No successful-installment customer receipt is sent. |
| Pending or unknown payment | Try applying credit while an earlier payment is in flight or uncertain. | Reconciliation is required before using credit. An unstarted old full charge can be stopped by explicit credit confirmation; concurrent dispatch cannot charge it after the credit was applied. |
| Original visit/history | Review gallery sample 28 and the customer credit history. | The $16.47 original card receipt remains. Replaced admission and both approved taxes yield $16.02 credit; the $0.45 fee remains. Source/target histories are linked and the same original funds cannot also be refunded. This sample uses the reconciliation service after an already paid same-day membership purchase; combined first-purchase conversion is unfinished. |
| Source return reported | Inspect credit linked to an original card payment with an unrecorded provider return. | Unspent credit is held for owner review, rather than shown as available. Affected applications pause benefits and further collection, including old queued dispatch. Existing allocations, receipts and booking prices remain unchanged. Dashboard links to the original source payment. |
| Credit after expiry | Leave some credit unspent when its linked membership ends. | The credit carries forward. Owner Dashboard identifies the remaining available credit; spending it clears the reminder. Credit held for a source-payment issue has its separate reconciliation reminder. |

| Owner credit removal | On the customer page, expand Owner: correct unused credit, enter a positive amount and reason, and review before confirming. | Only available unused credit can be removed. The resulting balance is visible before confirmation. Original receipts, transferred funds and used credit remain intact; no refund or new payment is recorded. Staff cannot perform the correction. |
| Bounded restoration | Choose Restore earlier removal, select that removal, enter a partial amount and reason, then confirm. | Only the still-unrestored amount from that removal can return. Repeating the submission creates no duplicate. Source-held funds remain held. Earlier removals and later restorations remain in the customer history with owner/time/reason. |
| Credit correction concurrency | Attempt spending the same credit while removing it, or submit two restorations for the same remaining removed amount. | Only one competing action succeeds; duplicate confirmation with the same key returns its original result. Stale reviews require reviewing the current balance again. |

## Membership list and operational exports

| Scenario | Actions | Expected result |
| --- | --- | --- |
| Search and filter | Search by family name, formatted phone, email or #M number; combine type/status and expiry. | All history remains accessible by default. Possible spelling matches are labelled. Status matches the overview's actual funding/credit state. Invalid dates show errors and no broad fallback results. |
| Clear expiry and paging | Filter a type/status and expiry, then Clear expiry or change rows per page. | Clear expiry keeps the unrelated choices; paging preserves filters. A cancellation's effective end is distinct from the original accepted end. |
| Export matching records | Expand Export filtered memberships and download Memberships, Payment transactions or Benefit usage. | Every matching membership is included across all pages. Actual recorded money stays separate from requested/pending amounts and credit. Benefit reservation/use/release events remain in history. Comments, waiver files and payment-storage secrets are excluded. |
| Permissions and history | Give a staff member the export permission explicitly; compare permitted report choices, then open export history as owner. | Normal membership powers stay available in the staff editor. Exports are not a default staff grant. Payment and benefit reports also require their own viewing permissions; only the owner sees paginated export history, with exact filters/count/actor/time. |

## Approved expiry and grace notices

| Scenario | Actions | Expected result |
| --- | --- | --- |
| Exact timing | Review gallery 36 and 37, then check Renewal notices on the overview. | Expiry notice is due five days before the actual cohort end. Grace notice is due on end + six days, with the deadline tomorrow at end + seven. Dates use New York, including midnight/DST boundaries. Viewing history queues nothing. |
| Protected link | Open a notice link without a staff session; try unmatched details, then the matching phone/name. | No customer membership details appear before verification. Within grace, the new term can be one month and starts on the actual renewal date. A still-valid 30-day link after grace normally requires three months; it grants no gap benefits. |
| Renew or cancel before dispatch | Queue the fictional notice, then renew all its places or cancel the membership before its mail job claims it. | The unsent notice is withdrawn without contacting the mail provider. A partial renewal changes the remaining-place wording through a new immutable snapshot. Earlier text stays in history. |
| Contact correction | Change the current email before dispatch, including correcting it back to a previously superseded address. | Only one current queued snapshot remains. Earlier unsent attempts stay withdrawn; customer text and recipient history are never overwritten. No attempted/unknown delivery is automatically repeated. |
| Payment review | Compare overdue cohorts, source-held credit and a reported unrecorded original card return. | A renewal notice is not sent while the original payment needs resolution. No customer failed-installment message is introduced. Existing owner attention remains separate. |
| Delayed or uncertain mail | Run a claim after its notice day, or simulate a lost provider response. | A stale queued notice is withdrawn, especially the grace notice saying tomorrow. Unknown/sent/failed attempts do not generate another automatic notice. Queued does not mean delivered. |

Developer/operator preparation uses `prepare_membership_notices --dry-run --limit 20` to inspect the bounded due batch without queuing. The normal bounded worker prepares due notices before consuming its existing queue after the active-membership feature is explicitly enabled. No command was used here to deliver customer email. The feature remains default-off until the authorized release.

## Direct membership payment reconciliation

| Scenario | Actions | Expected result |
| --- | --- | --- |
| Provider return not recorded | Review sample 39 and open the original payment from the membership overview. | Review status and unavailable benefits appear alongside recorded money received. No paid-in-full label or zero-dollar collection action appears. Existing bookings, quotes and reservations remain intact. |
| Later charge already queued | Report an unresolved return on an earlier receipt before the next queued installment dispatches. | The unstarted charge is canceled before any provider financial request. Cash/check/Zelle collection and credit application also wait for owner reconciliation across this cohort. Another independent paid cohort keeps its eligibility. |
| Reconcile actual return | Record the verified completed refund against its original source, then inspect the membership again. | The source-review hold clears only when the reported return is covered. Any remaining installment shortfall stays unpaid; duplicate observations of that same refund do not create another hold or another refund. A different later unrecorded return reopens review. Ordinary declines still permit explicitly confirmed manual retries. |
| Unsent confirmation | Report an unresolved source return after purchase confirmation was queued but before dispatch. | The original frozen message is withdrawn without mail delivery. No message claims membership readiness while the payment source needs owner reconciliation. |

## Renewal choices during booking

| Scenario | Actions | Expected result |
| --- | --- | --- |
| Existing combined screens | Review samples 40–42 with a membership within five days of expiry, then one past its grace deadline. | Inline Renew / Not now / Email me later choices sit beside existing membership information. Counts, price, capacity, closure/override, waiver and payment controls stay together. No choice is required to continue booking. |
| Renew and return | Enter attendee counts/socks, choose Renew, then return from the new tab. | The original fields remain entered and the estimate can refresh. Its existing 30-minute staff hold retains its original expiry; an expired hold must be explicitly renewed. Public booking still expires after 20 minutes. No booking is confirmed by opening renewal. |
| Protected customer checkout | Use Renew on the public booking, then attempt private checkout before and after phone/name verification. | Booking proof alone grants no purchase authority. Verified private checkout uses current terms and explicit card acceptance/final confirmation. One accepted purchase queues one payment; repeating confirmation does not queue another. |
| Not now | Choose Not now, open a later booking before 30 days after expiry, then one at/after that boundary. | No intervening prompt appears. One further prompt is allowed on the later booking; independently opened bookings cannot display that further prompt twice. An already displayed prompt in the same flow can still accept its choice. |
| Email me later | Inspect the date beside the choice and select it. | A reminder is requested for 9 a.m. the following New York day, including DST. It does not confirm a booking, charge a card, extend membership dates or preserve an expired seven-day minimum. Requested history remains under Renewal notices. |
| Contact not saved | Use a verified existing profile with no email and enter a valid email in the booking. Request a reminder before and after completing booking. | The page asks the customer to finish booking to save the contact. No message goes to the uncommitted address. Once the address is actually saved, eligible due preparation uses that current address. With no valid pending or saved address, the option is disabled. |
| Current facts before email | Partly/fully renew, record a cancellation or payment review, or correct contact details before the queued reminder is claimed. | Partial renewal/contact corrections replace the unsent frozen text; full renewal, cancellation, funding review or stale/revoked/used links withdraw it. A contact change during claim keeps the replacement tied to the original request. No attempted/unknown mail is automatically repeated. |
| Native navigation and stale reviews | Use the controls without JavaScript, then repeat with an expired flow or changed customer. | Renewal opens the protected page; saved/expired choices show clear return navigation. Counts in the original tab remain. CSRF, private flow ownership, actor/customer/revision and current eligibility are enforced. An old customer's token cannot act on the newly selected customer. |

## Existing credit at initial membership checkout

| Scenario | Actions | Expected result |
| --- | --- | --- |
| Same combined purchase form | Select a customer with available credit and use the new credit field/button; compare monthly and prepaid, cash and card. | Principal, actual credit, remaining payment and remaining card fee appear together. Credit applies only within the first installment's principal and available backed funds. Changing amounts clears acceptance and requires the current review. |
| New cash received | Review samples 44–45 and complete the fictional cash example with receipt/terms confirmation. | $53.97 is settled by $13.02 credit and $40.95 cash. Only $40.95 is a new receipt. No cash/check receipt date step or card fee is added. |
| Remaining card amount | Apply $16.02 to a $17.99 initial membership. | A $1.97 balance plus $0.06 fee queues one $2.03 request. Credit is not charged a processing fee or recorded as new money. Until that payment is confirmed, benefits remain pending. A declined attempt needs explicit retry and does not apply credit twice. |
| Full credit and future payments | Fully fund a first monthly installment, then a prepaid term. | Monthly still requires an accepted card mandate for later dues. A fully funded prepaid term needs no card or zero-dollar receipt. No physical payment is claimed. First payment remains due at purchase even for a future start; benefits then remain Scheduled until the term begins. |
| Stale/source/permission checks | Change credit availability or its source status, change the selected credit after saving card consent, and try forged credit on public renewal. | Invalid or source-held amounts create no partial purchase. Card authorization binds the current credit/terms. Unscoped public credit is rejected. An owner correction and purchase use the balance once without FK/advisory deadlock. |

This increment uses existing available credit. Combined purchase-and-visit conversion, broader redemption and credit-return cancellation remain separate unfinished flows below. No refund destination has been assumed.

## Combined membership purchase at arrival — cash/check

Review samples 46–48 for cash/check, 49–66 for card funding and recovery, 75 for a verified physical gift card and 76 for a paid membership during an owner-comped visit. Combined already-paid visit conversion remains in development; use fictional data only.

| Scenario | Action | Expected result |
| --- | --- | --- |
| One page | Open arrival on the visit date, select Buy a membership with this visit, then enter places, term, billing and the actual cash/check method. | Counts, waivers, pricing and one final confirmation stay on arrival. For three children/two adults buying two monthly Subscription places: $35.98 membership + $15.99 visit = $51.97 new cash. |
| Preview | Change the proposed package without confirming. | Membership benefits are hypothetical. No membership, benefit use or receipt is created. Existing customer credit is optional and never derived from unpaid admission. |
| Terms and payment | Review terms and the future installment card; acknowledge the actual combined amount received. | Monthly billing requires the accepted future saved card even when today's payment is cash/check or credit-funded. Prepaid manual payment needs no future card. Owner short-term/complimentary choices remain explicit. |
| Final confirmation | Confirm once, then repeat the same accepted request or submit it concurrently. | One membership and one arrival are recorded with exact constituent receipts; no zero-dollar receipt or second purchase is created. A late failure rolls back both sides. Changed prices/counts/waivers require a current review. |
| Prior Zelle | Apply $10 previously verified Zelle in the $51.97 example. | $10 applies once to the adjusted visit and $41.97 is new cash. Earlier Zelle and existing credit are identified separately in the combined email. Excess Zelle retains the existing manual-refund controls. |
| Completed booking | Review Payment and Saved price breakdown. | Visit money remains separate; a linked membership block records the combined payment split at confirmation. Adults included by membership are not described as cancelled attendees. |
| Combined email | Review the queued confirmation without delivering externally. | One combined membership/visit update includes actual amounts and the next scheduled installment, without a Book a visit CTA. The original earlier booking email remains in history. No additional membership-only confirmation is queued. |

## Physical gift card with membership and arrival

Review sample 75 with fictional data. This is verified in-person tender recording, not a gift-card sale or balance service. Gift cards remain unavailable for cancellation/no-show fees.

| Scenario | Action | Expected result |
| --- | --- | --- |
| One physical card | Select Physical gift card presented and buy two monthly Subscription places for the three-child example. | One page shows $35.98 membership + $15.99 visit = $51.97. Verify the presented card for that combined amount; there is no second cash/check acknowledgment. |
| Change the review | Change counts, membership options or remove/reinclude the membership after verifying. | Verification clears. Review the current total and verify again before confirmation. |
| Future installments | Compare monthly and prepaid. | Monthly requires the accepted future saved card. Prepaid physical-gift-card purchase needs no future card. Neither requests a provider charge today. |
| Confirm once | Confirm the verified tender and repeat the same confirmation key. | Exactly one membership receipt and one visit receipt, one arrival and one combined email entry. No zero receipt or repeated tender. A late local failure rolls everything back. |
| Existing Zelle | Keep $10 already recorded for the visit in this example. | Prior Zelle applies once to the visit; only $41.97 new gift-card funds are recorded. A separately received manual membership payment can now accompany split visit payments, as described below. Samples 92–93 add an explicit allocation of recorded booking Zelle toward membership; the separate new membership-transfer flow is also supported below. |

## Split visit payments with a separately received membership payment

Review samples 79–80. The membership's first payment is cash, check, a verified physical gift card or a separate new Zelle transfer (samples 81–82). Split rows cover the visit only. Splitting the membership payment itself, or funding it from recorded Zelle, remains in development.

| Scenario | Action | Expected result |
| --- | --- | --- |
| Review together | Select Split payment for the visit, buy two monthly Subscription places, choose Cash under Membership paid by and enter $10 visit cash. | Membership $35.98 + visit $16.17 = $52.15. Combined cash to record is $45.98; only $6.17 is charged to the booking card. The future installment card remains a distinct accepted choice. Preview creates no purchase or receipt. |
| All manual | Enter $10 visit cash and $5.99 visit check instead. | No visit card fee or charge. One final confirmation records $45.98 cash and $5.99 check across the membership and visit, totaling $51.97. The installment schedule remains unchanged. |
| Membership tender | Choose Cash, Check or Physical gift card (verified) for the membership payment. | A positive membership payment requires an explicit choice. Cash/check requires its received-payment acknowledgment; a gift card requires physical verification. An unselected preview cannot silently confirm a cash receipt. |
| Gift-card split | Use a physical gift card for the membership and/or part of the visit. Change the visit amount or remove/reinclude the membership after verification. | Verify all presented gift-card amounts. Verification clears when financial entries change. No gift-card balance service or cancellation-fee tender is implied. |
| Visit Zelle | Enter a new verified visit Zelle part with its actual bank receipt date and sender, or apply a previously recorded visit receipt. | Only the visit receives that Zelle application. New Zelle keeps its actual bank date; cash/check collected at arrival keeps today's date. Previously recorded Zelle is identified separately and never reported as new money. |
| Credit and prepaid | Fully fund the first membership installment with existing credit, or select prepaid manual membership payment. | Zero new membership money requires no fabricated receipt acknowledgment. Prepaid manual funding needs no future installment card; a positive visit-card remainder still needs the booking's reviewed card. |
| Pending card | Confirm once while the visit-card result is still pending or uncertain. Repeat the accepted submission. | One membership and one set of constituent payments. Received money includes only actual manual funds, excluding the pending card amount. No paid combined email is queued until the visit is funded; uncertainty blocks a second charge or substitute receipt. |
| Confirmed outcome | Reconcile the simulated $6.17 visit-card result in the review scenario. | Visit total received is $16.17. The linked membership block separately shows $35.98 membership and $52.15 combined new funds. Exactly one combined confirmation is queued; this does not deliver an email. |
| Known decline | Explicitly resolve the confirmed declined visit balance with cash. | Remove the uncharged card fee, preserve the already recorded membership payment and collect only the outstanding visit principal/tax. No second membership receipt or automatic retry occurs. |

## Separate membership Zelle transfer during split visit checkout

Review samples 81–82. Staff must verify a separate, not-yet-recorded membership transfer in the business bank account. This records actual funds; it does not send money, inspect a bank account automatically or move a booking's existing Zelle receipt onto the membership.

| Scenario | Action | Expected result |
| --- | --- | --- |
| Conditional controls | On arrival select Split payment, add the membership and choose Separate Zelle transfer (verified) under Membership paid by. | Only then do membership sender, bank receipt date and verification appear. The cash/check receipt checkbox is hidden. Visit Zelle has its own separate controls. |
| Actual membership funds | Enter the membership transfer's bank sender/date and verify it is a separate transfer not already recorded for this booking. | Two monthly Subscription places record $35.98 Zelle. With $10 visit cash and a $6.17 visit-card remainder, the final action records $45.98 manual funds and requests only that $6.17 card charge. No bank or card request occurs in preview. |
| Separate dates and sources | Use an earlier membership bank date, a different visit Zelle bank date and cash collected today. | Each bank operation keeps its actual date; cash stays dated today. The membership sender/date remain in immutable combined history. Existing booking Zelle applies to the visit by default and is identified as previously received. Samples 92–93 show the optional explicit membership share. |
| Update the review | Change bank sender/date, financial amounts, membership choices or remove/reinclude the membership. Use remaining balance or remove a payment row. | Obsolete receipt verification clears, and a changed bank sender/date invalidates an old accepted review. Checking the separate visit Zelle proof does not clear an unchanged membership proof. A late remaining-balance response cannot overwrite newer typing. |
| Card or waiver navigation | Open the protected signing or booking-card flow and return. | Entered membership source/sender/date, split rows and review choices remain in the private arrival draft. Navigation records no funds or membership. |
| Monthly and prepaid | Compare monthly and prepaid membership Zelle. | Monthly still requires an accepted future installment card. Prepaid Zelle needs no membership card; any positive visit-card remainder uses the booking card. |
| No new money on one side | Cover the visit fully with the new membership, or cover the membership fully with backed customer credit. | A zero-dollar visit creates no placeholder cash/card receipt. A fully credit-funded membership creates no fabricated Zelle receipt and needs no bank verification; existing credit stays separate from new money. |
| Confirm once | Submit twice or overlap two submissions. Simulate a known card result in the fictional review. | One membership and one set of payments, with bank funds recorded once. Pending card money is excluded from actual received totals; the combined confirmation is queued once only after the visit is funded. A late failure rolls back the new funds and preserves earlier booking receipts. |

A single transfer already recorded against a booking cannot be entered here as a new membership transfer. Samples 92–93 show its explicit allocation across membership and visit without another receipt. This flow requires staff verification; it cannot detect a falsely identified bank transfer through an external bank API.

## Paid membership with an owner-comped visit

Review sample 76. A complimentary visit and a complimentary membership are separate owner decisions.

| Scenario | Action | Expected result |
| --- | --- | --- |
| Existing owner exception | Open a confirmed owner-comped booking without selecting a membership purchase. | The original Owner-comped booking — no payment control remains. No paid tender or membership is introduced. |
| Add a paid membership | Select Buy a membership with this visit and choose the actual membership tender below. | The visit remains $0. Two monthly Subscription places cost $35.98 cash/check/verified gift card, or $37.06 by card. A future installment mandate remains required. |
| Remove/reinclude | Remove the purchase, then add it again. | The control returns to comped-only, then offers membership tenders again. The selected tender can be retained, but terms and receipt acknowledgment require fresh acceptance. |
| Complete once | Confirm the reviewed payment and waivers. | One membership receipt, no fabricated visit receipt and no consumed membership benefit for the comped visit. A positive first card payment must succeed before the accepted $0 arrival completes; no second card request is created. |
| Current owner decision | Change the owner-comped choice after a preview. | The old review cannot complete the purchase. Current booking/setup/payment facts must be reviewed again. Staff cannot grant or remove the owner exception through this form. |
| Reconfirm revised setup | Reconfirm an existing booking after the owner changes its pricing to complimentary. | The original email remains in history. One separate confirmation for the revised booking version can be queued; repeated confirmation creates no extra message. No email delivery is implied. |

## Credit-funded membership with visit-card recovery

Review samples 49–52 for the fully credit-funded initial membership. Samples 53–56 cover a positive first membership card payment with a protected dependent visit. Complimentary memberships also keep their visit charge and owner email choice separate.

| Scenario | Action | Expected result |
| --- | --- | --- |
| One page | Apply $17.99 existing credit to one monthly Subscription place; arrive with two children/two adults and select the visit card. | $0.00 new membership charge, $16.47 visit charge. The future installment mandate remains required. The final button requests only the visit charge; there is no cash-received checkbox. |
| Unknown response | Use simulated uncertainty, then inspect the booking and payment. | $0.00 new money is claimed until a confirmed outcome. The $17.99 applied credit stays separate. Another dispatch or replacement receipt is blocked; no paid combined email is prepared. |
| Reconcile | Confirm the original simulated transaction through provider GET. | One $16.47 visit receipt, one application of credit and one combined confirmation. No further financial POST is made. |
| Declined then cash | Explicitly record verified cash after a confirmed decline. | The adjusted $15.99 cash amount has no unearned card fee. The first membership credit is not applied twice; the combined email uses actual effective invoice amounts. |
| Source return | Report a return against the receipt backing the applied credit before dependent dispatch. | The visit charge stops for owner review. Additional collection is blocked. A forced PostgreSQL race verifies the correction remains visible after dispatch waits on the customer lock. |
| Before email dispatch | Change the committed customer email or settle a later installment before claiming the queued combined confirmation. | Only current, unattempted content can replace the stale queue entry. Initial combined money excludes later installments; the next installment is actually unpaid. An attempted/unknown email never automatically sends another. |

## Positive first membership card payment with arrival

Review samples 53–56. Use only fictional customers and simulated provider outcomes before release authorization.

| Scenario | Action | Expected result |
| --- | --- | --- |
| Both amounts together | On arrival, select two monthly Subscription places for three children/two adults and the saved membership card. Accept the current terms. | The page shows membership $37.06, visit $16.47 and total $53.53, identifying both cards. One final action saves the accepted purchase and initially requests only its $37.06 payment. No attendance or benefit usage is recorded yet. |
| First result uncertain | Inspect the same arrival URL and Check payment status. | $0.00 received; no dependent visit request, second purchase or automatic card retry. Existing payment controls support reconciliation of the original attempt. |
| First payment succeeds | Confirm the existing simulated membership transaction, then let the dedicated continuation job run. | Actual membership funds remain recorded independently. A new transaction checks the unchanged visit, actor, signed evidence, capacity and funding before requesting its $16.47 visit charge. It never charges inside the first-result callback. |
| Visit succeeds | Confirm the separate simulated visit transaction. | One arrived booking, two used membership places, $53.53 actual combined receipts, and one accurate combined confirmation. Both fees are included. Later installments are not included in today's receipts. |
| First decline then explicit cash | After a definite decline, explicitly record the actual membership cash payment in its existing payment controls. | The same membership is funded, with no duplicate purchase. Unchanged accepted visit details can continue; the confirmation uses actual lower effective membership fees. No failed card retries automatically. |
| Added signed waiver | Record another current paper/electronic waiver without removing any accepted valid evidence, then continue. | The still-valid review may proceed; the actual checkout records current coverage. Removed/expired accepted evidence or a material visit change requires review. |
| Reservation or details changed | Wait beyond 30 minutes, change the session/price/source, or deactivate the original actor before continuation. | No dependent visit charge is requested. Any already confirmed membership receipt is preserved. Dashboard attention persists. The owner may start the fresh current review described below once funding is confirmed. |
| Processing paused | Pause membership sales after acceptance and inspect arrival or another booking action. | The accepted intent remains protected; ordinary arrival/edit/cancellation cannot bypass it. Pending card dispatch does not proceed. Actual existing provider outcomes can still be reconciled. |
| Unchanged approved recovery | If the continuation job is blocked and the original review is still current, choose Complete reviewed arrival as the original staff actor or owner. | Recheck uses the same purchase and original accepted authority; no second first payment. The button is unavailable if amounts, capacity, waiver evidence or the reservation changed. |

## Fresh owner approval after an expired or changed arrival

Review samples 57–60. This uses the existing paid membership; it is a current visit approval with a distinct owner record.

| Scenario | Actions | Expected result |
| --- | --- | --- |
| Expired original reservation | After the initial membership receipt is confirmed, wait beyond the 30-minute extra-attendee reservation. Open arrival status. | Actual membership funds and balance remain visible. No visit charge or hold extension occurs. An owner can choose Review current arrival. Unconfirmed/held first funding must be reconciled first. |
| Start current review | Click Review current arrival. | An explicit protected POST pauses the original automatic continuation. Counts, signed/paper waivers, pricing and payment controls appear on the existing arrival page with the received membership amount and term. No membership-buy fields are shown. Merely opening a GET link cannot pause processing. |
| Review and confirm | Correct counts, enter the reason, confirm actual waiver coverage and select the visit payment. Review the new estimate and confirm once. | Current capacity, fees, benefit availability, waivers and payment source are checked again. Only the current remaining visit payment is recorded/requested. Original terms, accepted intent, first receipt and purchase count stay intact. Owner identity, reason and current checkout are retained in an immutable resolution and readable Change history. |
| Original staff deactivated | Complete the new review as an active owner after deactivating the original staff member. | The visit belongs to the new owner approval. The original purchase/receipt keep the actual original staff actor. No old credentials or impersonation authorize a new charge. |
| Waiver/card return | Leave through the existing waiver/card controls, then return to the private arrival draft. | Entered counts, reason, payment choices and recovery identity return together. Private actor/booking/version/expiry checks still apply. Normal customer/public forms cannot use this authority. |
| New capacity conflict | Increase counts beyond current capacity, then review before confirming. | It remains blocked unless the owner explicitly checks the existing capacity exception. An expired hold is not treated as reserved capacity. |
| Stale or repeated confirmation | Change counts/reason after review, submit the same confirmation twice, or use two owner tabs. | Changed facts require a new review. Identical accepted requests reuse the saved checkout. Competing confirmations and an old continuation worker produce only one visit payment. |
| Native and validation recovery | Use the form without JavaScript, or submit with a missing reason. | Native Update totals then Confirm uses the current amount. Errors leave the final button unavailable while the safe visible estimate still applies actual paid member benefits. A missing CSRF token makes no changes. |
| Actual receipt and mail | Confirm the simulated remaining visit result, then inspect booking and queued email. | Original membership and current visit receipts appear separately and add once. The confirmation uses current fees/tax/counts and remains pending until actual funds are confirmed. |

## New membership card during combined arrival

Review samples 61–64. Actual hosted provider fields and live flags remain unverified; the sample inputs are visibly labelled test doubles.

| Scenario | Actions | Expected result |
| --- | --- | --- |
| New card on the same page | Select Enter a new card in the membership card selector. Enter the hosted fields, choose future-visit Yes/No, accept the current terms and review both amounts. | Counts, waivers, price and final confirmation remain together. Monthly payments keep the accepted membership mandate even with No for unrelated future visits. The new membership card does not replace the booking's separately authorized visit card. |
| Final action | Confirm the reviewed combined amount once. | Card storage creates no payment. Current accepted card authority is bound to this actor/customer/purchase key and exact offer. The combined price is checked again before the existing membership-first/dependent-visit flow can proceed. |
| Storage unknown | Simulate uncertainty, reload, then Check card setup. | The existing setup is inspected without another nonce exchange or automatic purchase. The private draft retains the visit and selection. Required unresolved storage blocks confirmation. |
| Reconciled saved card | Resolve the existing simulated setup through provider reads. | The actual saved source appears; no purchase or payment is automatically submitted. The owner still confirms the reviewed visit. |
| Terms or capacity changed | Change membership terms after storing a card, or change capacity while card authorization is being refreshed. | New terms need explicit acceptance and current card authorization. Known-card reauthorization uses provider reads, not another storage exchange. A changed visit/payment review stops before purchase or payment and requires review again. |
| Membership-only storage | Choose No for future visits. | The new nonreusable card is available only with its scoped authorization and then retained for the accepted membership obligations. Another request/browser/customer cannot borrow it. Earlier visit consent and binding remain intact. |
| Keep for future visits | Choose Yes, then compare before and after final purchase confirmation. | The old future-use preference is replaced only at final confirmation. Its existing booking binding remains active until those obligations are settled; the new member card never silently takes over that visit. |
| Expired authorization | Leave the card authorization beyond its existing 20-minute lifetime. | It cannot fund a purchase or extend itself. The same known saved source can use the explicit fresh review below while its original private browser/customer/actor context remains available. The two-hour private arrival draft does not extend card authority or capacity. |

## Expired saved-card review

Review samples 65–66. This applies to staff purchase/arrival sessions with a known saved source. Expired replacement-card update sessions direct staff back to the membership for a fresh update; missing/changed private context requires a new checkout.

| Scenario | Actions | Expected result |
| --- | --- | --- |
| Read after expiry | Leave a known saved card beyond the 20-minute review window, then reload/check its setup. | The card remains visible for review, with counts and current prices. Acceptance is cleared; status/preview reads do not renew authority or request payment. The original expiry remains immutable. |
| Explicit current approval | Accept the current terms again and confirm the reviewed total using the same known card. | A provider ownership/expiry GET checks the existing source. A new authorization records this current acceptance and a new 20-minute deadline; the old record is retained. No nonce is exchanged and no card is stored again. Only then can the selected initial purchase/payment proceed. |
| Unknown expired storage | Inspect an old uncertain setup, then try fresh authority or another nonce. | The existing outcome remains reviewable, but the attempt is blocked before provider I/O until reconciled. Expiry does not convert uncertainty to a decline or allow another exchange. |
| Live page expires | Keep a standalone staff purchase page open until its current card review expires, then confirm. | The client stops submission, clears acceptance and asks for a fresh current review. The server still enforces expiry. No payment proceeds using the expired authorization. |
| Return after fresh review | Reload after a successful fresh authorization but before the purchase was completed. | The setup recovery link and latest already-created authority for that source/current terms remain available. A GET does not recreate an authority or repeatedly clear a new acceptance. |
| Scope changed | Use another browser/actor, change committed customer details or select a different source through the expired private proof. | The old authority cannot be borrowed. Start a new reviewed checkout when the original context is unavailable. Public renewal verification/deadlines are unchanged. |
| Purchase already recorded | Try requesting initial card setup/reauthorization after the purchase exists. | No new storage or initial authority is issued. Status reports that the purchase is recorded; review its existing payment instead. Retry/resolution still uses the dedicated explicit membership payment controls. |

## Scheduled collection foundation

The developer-only `preview_membership_installments --limit 20` report is read-only. It shows installments due on the current New York date, the accepted price, backed credit, the remaining card amount and reasons for owner review. `--include-overdue` includes missed dates for review; it never catches up or retries a charge.

Immutable scheduled claims protect one installment's accepted scope and fixed keys against duplicate preparation. Claim preparation itself creates no financial work. The internal collection service now applies backed customer credit, adjusts only the uncharged card fee and queues only a positive card remainder through the existing one-POST worker. A fully credit-funded installment has no card request, new receipt or successful-installment customer email. Existing receipts and credit history remain distinct.

| Developer-verified scenario | Expected result |
| --- | --- |
| $17.99 membership principal with $16.02 converted credit | Apply $16.02 existing funds; request $1.97 principal + $0.06 fee = $2.03 on the accepted card. New money remains $0.00 until confirmed, then $2.03. Original visit receipts and retained fees remain unchanged. |
| Credit covers the full $17.99 principal | Apply $17.99 credit, remove the uncharged card fee and mark that installment funded. No card operation or dispatch job is created, even if its accepted card is now inactive. Excess credit remains available. |
| Declined card remainder | Keep the credit application and the exact failed request. Do not retry automatically. An authorized explicit cash resolution collects only the remaining principal, removes its uncharged fee and never reports credit as new cash. |
| Credit restored or a source return appears before dispatch | Cancel the older unattempted card scope and leave payment review to the existing owner controls. Preserve the credit application and original receipts; no larger or replacement card request is silently created. |
| Concurrent collections or an owner correction | Available source budgets serialize. Two distinct installments cannot spend the same credit; duplicate scheduling returns the existing application/request. |

The existing bounded payment worker now prepares installments on their original New York due date when `MONKEYDO_MEMBERSHIP_COLLECTIONS` is enabled. The switch remains off by default. Preparation and card dispatch are separate durable steps; full-credit preparation creates no card job. Current cancellations, previous unpaid installments, funding holds, existing invoices and claims are respected. There is no automatic retry, catch-up collection or term renewal. Existing explicit installment controls remain available.

| Owner review | Expected result |
| --- | --- |
| Current unattempted preparation — gallery 73 | The family, membership and due date appear together, with a direct membership link and current credit/card estimate. Only the owner can resume eligible work after reviewing it. An existing uncertain payment cannot be resumed through this action. |
| Missed date — gallery 74 | Resume is unavailable. Use the linked membership payment controls for an explicit collection. Closing the technical task does not record payment or remove the installment balance. |
| Temporary producer failure | Existing queued work continues. The worker reports a safe review message; it never exposes raw provider/database text. Two simultaneous producers create one preparation job. |

## Apply a released Unlimited benefit from the customer receipt

Review samples 77–78. This uses the original private booking browser and its existing twenty-minute deadline; it does not renew verification or grant payment permission.

| Scenario | Action | Expected result |
| --- | --- | --- |
| Released daily place | Make two bookings for a customer with one Unlimited place, then release the first booking's daily reservation through the normal cancellation controls. Open the second booking's original receipt. | Its saved ordinary price stays unchanged. The receipt offers Apply available Unlimited benefit with current and proposed booking totals; viewing it reserves nothing new. Its existing capacity reservation remains in place. |
| Review and confirm | Review the proposed itemization and confirm the updated price once. | Append a quote and reserve one benefit. Do not mark attendance/use, collect money, change the card, confirm a waiver or queue another email. Original quote, signed evidence and original confirmation remain in history. |
| Clear adjustment | Compare the resulting receipt with the original booking. | The example changes $16.47 to $0.00: $15.00 membership adjustment, $0.45 uncharged card fee and $1.02 tax estimate removed. Included adults are described as a membership adjustment, rather than cancelled admissions. |
| A later membership purchase | Start with an ordinary booking, then complete a qualifying membership purchase. | Its original private receipt can offer the paid benefit, including for a new customer whose original profile remains unchanged. An earlier ordinary quote need not contain membership metadata. |
| Repeated or competing confirmation | Repeat one confirmation, or have two bookings try to reserve the one available daily place. | Repeated confirmation returns the original result. Only one booking can take the daily place. The other retains its saved price and must review current availability. |
| Staff or payment change | Begin arrival/payment, change an owner price or consume the benefit after the customer's preview. | The old review cannot change the booking. Current staff/owner decisions remain intact; no automatic repricing or collection occurs. |
| Advance Zelle | Record actual Zelle funds before confirming the price change. | A new receipt invalidates the older review. The receipt separates recorded Zelle from its booking-price estimate and does not ask for another transfer when the existing funds cover it. Fresh confirmation preserves those funds without another receipt, application or completed refund. The existing arrival/refund controls handle the actual funds later. |
| Verification or recovery boundary | Let the private booking session expire, change the verified contact profile or enable recovery hold. | No benefit mutation is allowed. Use staff assistance when the original private verification is unavailable. This flow cannot borrow a membership receipt's read-only verification or extend a card deadline. |

## Existing customer credit for ordinary or supervised arrival

Review samples 83–85. Staff can redeem backed existing funds in the current arrival page; opening or adjusting the review does not spend them. This does not create a physical gift-card balance or add a public post-visit credit action.

| Scenario | Actions | Expected result |
| --- | --- | --- |
| Partial credit with a visit card | On the illustrated two-child visit, enter $10.00 credit and keep the card for the balance. | One member admission is included; the remaining admission uses $10.00 existing funds and $6.17 on the booking card, including only that card remainder's fee/tax. Total $16.17. Preview records nothing. Final confirmation applies the credit once and queues only the $6.17 card request. |
| Use available credit | Click Use available credit on the same visit. | It chooses $15.99, capped at the visit's eligible balance even though $16.02 is available. No uncharged card fee is added. Full credit hides the unused payment method/physical-gift verification and leaves one explicit final confirmation. |
| Complete full-credit arrival | Confirm the $15.99 review once, then inspect booking and the original private receipt. | No new payment, card operation, posting or email. $0.03 stays available. Actual new money is $0.00 and existing credit applied is $15.99. The customer receipt says no remaining visit payment is due, with the original verification deadline and booking confirmation retained. The completed booking-card obligation closes; any card still needed for future membership installments remains retained. |
| Cash, split or supervised balance | Use $10 credit with cash/split, or with the illustrated supervised Subscription visit. | Cash remainder is $5.99; Use remaining balance fills only that amount. The supervised card example is $10 credit + $5.34 card = $15.34 without consuming ordinary free-visit quota. Socks can also use credit; their original tax treatment stays intact. |
| Recorded bank transfer | Record $10 verified visit Zelle first, then review $5.99 credit. | The earlier bank funds apply first and are not recorded again. Credit covers only the remaining eligible balance; neither source is reported as a new receipt. Excess credit stays available. |
| Real received remainder | Select a positive physical gift-card or new visit-Zelle remainder. Change the credit or another financial field after verifying it. | Actual positive gift/Zelle parts need explicit receipt verification. A changed financial amount clears that old proof. Fully credit-funded visits need neither fake gift proof nor a zero-dollar receipt. |
| Stale, repeated or competing use | Change source availability after review, confirm twice, or use the wallet from another arrival/owner correction. | A stale review stops before spending. The same accepted request returns its one application; competing requests serialize source budgets and cannot use the funds twice. Source-return review blocks spending or an unstarted remainder charge. An uncertain card remainder cannot be replaced until reconciled. |
| Existing staff permission | Use an active booking cashier with booking/customer access and Collect payment, without permission to sell memberships. | Existing funds can be redeemed for this visit. The page does not claim that the cashier can make a new membership purchase. Immutable source/application history remains available through permitted booking/customer records. |

Not finished yet: allocating credit to a visit and a simultaneous new membership purchase; applying fresh credit to an already completed arrival; returning applied visit credit or reconverting that visit into another credit source. Those cases stop for review rather than silently charging a different amount. Their accounting/controls remain part of the continuing implementation. Ordinary phone cancellation/no-show fees are not funded from admission credit.

## Customer credit when fewer children arrive

Review samples 86–87. Credit covers eligible admission/socks and their existing tax; it does not pay the itemized partial cancellation fee. Everything stays on the current arrival page.

| Scenario | Actions | Expected result |
| --- | --- | --- |
| One fewer child | In the fictional three-child booking, change the arrival to two children and apply $10 credit. | One member admission remains included. The ordinary admission/tax uses $10 credit, while its remaining amount plus the $3 cancellation fee leaves $9.26 on the card, including the actual remaining card fee/tax. Adjusted visit total $19.26. Preview spends nothing. |
| Use available credit | Click Use available credit with $16.02 in the wallet. | It stops at the eligible $15.99 admission/tax, leaving the cancellation fee payable. The remaining card is $3 + $0.09 fee = $3.09; no tax is added to that nontaxable fee-only card portion. Adjusted total $19.08, with $0.03 credit left after confirmation. |
| Actual cash instead | Select cash or use the split-row remaining-balance control after the $15.99 credit selection. | Only $3 cash remains; no uncharged card fee or extra fee tax. Credit stays $15.99 and actual new money is $3.00. |
| Earlier bank transfer | Record $10 verified Zelle, then review the same reduced visit. | Those funds allocate first. Eligible admission credit is now capped at $7.57, leaving $1.46 on the card including $0.04 fee. The old $10 is not recorded again. |
| Pending and confirmed card | Confirm once, then inspect the booking before/after a simulated provider approval. | While pending, new received money is $0 and credit applied is $15.99. Only a confirmed result makes received money $3.09 and the visit funded for $19.08. The original quote, source funds and one application stay intact. No extra arrival email is created. |
| Confirmed decline | Resolve the known declined $3.09 card remainder explicitly with cash. | Collect only $3.00 and remove the unused $0.09 fee. Do not use the wallet again. An uncertain result still requires reconciliation before another collection. |

Ordinary full cancellation/no-show still uses the booking card or verified recorded Zelle, with its existing charge/no-charge choice. This does not authorize admission credit for those fees. Original saved invoices keep their accepted fee and tax allocations; a new review records its own actual funding. Earlier code cannot replace this compatible version after visit-credit accounting is accepted.

## Split the membership first payment on its purchase page

Review samples 88–89. This is the standalone staff purchase/renewal/addition page. Its product, first receipts, credit, card, price, terms and final action stay together. Fully received manual splits also work during arrival (samples 90–91). Samples 94–99 also support its card balance during arrival, including new manual visit receipts and previously recorded bank funds.

| Scenario | Actions | Expected result |
| --- | --- | --- |
| Multiple first receipts | Choose Split payment for two monthly Subscription places; enter $10 cash, $5 check and $2 verified Zelle. Select the accepted card and review the terms. | First principal $35.98. Only $18.98 remaining principal receives the $0.57 card fee: $17 actual manual receipts + $19.55 card = $36.55. The final button names both actions; preview creates no purchase or money. |
| Record once, then check result | Confirm once. Inspect the membership before and after the simulated card approval. | One membership, one invoice and four tender operations. Initially $17 received and benefits Pending; no paid customer confirmation. Only a confirmed card result makes $36.55 received, activates benefits and queues one confirmation. Repeated/overlapping confirmation does not create another receipt set. |
| Keep original monthly dates | Inspect later installments after a manual/split first payment. | Later amounts remain the accepted full card amounts: $37.06 on November 30 and December 31 in the sample. First-payment split amounts do not become future cash/check instructions. A separate developer test queues the original later $37.06 against the accepted card without sending it to the provider. |
| Bank or physical gift card | Enter positive Zelle or gift-card amounts. Verify the actual bank transfer or physically presented gift card. | Each source has its own proof. Bank date/sender remain in immutable accepted history and the overview; cash/check use today's receipt date. Existing money recorded elsewhere must not be entered as a new transfer. Changing financial amounts/sender/date clears earlier receipt proofs and term acceptance. No bank account or gift-card balance is checked automatically. |
| Prepaid split | For a $107.94 prepaid term, enter $100 cash; then compare $107.94 cash. | The partial case needs the accepted card for $7.94 + $0.24 fee = $8.18. The all-manual case needs no card or storage exchange. Prepaid cash/check/gift combinations also work after their actual receipt verification. |
| Monthly all-manual first payment | Enter $35.98 cash for the first monthly payment. | No first card charge or fee is fabricated. The accepted saved card remains required for later scheduled installments. |
| Existing credit plus split | Apply $10 of the sample's $16.02 credit, enter $3 cash for a one-place monthly purchase, and keep its accepted card. | $10 existing credit + $3 cash + $5.14 card, including $0.15 fee. Only $8.14 is new money, with $6.02 credit left. The source $16.47 receipt/retained $0.45 fee remain unchanged. Full credit creates no zero-dollar receipt. Use available credit caps itself after the manual amounts already entered. |
| Declined or uncertain card | Resolve a confirmed declined $21.61 remainder from the $10 cash/$5 check example with actual cash. Compare an unknown outcome. | Known decline collects only $20.98 principal, removing the unused $0.63 fee, without recording the earlier $15 again. An unknown outcome blocks another collection until reconciled. Source-held credit also blocks new spending/dispatch. |
| Card setup and authority | Save a new membership card for a prepaid split with a positive card remainder. Change the split and review again. | Storage alone takes no payment. Accepted terms/offer/card authority bind the current amounts. Fully manual prepaid rejects unnecessary setup before provider access. Real hosted fields remain unverified by the fictional gallery. |

Staff-only split payments do not add manual-payment or credit authority to private public checkout, which retains its card-only flow. Migration 0076 records the model choice without adding a new money table/column; reversal and release compatibility refuse older code after accepted split purchases. No production financial action is exercised by these examples.

## Received membership split with arrival

Review samples 90–91. Choose **Split payment** for the visit, **Split received payment** under Membership paid by, and enter the membership amounts separately. For two monthly Subscription places, enter $10 cash, $5 check and $20.98 separate verified Zelle. Enter $10 cash in the visit's payment rows; its card remainder is $6.17.

| Check | Expected behavior |
| --- | --- |
| Review together | Membership $35.98; visit $16.17; combined $52.15. Cash to record $20, check $5, Zelle $20.98 and booking card $6.17. Review creates no money or membership. |
| Verify actual receipts | Cash/check need their receipt confirmation, Zelle needs bank date/sender and its separate bank verification, and a positive gift amount needs physical verification. One proof cannot substitute for another. |
| Change amounts or bank details | Old proofs and terms acceptance clear. The current financial review must be accepted again. A private draft reload keeps the entered amounts. |
| Confirm once | One membership and its actual manual receipts are recorded atomically with arrival. A repeated confirmation returns the same records. A late failure leaves no partial purchase or receipt. |
| Card is pending | $45.98 is received. Membership benefits are active because its entire first installment is funded; the visit card is pending. No paid combined email is queued yet. |
| Confirmed visit-card result | $52.15 is received, with membership $35.98 and visit $16.17 shown separately. One combined confirmation is queued. Checking status never charges again. |
| Keep funding sources separate | Recorded booking Zelle applies to the visit by default; samples 92–93 add an explicit membership allocation. Newly entered membership Zelle is a separate verified transfer. Existing credit reduces only the membership amount selected and is never reported as new money. |
| Preserve card authority | Monthly membership requires its accepted future-installment card. A newly entered private membership card does not replace or fund the visit's booking card. Fully received prepaid needs no membership card. |
| Membership split still has a card balance | Samples 94–99 retain received membership and visit funds while the first card is pending. Arrival and its separate visit card follow confirmed funding and current validation. |


## Apply recorded booking Zelle to membership

Review samples 92–93. On the same arrival page, choose **Split payment** for the visit and **Split received payment** for membership. When verified booking Zelle is available, enter the part to apply to membership; the rest remains for the visit. Do not enter this original transfer again in the separate new membership Zelle field.

| Check | Expected behavior |
| --- | --- |
| Assign one original transfer | With $25 already recorded, assign $20 to membership. The visit retains $5. Review makes no allocation or payment record. |
| Review new money | Two Subscription places cost $35.98. Enter membership cash $10 and check $5.98. The visit costs $15.99; its Use remaining balance shortcut gives $10.99 cash after its $5 bank share. New funds total $26.97. |
| Preserve one bank receipt | Confirm once: the original $25 is applied as $20 membership and $5 visit, with its original date/sender. There is still one bank receipt. The two source applications do not mean two new transfers. |
| Inspect the completed booking | Visit funding is $15.99. New cash/check funds are $26.97, split into $15.98 membership and $10.99 visit. Earlier bank allocations remain separately labelled. One combined confirmation is queued. No card is charged in this example. |
| Change an assignment | Old cash proof and terms clear. Added/changed receipts or source use make an earlier review stale. Invalid/excess amounts save nothing. |
| Preserve the draft and source cards | Reload keeps the bank selection and entered amounts. Monthly membership still requires its accepted future card; later amounts/dates do not change. |
| Combine bank and backed credit | Both reduce only the remaining membership principal. New money is separate from both. Bank funds left after a fully covered visit remain a refund balance for that visit, without including money already assigned to membership. |
| Cover the first payment completely from bank | No new cash/bank proof or fabricated new bank receipt is needed. A monthly term still needs its accepted future card. Any unassigned excess is calculated as a manual Zelle refund due. |
| Return only unused bank money | Allocated membership/visit amounts cannot also be returned through the booking's unallocated Zelle-refund action. Record only the actual unused refund after manually returning it. |
| Keep the scope explicit | This allocation belongs to the original customer's combined booking/first membership installment. Standalone/public purchases and another customer's booking cannot consume it. A first membership card remainder also supports this allocation, as described below; new manual visit funds are saved immediately as in samples 97–99. |


## First membership card remainder during arrival

Review samples 94–96. Use **Split payment** for the visit and **Split received payment** for membership. Enter received membership amounts separately; leave visit manual amounts blank when it uses only card and/or prior bank funds. Samples 97–99 also support new manual visit receipts.

| Check | Expected behavior |
| --- | --- |
| Review both card amounts | Two Subscription places: $10 membership cash + $5 check + $21.61 membership card = $36.61. The separate visit card is $16.47. New payments total $53.08. The final action names the $15 received funds and the first card request. Preview writes nothing. |
| Confirm once | Record the $15 membership receipts once and request its $21.61 card remainder. No active benefits, arrival or visit-card request while that first card is pending. Repeated/overlapping confirmation returns the same purchase and receipts. |
| Check the pending result | Membership amount, $15 actual received, $21.61 balance and reviewed visit remain together. Status checking requests no new charge and preserves the original thirty-minute extra-capacity deadline. |
| Funding is confirmed | Recheck current booking, capacity, source, waiver and benefit facts. Then complete arrival and request the exact separate $16.47 visit card. Its pending result still does not claim the combined visit paid. |
| Visit payment is confirmed | Show $53.08 new money, including $36.61 membership and $16.47 visit. Queue one combined confirmation only after actual funds are confirmed. Later monthly installments retain $37.06 and their original dates. |
| Prior recorded bank funds | With $25 earlier Zelle, assign $20 membership/$5 visit and enter $10 new membership cash. The first card is $6.16, the later visit card $11.32. Pending membership funds show $20 earlier bank + $10 new cash separately. Reloading the saved intent preserves original source identity and uses the bank allocation once. |
| Prepaid or fully manual membership | A one-place prepaid term with $50 cash needs only its $4.09 card remainder. A fully manual prepaid purchase needs no card. A fully funded manual membership can also accompany an entirely card-paid visit without a fabricated manual visit row. |
| Confirmed decline | Explicitly receive the remaining $20.98 principal from the cash/check example, removing the uncharged $0.63 card fee. Earlier $15 is not recorded twice. The reviewed visit can continue after funding. |
| Unknown result | Keep the original operation and received funds visible. No automatic retry, replacement receipt or visit card request until reconciled. |
| New manual visit money while first membership card is pending | Record the actual visit sources now, as in samples 97–99 below. They remain separate from membership funds and apply once after funding. After confirmed membership funding, use the owner return/review flow in samples 100–102. For an unresolved first card, use the explicit unused-funds pause in samples 107–108; an unstarted request still needs its existing payment/purchase controls first. |

Migration 0078 binds the pending first card to its accepted split remainder, exact actor/customer/booking and original capacity deadline. Used migration reversal and release compatibility refuse older code that cannot preserve that split. No actual processor behavior is established by simulated results.

## Manual visit receipts while membership funding is pending

Review samples 97–99. Enter received membership amounts above, and received visit tenders in the separate visit payment rows. Bank/gift proof is required for each applicable source; an older transfer already recorded for the booking must not be re-entered as new money.

| Check | Expected behavior |
| --- | --- |
| Review once | Membership $10 cash/$5 check/$21.61 card; visit $3 cash/$2 check/$1 Zelle/$1 gift/$9.26 card. Combined new funds $52.87. Preview records nothing. |
| Confirm actual receipts | Save $15 received for membership and four original visit receipts totalling $7. Only the first membership card is requested. Received visit funds appear on pending arrival and booking; no completed visit or active benefits yet. |
| Preserve dates and proof | Cash/check/gift use the actual confirmation day. The separate verified Zelle keeps its earlier bank date/sender. Changing amounts clears obsolete verification; changing membership payment terms clears its acceptance. |
| Reload and inspect unknown outcomes | Original visit funds remain $7 and keep their collecting actor/date. Unknown membership card outcomes cannot trigger a visit charge or replacement collection. No extra-capacity deadline extension. |
| Membership funding succeeds | Revalidate the original reviewed visit, apply each original source once to its accepted invoice with its original date, then request $9.26 visit card. Repeated confirmation and worker continuation create no duplicate receipt/application. |
| Visit result succeeds | Received money becomes $52.87, separately membership $36.61 and visit $16.26. Queue one combined confirmation after actual funding. Source facts and invoice applications are not two receipts of money. |
| Earlier original bank funds | Explicitly assign original booking Zelle between membership and visit, then add new cash/check visit funds. Original bank uses its established allocation; the new manual receipts remain distinct. |
| Fresh owner review | After the original extra-capacity deadline, the owner can review current arrival and apply unchanged received tender amounts. The original collecting staff member and receipt dates remain intact even when the owner completes the visit. |
| Changed manual amounts or a return | After confirmed membership funding, pause for owner review and record any actual original-tender return as in samples 100–102. For unresolved funding, samples 107–108 provide a separate owner pause for actual visit-fund returns; terminal reconciliation remains separate. Retain the original records. |

Migration 0079 adds immutable source/application facts. Database constraints bind them to the original accepted visit/tenders and require all received sources before commit and a completed original arrival before applying them. Used reversal and older release switching refuse to discard those facts. No external bank, gift-card balance or provider call is performed by these samples.

## Unused visit funds after confirmed membership funding — samples 100–102

These are review/developer-test steps for a later separately authorized staging release. The owner must pause arrival before handling a manual original-tender return. This is not a processor-refund or live-payment instruction.

| Action | Expected result |
| --- | --- |
| Open a funded membership with unfinished arrival | Choose **Review current arrival or unused funds**. Automatic arrival stops; no new visit charge occurs. For unconfirmed membership funding, use the separate unused-funds pause in samples 107–108. Nonowners and already applied visit sources cannot record a return. |
| Expand **Record returned visit funds** | See original receipts and unused balances. Select the original source, actual returned amount/date and confirm it was returned through that original method. Today is filled in correctly. Changing source/amount/date clears this confirmation. |
| Record a $2 return from original $3 cash | Preserve the original source/collecting staff/date. Add one immutable owner return fact. Keep entered counts/reason on the same page and show $1 cash remaining. Repeating the same submission adds no second return. |
| Review $5 received visit funds remaining | Apply the original $1 cash/$2 check/$1 Zelle/$1 gift once. The old Zelle date/sender remain intact. No new verification is required for these already verified funds. |
| Add genuinely new manual money | Choose **Add another payment**. Tender totals include old held amounts; only amounts above those held sources become new receipts. Additional bank/gift funds need fresh verification; new Zelle keeps its own actual date. A completed return is removed from draft totals so it cannot appear as newly received money. |
| Review current price before confirmation | In this fixture the visit is $16.32, including $0.31 card fee. The final button names $5 received funds plus the exact $11.32 card balance. Old source/price hashes cannot authorize the earlier amount. Return recording itself creates no card request, invoice receipt, membership change or credit. |
| Confirm once, then verify the existing visit card result | Apply four original source remainders once and request one $11.32 card operation. Only a confirmed result produces $52.93 net membership/visit funds and one combined confirmation. Pending or unknown funds are not reported received. |
| Compare original and current history | Original received $7, returned $2 and applied $5 reconcile. Membership remains $36.61; visit receives $16.32. Original source/return actor/date, membership terms and future installments are retained. |
| Stop before unresolved situations | This records only actual unused visit-fund returns. The separate pause in samples 107–108 also supports unresolved membership funding. Cash change, completed-visit refunds, membership refunds, wallet transfers and remaining terminal reconciliation keep their own rules and controls. |

Migration 0080 preserves the frozen original receipt scope, adds immutable original-source returns and serializes return/application budgets. Exact remaining balances, actual dates and owner-review state are required. Used reversal and incompatible older releases are refused; this is not an authorization to run a migration or deploy.

Developer evidence: **1,476 PostgreSQL tests pass (553.752s)**; the final actual browser scenario passes in 8.118s, with original $7 / actual returned $2 / remaining $5, one membership/eight operations/four source applications and one queued unsent combined confirmation. All six 100–102 desktop/phone samples were visually inspected. These fictional outcomes do not verify actual Banquest fields or authorize financial actions.

## Gift-card goods payment and a separate cancellation fee — samples 103–104

For a later separately authorized staging test, use fictional records and test payment methods. Physical gift-card verification remains manual; the site does not call a gift-card balance API.

| Scenario | Expected result |
| --- | --- |
| Two children booked, one arrives | Show $15 admission, $0.99 tax and $3 partial cancellation fee. Keep the original $32.94 estimate and the adjustment explanation. |
| Choose gift card for eligible goods | Use $15.99 gift funds for admission/tax. Show a separate $3.09 booking-card action for the cancellation fee and its $0.09 processing fee. No taxable card-funded goods remain, so no processing-fee tax is added. |
| Use the split-row shortcut | Choose Gift card → **Use remaining balance**. Fill $15.99, including when recovering from a $16 excessive entry. Refuse gift amounts above eligible goods before any financial write. |
| Change a financial amount | Clear the physical-gift verification, then require confirming the current actual receipt again. This also works without membership purchase or customer-credit controls. |
| Confirm once | Record one $15.99 gift receipt and request only one $3.09 card operation. Pending/unknown card money is not reported received. After its confirmed result, show $19.08 received with both sources underneath. |
| Cash/check/new Zelle covers the fee | Gift $15.99 plus an eligible $3 actual receipt yields $18.99 and no card fee. New Zelle needs its own verification/date. Already recorded Zelle is applied once before gift eligibility is calculated. |
| Existing customer credit plus gift | $10 credit + $5.99 gift + $3 cash covers this visit. Credit and gift share the same eligible goods limit; neither funds the cancellation fee. Credit applied remains separate from $8.99 newly received money. |
| Pending original gift source but revised visit has only a fee | Stop for owner review. Preserve the original source. Any unused gift money must actually be returned through its original method and recorded before it is removed from the visit budget; it cannot silently fund the fee or become credit. |
| Collect a remaining balance | The current page takes one method per action. Gift is refused while the chosen allocation includes an unpaid fee; select another eligible method. If the fee has already been paid and only goods remain, gift collection still works. |
| Review old records | Existing paid gift facts stay intact and replay adds nothing. New invalid receipts and promotion of an old invalid pending gift request are refused by service/database guards. Existing owner original-tender corrections remain available without rewriting the original receipt. |

Migration 0081 adds an insertion/state-transition constraint without changing historical financial facts or the existing accepted component format. Previous reviewed migration hashes remain unchanged. This guide does not authorize migration, deployment, actual card charges or external refunds.

Developer evidence: **1,498 PostgreSQL tests pass (546.725s)**, including 22 new pricing/native/legacy cases. The final related 101 pass in 65.893s and real desktop/phone scenario passes in 5.388s. All four 103–104 samples were visually inspected; the gift funds are $15.99, the card is $3.09 and only its simulated confirmed result produces $19.08 received. There are no external financial/provider/mail actions.

## Known unfinished areas

Remaining combined-renewal funding methods; owner cancellation-date corrections, expired-term/general corrections, consolidation and nonpurchase grants; remaining mixed manual/card combinations and general date/source exceptions; credit returns and remaining broader redemption; remaining cross-workflow filters/exports and final provider validation remain in progress. Private customer renewal, explicit private-receipt benefit reservation, inline booking renewal choices/requested reminders, staff replacement-card entry, owner decisions for affected bookings, current-term membership cancellation/refunds without credit applications, paid same-day reconciliation, explicit initial/due-installment and ordinary/supervised arrival credit application, and owner unused-credit corrections are functional. Cancellation of credit-funded terms is blocked pending the credit-return flow. Actual Banquest source-return reconciliation of converted funds and whole provider voids including retained fees still need their separate owner correction workflow. The release feature switch stays off by default.

Gift-card allocation with a partial cancellation fee is now covered by samples 103–104 and the checks below. Cancellation/no-show fees never accept gift-card funds. The single-method remaining-payment page asks for another eligible method while a fee remains outstanding.

Developer application testing uses PostgreSQL. An older SQLite migration currently prevents full application startup on that development backend; the new gift-card constraint passed 18 isolated SQLite SQL checks.

Actual Banquest hosted fields and installment processor flags are not verified by the fictional gallery. Three policy answers about later installments after failure, parent arrears after prepaid early renewal, and credit-funded cancellation refund destinations remain pending in the [implementation record](ACTIVE_MEMBERSHIP_IMPLEMENTATION.md). The disputed automatic branches are not enabled, and no credit-refund destination is assumed.

The final guide will add those completed flows, exact release prerequisites and the approved deployment handoff. Merging, deployment and live financial actions require separate explicit release authorization.


## Stop an unfinished arrival while keeping the booking

Review samples **105–106** in the gallery. This action applies to a known-funded, uncancelled membership and an explicitly paused owner arrival review. Unknown/unpaid funding and unresolved membership funding must be reconciled first.

| Scenario | Actions | Expected result |
| --- | --- | --- |
| Unreturned new visit funds | Pause the arrival after membership funding. Open Stop this arrival; keep booking with unused cash/check/new Zelle/gift receipts still held. | The same screen asks for actual original-tender returns first. No stop, fee, refund request or new payment is created. Record only funds actually returned using the existing return controls. |
| Keep booking and membership | After all unused new visit funds have actually been returned and recorded, expand the stop control, read the original counts and continuing membership schedule, enter a reason and confirm. | The original booking remains Upcoming with its original counts and capacity. Only the extra temporary arrival hold is released. The membership purchase, terms, dates, payment sources and agreed future installments remain intact. No attendance, benefit use, visit invoice or card request is created. |
| Original booking Zelle | Use $20 of a previously recorded $25 booking receipt for the membership, then stop the unfinished arrival. | The remaining $5 is still available to the original booking. No duplicate bank receipt or automatic refund is recorded. Ordinary later arrival/cancellation reconciles it through the existing booking actions. |
| Unsaved counts and open tabs | Change a count without confirming arrival, then stop. Reload an old owner-review tab or a private arrival draft; allow an old continuation job to run in a local test. | The unsaved count is not saved. Stopped arrival cannot resume or turn into a fresh arrival automatically. Open booking details to start a new review. The original background continuation does nothing financial. |
| Confirmation retry | Submit the same stop confirmation twice, including after another booking edit. | One immutable stop record and at most one membership-purchase confirmation are retained. The original send-email choice remains respected; no completed-visit message is created. |
| Current booking history | Open the booking payment card and expand Stopped arrivals. | Owner/time/reason, membership link and first membership payment received when stopped, and the returned visit funds by original tender remain visible. Membership funds are not counted as visit money. Current booking status remains above; a later normal cancellation/no-show is a separate action. |
| Role and stale review | Try as ordinary staff, omit confirmation, alter the booking/funding after review, or submit to another booking. | The action is refused before financial writes. A validation error retains only the bounded reason for a fresh review, not confirmation or financial authority. |

This flow **does not cancel a booking or membership**. Those actions remain separate, explicit owner/staff workflows. The separate pause in samples 107–108 allows actual visit-fund returns with unresolved membership funding. Samples 109–110 add stopping an arrival after a recorded membership cancellation. An unconfirmed incoming membership receipt still requires reconciliation before stopping. Do not treat a computed return or queued email as completed.

Developer checks: the complete 1,522-test PostgreSQL suite passes (589.464s), followed by 37 final focused/desktop/phone checks (63.790s) after the retained-history wording was finalized. These cover known/unconfirmed funds, original Zelle and a later explicit cancellation with $5 still due back, extra capacity release, stale tabs/drafts/retries, CSRF/owner/recovery-hold restrictions, immutable evidence, deferred database scope, simultaneous stop versus arrival, and used/unused schema/release compatibility. The final fictional browser creates no new visit invoice/payment request or external financial/email action; its four final images were inspected. The new gallery total is 106 desktop/phone pairs. Actual Banquest and the previously documented SQLite integration limitation remain unverified.


## Unused visit funds before membership funding is confirmed — samples 107–108

| Scenario | Actions | Expected result |
| --- | --- | --- |
| Unknown membership card | As owner, open its unfinished arrival, choose Review unused visit funds, then expand Record returned visit funds. | Only this visit is paused. The original membership operation/reference/outcome stay in place. No new card attempt, cancellation or membership refund is created. |
| Record a real visit return | Return $2 from the original $3 cash receipt and record the actual date and original-method confirmation. | The original receipt stays $3; one $2 return leaves $1 cash and $5 across all visit sources. A double click reuses the same return. No visit invoice, receipt application, attendance or benefit usage is created. |
| Card already sending | Pause and record a completed unused visit-fund return while the membership card is sending. | Its outcome remains sending/unconfirmed for reconciliation. The return cannot stop a request already in flight or create a replacement request. |
| Card not yet sent | Try to pause an arrival whose original membership card is still unstarted. | Use the existing payment-resolution or membership-cancellation controls first, or await its outcome. This action never implicitly cancels the queued card. No pause or return is saved by this rejected action. |
| Late success | Resolve the same original membership card as successful after the visit return. | Automatic arrival remains paused. Reopen a fresh owner arrival review; it applies only the original source remainders. In the fictional partial-return case, the final action uses $5 recorded visit funds plus an $11.32 card request. |
| Original bank funds | Keep a previously recorded $25 booking Zelle receipt, with $20 explicitly used for membership. Return only unused new visit cash/check/gift funds. | The original $5 bank remainder stays available to the booking. No duplicate bank receipt or Zelle refund is created. |
| Separately cancelled membership | Explicitly cancel an unstarted membership purchase with $15 received and $15 refund due. Separately record $2 actually returned from visit cash. | Membership refund due stays $15; visit funds fall from $7 to $5. No membership refund is implied or sent. Its dashboard liability remains separate. After returning all unused visit funds, use samples 109–110 to stop only this arrival while keeping the original booking and membership refund liability. |
| Permissions and races | Try as staff, use an old pause intent, or overlap a late success/another return. | Only the owner can pause/record. Wrong intents and overdraw are refused. A late success cannot bypass the owner pause; a simultaneous completed arrival cannot also return an applied receipt. |

No new schema or capability format is required: the existing immutable unused-visit receipt/return facts and budgets already keep these sources separate. Earlier compatible code retains their balances and keeps the owner pause; releases predating recorded returns remain blocked by the existing capability check. The ordinary owner arrival review and stop-while-keeping-membership action still require known reconciled funding and an uncancelled membership.

Developer verification: all 1,536 PostgreSQL tests pass (593.362s), including 11 new native and three actual transaction-overlap cases. The final real desktop/phone browser case passes (5.825s) with unknown membership state preserved, one $2 actual visit return, $5 remaining original visit funds, no new payment/invoice/customer message and a later success still paused for owner review. All four final images were inspected; no overflow, duplicate IDs, nested forms, JavaScript errors or external provider/storage/bank/gift/mail actions occur. The gallery has 108 desktop/phone pairs. All 56 published migration hashes are unchanged; no schema or compatibility format change is needed. Actual Banquest and full SQLite integration retain their documented limitations.


## Stop arrival after membership cancellation — samples 109–110

| Scenario | Actions | Expected result |
| --- | --- | --- |
| Cancellation already recorded | Separately cancel the pending purchase using its normal explicit owner controls. Open its pending arrival and review stopping it. | The cancellation/effective date and refund due appear on the same page. The stop action does not create another membership cancellation or refund. |
| No unused visit receipts | With no held visit receipts, select Review stopping this arrival. Enter a reason, check the booking/cancellation separation and confirm. | The visit can stop without inventing a return or requiring a paid/active membership. Original booking capacity/counts remain; only the extra temporary hold is released. |
| Held visit funds | With $7 of unused cash/check/gift/new Zelle, try to stop before recording actual returns. | Record the completed original-method returns first. Those $7 are separate from the $15 membership refund due. Nothing is silently netted or refunded. |
| Separate refund due | Stop the arrival while $15 membership refund remains due. Open Dashboard and the membership. | Both original refund plans remain due and actionable. No visit invoice, attendance, benefit use or new payment/refund request appears. |
| Pending membership refund | Stop with an existing queued/sending/unconfirmed membership refund. | Its exact operation stays in place; it is not cancelled, retried or described as completed. Review it through the membership. Incoming receipt outcomes still need to be resolved first. |
| Refund changes during review | Record a separate $2 completed membership refund after opening the stop form, then submit the old form. | The stale review is refused. A fresh review shows $13 due. After stopping, a later refund updates the current membership/dashboard liability, with the old $15 snapshot clearly labelled as historical. |
| End-cycle cancellation | Use a cancellation effective at the end of the current cycle and stop the arrival. | Its actual future effective date remains recorded. The stop does not end the membership earlier, modify term evidence or consume visit benefits. |
| Repeat or old tab | Submit the same confirmation again, or use an old funds-review/close-review button after stopping. | One closure remains; old tabs return to current booking details. The original cancellation-email Yes/No choice is unchanged, with no purchase/completed-visit message. |
| Older release/history | Compare existing kept-membership closures with the new cancellation-linked closure. | Existing evidence stays unchanged. Migration 0083 adds only the optional cancellation reference and exact scope; used new references block older-code switching/reversal. |

Final developer verification: the complete PostgreSQL application suite passed **1,555 tests in 630.202 seconds**, with all final application/schema/template changes included. After adding one further test for an already-unknown outgoing membership refund, the final focused run passed **15 tests in 18.126 seconds**, including all 13 cancellation-linked stop cases and both actual desktop/phone browser scenarios. The final test inventory is 1,556; a complete local 1,556-test run is not claimed. Earlier targeted verification also passed 55 related migration, concurrency and compatibility checks. Both browser runs confirm one stopped intent, original booking/counts, released extra hold, zero visit invoices/attendance/provider calls/delivered emails and no overflow, duplicate IDs, nested forms or JavaScript errors. The cancelled scenario retains the $15 membership refund and both dashboard refund plans; the kept-purchase scenario retains its $36.61 funding and one queued, unsent membership confirmation. All eight final desktop/phone images for samples 105–106 and 109–110 were visually inspected. The gallery has 110 pairs/220 unique PNGs. Ruff/formatting (547 Python files), migration drift, JavaScript syntax, whitespace and all 57 reviewed migration pins pass; all 56 previously published migration hashes are unchanged. The previous published commit dc63883 passed all four GitHub checks. Checks for this update will be assessed after publication. Feature/collection switches remain off by default; PR #37 stays draft, with no merge, deployment or live financial/email action.


## Arrival-fund downloads

On Memberships, use the existing filters, expand **Export filtered memberships** and select **Arrival funds** or **Arrival fund history**. A staff member needs the optional export permission and both booking/financial view permissions. These actions prepare a read-only CSV and record its filters, actor and exact row count.

| Scenario | Check |
| --- | --- |
| First membership card outcome still unknown; $7 actual visit funds | Four source rows retain $7 received/unapplied. No visit application or successful membership payment is invented. |
| $3 cash source; actual $2 return; remaining $1 applied at arrival | Balance row shows $3 originally received, $2 returned, $1 applied and zero unapplied. Event history records original receipt, each actual return and application separately; application adds zero new money. |
| Different collecting/returning staff | Original receipt date/actor and each owner's actual return date/actor remain separate, including the original Zelle sender/date. |
| Stopped arrival with separate cancelled membership | The $7 actual visit returns remain $7. A separate $15 membership refund does not become a visit return; cancellation reference and stopped timestamp remain identifiable. |
| Filtered or empty result | All matching memberships across result pages are included. An empty report has headers and a zero-row audit. |
| Export history | The actual sample downloads record Arrival funds · 4 rows and Arrival fund history · 8 rows for the selected customer. |

The reports cover separately received conditional-arrival cash/check/new Zelle/verified physical gift-card funds. They do not duplicate original booking Zelle, credit, membership receipts or later ordinary visit-invoice refunds. Source received, actual unused-fund return, invoice application and current unapplied balance are different columns; do not add invoice applications to received money. Event money columns are additive, while source/contact/state columns identify the same original receipt across events. Samples 111–112 include the actual fictional CSV downloads.

Developer checks: the final combined run passed 20 tests in 12.908s, including nine new source-report cases, all ten existing reporting cases and actual desktop/phone downloads/audit history. No provider call, financial change or delivered email occurred. This is additional targeted verification after the earlier full 1,555-test baseline and subsequent 15 checks; it is not a claim of a complete local 1,565-test run.


## First membership from an already-paid visit

From a fully paid arrived booking for today, choose **Apply today's visit toward a membership purchase**. The combined page reuses the customer, shows the original payment/fee, membership price, amount applied and new cash/check payment. Review the selected term, any scheduled card installments and agreement before the one final confirmation. Choose Split for one or more new Zelle, physical gift-card, cash or check amounts (samples 117–118). A card-only remainder is now available in samples 119–124; mixed manual/card remainders and further recovery controls remain in progress. Ordinary membership purchases retain their existing payment options.

| Scenario | Expected result |
| --- | --- |
| $15.99 cash-paid child visit; one Subscription place monthly | $15.99 applies to the $17.99 first month; record only $2 new cash/check. First month is funded, one free visit is used, one remains and the next installment is $18.53. |
| $16.47 card-paid child visit | Retain $0.45 original fee. Reverse $15 admission plus $0.99 admission tax and $0.03 fee tax; apply $16.02 and record only $1.97 new cash/check. The original card receipt remains; no separate refund is issued. |
| $37.31 cash-paid two-child/two-adult visit; two places monthly | Apply $35.98; $1.33 remains customer credit. No new payment or zero-dollar receipt. Two benefits are used and future installments remain $37.06 each. |
| Prepaid one-place term, original $15.99 cash visit | First full-term principal is $53.97; apply $15.99 and record $37.98 new check. No future installment/card is required for this prepaid payment. |
| Membership priced at zero | No zero-value credit application or new payment; converted funds stay customer credit and the actual visit benefit usage is recorded. |
| Unreceived new amount or changed price/source/contact | Confirmation is refused before a partial conversion. Review the current amount/terms again. An unrecorded provider return needs reconciliation first. |
| Existing credit elsewhere in the wallet | This flow applies only the credits issued from this visit; it does not silently spend older unrelated credit. |
| Repeated confirmation/recovery reload | Existing membership/receipt/conversion are returned. A different request cannot convert the same visit twice. |
| Membership/booking navigation | Membership overview has Return to converted visit; booking Payment links its membership and preserves original receipt plus conversion history. |
| Confirmation email | One queued combined update separates original money, retained fee, applied funds, new receipt, remaining credit and next installment. No duplicate membership-only receipt, immediate card charge or external delivery. A changed contact refreshes unattempted content; an attempted or unknown email never automatically sends again. |

Existing original visits, accepted terms and signed waiver evidence remain unchanged. The financial history adds a conversion and exact linked reversals/credit allocations. There is no separate cash/card refund for the converted funds. Cancellation of credit-funded membership retains the earlier guarded refund-destination policy; this flow does not choose a new destination.

The complete **1,588-test PostgreSQL suite passed in 673.174s**. After the final receipt-proof reset, **70 focused checks passed in 73.378s**, covering the new conversion, real PostgreSQL overlap/reversal races, affected public/card/deployment paths and three actual Chromium scenarios. A changed server price clears both accepted terms and every old receipt-verification checkbox, including without JavaScript; it cannot convert the visit using proof of an older, smaller amount. The browser checks cover the $1.97 remainder, $1.33 excess credit and stale-price refusal with original funds untouched. All eight final 113–116 desktop/phone images were visually inspected, with no overflow, JavaScript errors, duplicate IDs or nested forms. All 553 Python files pass lint/format checks; model drift, both affected JavaScript syntax checks, diff whitespace, all 232 PNGs and all 58 migration pins pass. The final native inventory is 1,589; a complete local run of that later inventory is not claimed. No external provider/storage request, delivered email, merge or deployment occurred. The same PR37 remains draft with default-off features.


## Received split payments when applying a paid visit

Review samples **117–118**. From the combined paid-visit page, select **Split** to use one or more new manual receipts, including a Zelle-only or gift-card-only remainder. Original visit funds are already applied; never enter them as another receipt.

| Scenario | Expected result |
| --- | --- |
| $16.47 original card-paid visit; $1.97 remaining | Enter $0.50 cash, $0.50 check, $0.47 Zelle and $0.50 physical gift card. Confirm cash/check received, verify the bank transfer, and verify the presented physical gift card. All four are recorded separately; the original $16.02 applies once and its $0.45 fee stays on the visit. |
| Only part of the $1.97 entered | The original balance stays $1.97, without a hypothetical card fee. The price card shows how much remains unallocated and the final button stays disabled. A direct confirmation also refuses before saving a purchase, conversion or receipt. |
| Too much entered | Correct the applied amounts; they cannot exceed the balance after original visit funds. Cash change is not inferred. |
| One required proof missing or entered as a non-boolean API value | No purchase/conversion is recorded. Cash/check, Zelle and gift-card proof are independent. |
| Earlier verified Zelle bank receipt | Keep its actual earlier date and sender; today's cash/check/gift receipts keep today's date. Missing sender/future date is refused. A transfer already recorded elsewhere must not be entered as new money. |
| Zelle-only or gift-card-only remainder | Use the corresponding received amount and its own required proof. Unused cash/check and bank/gift acknowledgments are not required. |
| Prepaid membership | Record only the remaining full-term payment through supported manual sources. No saved card or fabricated card operation. |
| Duplicate submission or overlapping source purchase | One conversion and one set of receipts; the original funds cannot be used twice. |
| Receipt/benefit/message failure near confirmation | Every new receipt and the source conversion roll back together. The original paid visit remains. |

The receipt date and source belong to each original record. Applied funds are not new money received. Manual gift verification does not call an external gift-card system. One combined message is queued without sending it. Original waivers, counts, capacity and signed evidence remain unchanged.

The final affected-path run passed **102 checks in 88.755s**, including 98 native PostgreSQL cases and four actual Chromium scenarios. It covers all 11 new received-split cases, four new real concurrency/reversal cases, existing paid-visit and first-split behavior, public/card checkout and the reviewed additive upgrade/capability guard. After shortening the selected dropdown label for phones, the final 12-case check passed in 11.845s and the final browser capture passed again in 6.213s. All 12 final 113–118 desktop/phone images were visually inspected, with no overflow, JavaScript errors, duplicate IDs or nested forms. Lint/format (556 Python files), model drift, affected JavaScript syntax, whitespace, all 236 PNGs/links and all 59 migration pins pass; all 58 published migration files/hashes remain unchanged. The prior complete local PostgreSQL suite was 1,588 tests before this increment; the final native inventory is 1,605, and a complete local run of that later inventory is not claimed. The prior published commit passed all four GitHub checks; new CI awaits publication. No external provider/storage call, delivered email, merge or deployment occurred.


## Paid visit with a separately requested card remainder

Review samples **119–124** using fictional data only. Select **Credit card** on the same paid-visit membership purchase page. Review the original money, retained fee, reserved amount, exact new charge and future schedule before accepting terms and confirming once.

| Scenario | Expected result |
| --- | --- |
| $16.47 original card-paid visit; one $17.99 Subscription place | Reserve $16.02 and retain the original $0.45 fee. Request only $1.97 new principal + $0.06 membership card fee = $2.03. Future installments stay $18.53 each. |
| Immediately after confirmation | One accepted membership, one source reservation and one ready card request. New received money is zero; the original $16.47 paid visit, counts, waivers and capacity remain unchanged. No member benefit is used. |
| Uncertain card result | Check the existing payment. No automatic financial retry or second collection. Stop is unavailable; original funds stay reserved and the source notice remains. |
| Card receipt known, completion not yet finished | The $2.03 receipt remains visible independently from applying the original funds. Resume with Continue applying this visit only when offered. This requests no new card payment. |
| Completed source application | Original receipt stays $16.47; its invoice becomes $0.45. Apply $16.02 existing funds to the membership, record only $2.03 new money, fund the $18.05 invoice and use one benefit. One remains available. |
| Failure while applying original funds | The already recorded card receipt survives. Source changes/credit/benefits/release roll back together. Review the notice; an eligible pure completion retry makes no additional charge. |
| Declined/cancelled or still-unattempted ready request | An owner can stop this source application when its current result is known and no new money remains held. Supply a reason. A ready request is cancelled locally. No original refund or booking cancellation is claimed. |
| After stop | Original visit remains paid and unchanged. Membership terms, purchase and payment history remain; the source-specific notice clears. A separate membership-term or fee/refund decision is not performed by this button. |
| First request expires before dispatch | The unattempted 30-minute request is cancelled for review, with source funds still reserved. An uncertain result never causes automatic release. |
| Source fully covers first principal | No zero-dollar card receipt; source application and actual benefit usage finish together. A monthly plan still needs its accepted future-card mandate. |
| Prepaid one-place term after $16.02 source funds | $37.95 new card principal + $1.14 fee = $39.09. No future installments. |
| Global membership price changes later | The accepted purchase/calendar/fee schedule remains fixed. Source or payment corrections still require reconciliation. |

While reserved, a refund, price adjustment or another conversion of the original visit is blocked. Its receipt must never be re-entered as new money. Generic payment/credit controls cannot collect the reserved source amount again, including after a stopped application. Unknown outcomes, real retained fees or money still held require their own reviewed resolution; no refund destination or extra financial authority is inferred.

The direct card branch currently covers the bounded request, known-result source completion, uncertain outcomes and a safe owner stop. Known-failure same-day retry with an eligible saved card is covered below. Brand-new replacement-card entry, mixed manual/card remainder, manual alternatives and source/date exceptions remain in development. Membership cancellation still follows its separate approved controls; a credit-funded cancellation does not bypass the outstanding refund-destination policy. No real provider or customer email was used for the screenshots.

Developer verification: the complete PostgreSQL suite passed **1,629 tests in 707.227 seconds**. After the final future-card binding and replay-handling fixes, **69 focused checks passed in 39.458 seconds**, including 22 paid-visit card cases, five real PostgreSQL concurrency/reversal cases, existing billing/card/collection cases and two actual Chromium scenarios. Changing a future billing card preserves the original accepted first request; a stale continuation after completion or owner stop cannot repeat funds or falsely report a transfer. The final native inventory is 1,633; a complete local 1,633-test run is not claimed. All 12 final desktop/phone images for samples 119–124 were visually inspected. Browser checks report no overflow, JavaScript errors, duplicate IDs or nested forms, with zero external provider/storage calls and zero delivered emails. All 561 Python files pass lint/format checks; migration drift, affected JavaScript syntax, diff whitespace, all 248 PNGs/gallery links and all 60 migration pins pass. All 59 previously published migration files/hashes remain unchanged. The previous published commit passed all four GitHub checks; checks for this increment will run after publication. Features remain off by default and PR #37 remains draft; no merge, deployment or live financial action occurred.

Future-card updates keep existing initial requests and their results on the original accepted card. They do not retry, collect or retarget that request. The pending panel identifies the original session date/time without opening another page.


## Explicit saved-card recovery for a paid-visit purchase — samples 125–128

Use fictional data after a separately authorized staging release. The original card remainder must have a definite decline or cancellation; unknown, sending or ready requests do not expose another financial attempt.

| Scenario | Expected result |
| --- | --- |
| Request another attempt after customer contact | Expand **Try a card payment again** on the existing membership page. Select an eligible saved card, confirm the customer's exact $2.03 authorization and request once. No separate purchase page. |
| Select a different eligible saved card | Card 6789 pays this remainder. Future installments stay on card 1234; neither old request nor original accepted terms is rewritten. |
| Repeated click/reload or concurrent confirmation | One recovery authority and one new request. Different simultaneous reviews cannot both collect the same remainder. |
| New request ready/unknown | No credit or visit benefit usage. Original $16.47 paid visit remains intact and $16.02 stays reserved. An unknown result blocks another request and owner stop. |
| Known success | Only $2.03 becomes new received money. Pure continuation applies $16.02 existing funds and uses one benefit. It does not charge again. |
| Second confirmed decline | Review the latest outcome and authorize a fresh request explicitly. Keep every earlier failed request in history. |
| Original unattempted request expired | It is cancelled without a financial POST. A new same-day review can authorize its own 30-minute request; it does not extend or reuse the old authority. |
| Latest request expires or selected card becomes unavailable | Cancel before financial dispatch. Preserve the original source for reviewed resolution; do not auto-release it or choose another card. |
| Owner stops while latest request is ready | Cancel that latest unattempted request locally and release the original visit reservation. Unknown/sending results block the stop. Original membership terms/history remain. |
| Stale review, source change, other customer's card, missing authorization | Refuse before creating another payment. No generic collection of the full invoice ignoring the reserved $16.02. |

This branch accepts the original or another eligible **already saved** card only. It does not yet save a brand-new recovery card or accept a manual alternative, mixed manual/card payment, later-day date exception or general source/date exceptions. The bounded retained-fee cancellation release is covered in samples 129–132 below. Actual provider outcomes are not established by these simulated samples. The three existing unresolved business policies stay guarded.

The Dashboard notice opens the same paid-visit membership panel and cannot be dismissed while its source application is unresolved. Completion or a safe owner stop clears it. A new failure also creates fresh attention after an older historical acknowledgment. Later scheduled installments retain their own amount, date and payment authority; they do not reuse this first-payment recovery check.

Developer verification: the complete PostgreSQL suite passed **1,656 tests in 736.241 seconds**. After the final first-invoice dispatch and persistent Dashboard-notice corrections, **133 checks passed in 72.767 seconds**, including 19 new recovery cases, six real PostgreSQL concurrency/reversal/runtime cases, existing card/billing/collection/funding checks and three actual Chromium scenarios. Later scheduled installments retain their own payment authority; source notices link to the application, resist premature dismissal and reopen after historical acknowledgment when a new failure occurs. The final native inventory is 1,659; a complete local 1,659-test run is not claimed. Earlier expanded verification passed 68 checks, and the final screenshot capture passed 25 checks. All 20 final new/refreshed images for samples 119–128 were visually inspected; the final browser run repeated behavior/overflow/DOM checks without overwriting those PNGs. There is no overflow, JavaScript error, duplicate ID or nested form in those browser scenarios. All 565 Python files pass lint/format checks; migration drift, diff whitespace, all 256 PNGs/gallery links and all 61 migration pins pass. All 60 previously published migration files/hashes remain unchanged. All four GitHub checks passed for the prior published commit; checks for this increment run after publication. No external provider/storage request, delivered customer email, merge or deployment occurred. Features remain off by default and PR #37 stays draft.


## Release a paid visit after membership cancellation — samples 129–132

For a later authorized staging test, start from a first membership purchase whose original paid visit is still reserved and whose separate card remainder is known received. Do not re-enter the original visit receipt. Record the membership cancellation and the owner's chosen refund through the existing controls before closing the source application.

| Scenario | Expected result |
| --- | --- |
| $2.03 received, owner chooses $1.97 refund | Original $16.47 visit stays intact, $16.02 stays reserved, and membership refund still due is $1.97. No source-release button yet. |
| Refund queued, sending or outcome unknown | Review the existing refund. No new attempt or source release; Dashboard attention remains. |
| $1.97 returned to the actual receipt card 6789 | The same page shows $0.06 held and the original funds reserved. Future membership card 1234 is unchanged. |
| Owner enters a reason and releases original visit funds | Cancel exactly $16.02 never collected on the membership, release the reservation and keep the original visit invoice/receipts at $16.47. No refund is sent by this button. |
| Owner chose a partial $1.00 refund | After that actual refund, $1.03 is retained: $0.97 principal and $0.06 fee. Release preserves that choice rather than silently refunding another $0.97. |
| Owner chose no refund | $2.03 stays retained. The cancelled uncollected $16.02 does not create a new receipt, refund or customer credit. |
| Reload, repeat confirmation or simultaneous owner actions | One release and one matching uncollected adjustment. A stale or different review cannot repeat them. |
| Local completion fails after the real refund was already recorded | Refund history stays recorded. The source release and its adjustment roll back together and can be reviewed again without another refund. |
| Cancellation is future-effective, funds are unknown or original visit changed | Block release with a reason. No automatic date exception, financial retry or source correction. |
| All selected refunds are complete, but the application is not released | Keep the source Dashboard notice until the owner finishes the release. After commit, clear that notice; unrelated notices remain separate. |
| After release, a new separately accepted membership is bought | Original funds may be reviewed for that new purchase only after the first reservation is actually released. The cancelled membership stays cancelled and cannot activate benefits. |

This is an explicit cancellation-linked release before any visit credit or benefit was applied. A credit-funded cancellation still requires the outstanding refund-destination decision. Full external voids returning retained fees, historical tax corrections, general date/expired-term corrections and new-card/manual-alternative recovery remain separate guarded work. An effective cancellation may be closed later without backdating payment dates, purchase terms or signatures.

Developer verification: the complete PostgreSQL suite passed **1,683 tests in 782.583 seconds** with the final financial/service/schema changes. The final copy clarification then passed **18 checks in 19.205 seconds**, including all 17 new native cancellation-source cases and the actual Chromium refund/release scenario; it changes only the heading/success message to distinguish reserved funds from the booking. Earlier final-focused verification passed **88 checks in 81.639 seconds**, including six new real PostgreSQL concurrency/reversal/runtime-grant cases and existing cancellation/deployment checks. All eight final desktop/phone images for samples 129–132 were visually inspected. Browser assertions report no overflow, JavaScript errors, duplicate IDs or nested forms, with zero external provider/storage calls and zero delivered emails. All 569 Python files pass lint/format checks; migration drift, diff whitespace, all 264 PNGs/gallery links and all 62 migration pins pass. All 61 previously published migration files/hashes remain unchanged. All four GitHub checks passed for the prior published commit; checks for this increment run after publication. Membership and collection features remain off by default and PR37 remains draft. No merge, deployment or live financial action occurred.


## Enter a new card for a failed paid-visit remainder — samples 133–135

For a later authorized staging test, use a paid-visit membership purchase whose first card remainder has a definite decline or cancellation. Open **Try a card payment again**, choose a saved card or **Enter a new card**, record the customer's Yes/No future-visit choice and confirm the exact amount. One final action saves the card and requests that remainder. It does not change the future installment card or original accepted terms.

| Scenario | Expected result |
| --- | --- |
| New card, No future visits | Store only for this unresolved first payment. Request exactly $2.03, not the full $18.05 invoice. No new receipt or benefits until the financial result is known. |
| New card, Yes future visits | After the explicit payment request, the retained card appears for future bookings and replaces the prior future-visit card. Before confirmation it is excluded from that selector. Future membership installments stay on their original card 1234. |
| Save succeeds but financial confirmation was not submitted | On reload the known card remains selectable for this same purchase. No payment is inferred from saving. |
| Save is uncertain or the response is lost | Check the existing setup. Reload does not save again. No replacement card payment or source release until storage is reconciled. |
| Owner reconciles the existing save | Provider lookup identifies its single actual method; no new card-save POST. Staff then review and request payment explicitly. An ambiguous/missing method remains guarded for provider support. |
| Another staff/browser has an unresolved setup | Show the existing setup review rather than a second new-card action. Original authorized browser scope is required for setup-status data. |
| Storage review expired before exchange | Refuse a fresh nonce. If the card was already known saved, review that known selection again rather than saving it again. |
| Original payment/source/customer/billing details changed | Refuse the stale storage or financial review. Preserve original accepted purchase, receipts, source reservation and signatures. |
| New request definitely declines | A fresh explicit review may reuse this known nonretained card for the same purchase. No automatic retry. |
| Abandoned future-visit Yes choice | The previous saved future-visit card remains. After source release and setup expiry, the unconfirmed new choice is removed through normal disposal. |
| Nonretained source after completion/closure | Keep it while needed by this unresolved source/payment; dispose only after those obligations are resolved. Keep all financial history. |

The screenshot provider areas are labelled simulations. Actual Banquest hosted-field layout, tokenization and processor behavior still require separate permitted provider verification. Manual alternatives, mixed manual/card remainders and general date/source exceptions remain separate work. The three unanswered policies stay guarded without inferred defaults.

Developer verification: the complete PostgreSQL suite passed **1,704 tests in 801.772 seconds** before the final retained-card selector and scoped hidden-control CSS corrections. After those corrections, **57 focused checks passed in 38.556 seconds**, including the new future-visit selection case, all 16 new storage cases, existing saved-card/card-setup behavior and two actual Chromium scenarios. The final native inventory is 1,705; a complete local 1,705-test run is not claimed. Earlier expanded verification passed **113 checks in 62.633 seconds**, including five new real PostgreSQL concurrency/reversal/runtime cases, cancellation, scheduled collection, disposal and deployment checks. All six final 1440px/390px images for samples 133–135 were visually inspected. Actual browser assertions cover payment-action/authorization visibility during uncertain storage, reload and no repeated exchange, with no overflow, JavaScript errors, duplicate IDs or nested forms. All 573 Python files pass lint/format checks; model drift, affected JavaScript syntax, diff whitespace, all 270 PNGs/gallery links and all 63 migration pins pass. All 62 previously published migration files/hashes remain unchanged. Provider/storage calls were mocked, external requests blocked, and no customer email delivered; actual hosted fields and processor behavior remain unverified. Prior-commit GitHub checks are recorded separately; checks for this increment run after publication. Features and scheduled collection remain off by default, PR37 stays draft, and no merge, deployment or live financial action occurred.


## Received replacement after a paid-visit card failure — samples 136–138

For a later authorized staging test, open a membership whose paid visit is reserved and whose first card remainder is definitely declined or cancelled. Open **Record received payment instead** on that same page. Record only money actually received; this action does not collect it from a bank or gift provider. The fixed amount covers the full remainder using one tender. Mixed manual/card remainder is still separate work.

| Scenario | Expected result |
| --- | --- |
| Cash/check for the example remainder | Record $1.97 today, remove only the unused $0.06 card fee, then apply $16.02 original visit funds. First membership total becomes $17.99. No receipt-date step for cash/check. |
| Zelle | Verify the bank, enter its actual receipt date and sender. An earlier bank date is allowed; a future date is refused. Saving the receipt does not claim a bank transfer was initiated. |
| Physical gift card | Staff must physically check it and verify the exact amount received. This pays membership goods; it does not make gift cards available for cancellation fees. |
| Original source and future card | Original receipt stays $16.47 in history, with its $0.45 fee retained. Future membership card 1234 and accepted installment amounts remain unchanged. |
| Card still ready, sending or uncertain | No manual replacement offered. Check the existing card outcome first. |
| New-card storage still uncertain | No manual replacement, new payment or source release. Reconcile the existing setup first. |
| Double click or stale simultaneous card/manual choices | One actual receipt/authority, or one card request. They cannot both claim the same remainder. |
| Local visit application fails after payment was recorded | Keep the known $1.97 receipt and fee adjustment. Original visit stays intact and reserved, no benefit/credit is used, Dashboard review persists. **Continue applying this visit** uses the existing receipt, without another collection. |
| Owner cancels before applying the visit | Use the existing cancellation controls and chosen actual original-tender refunds, then release original visit funds. Full $1.97 return leaves no membership money held; a chosen $0.97 return retains $1.00. No refund retains $1.97. All choices preserve the original $16.47 visit, and create no visit credit or benefit. |
| Receipt or source changed, another correction exists | Stop for review rather than repeating collection or silently changing original accepted terms. |

Cash change, new mixed-tender authority, general date/source corrections and the three outstanding business policies are not inferred by this feature. Financial data in these samples is fictional; no external financial action or email delivery was performed.

Developer verification: the complete PostgreSQL suite passed **1,730 tests in 841.103 seconds** before the final manual-only cancellation-source safeguard and removal of the redundant application checkbox. After those changes, **111 focused checks passed in 133.077 seconds**, including all 18 manual-receipt cases, seven real PostgreSQL concurrency/reversal/runtime cases, existing card/storage/cancellation behavior, reviewed deployment and two actual Chromium scenarios. The final native inventory is 1,731; a complete local 1,731-test run is not claimed. All six final 1440px/390px images for samples 136–138 were visually inspected. Browser checks cover conditional bank fields, exact receipt/application totals and recovery without duplicate money; no overflow, JavaScript errors, duplicate IDs or nested forms were found. All 577 Python files pass lint/format checks; model drift, JavaScript syntax, diff whitespace, all 276 PNGs/gallery links and all 64 migration pins pass. All 63 previously published migration files/hashes remain unchanged. Provider/storage calls were mocked or blocked, and no customer email was delivered. All four GitHub checks passed for the prior published commit; new checks run after publication. Features/collection remain off by default, PR37 stays draft, and no merge, deployment or live financial action occurred.


## Recorded bank evidence and paid-visit history — samples 139–140

For a later authorized staging test, open a known Zelle payment. Its recorded bank date and sender appear on the payment page; pending paid-visit applications show those details on the same membership screen. The normal **Payment transactions** CSV adds receipt-origin evidence and the original receipt reference/recording staff/time when earlier received funds were applied. Missing bank evidence is not inferred from customer details or a card request.

From **Memberships → Export filtered memberships**, choose **Paid visit application history**. It includes all matching memberships across every results page, subject to the separate export, booking-view and payment-view permissions. Downloads remain private and audited.

| Check | Expected result |
| --- | --- |
| Original $16.47 visit, $1.97 new Zelle, completed conversion | Original invoice funds $16.47 once; new membership money $1.97; converted credit created/applied $16.02; original processing fee retained $0.45; unused new-card fee removed $0.06. Credit/adjustments are not new receipts or bank refunds. |
| Tax components | Converted credit identifies original $15.00 principal, $0.99 item tax and $0.03 fee tax, preserving the original tax treatment. |
| Card outcome is unknown | Requested amount and unknown state remain visible, with zero newly received money and no converted credit. |
| Old application stopped, same visit used for a new purchase | Original invoice payment appears once, linked to the matching memberships. Separate member attempts remain separate transactions. |
| Visit converted toward a membership purchased earlier | The visit's source and credit are shown; the earlier membership purchase is not labeled new conversion money. |
| Cancellation and actual return | Show the actual membership refund separately. Releasing $16.02 never collected is an invoice adjustment, not a refund of the original $16.47 visit. |
| Bank recorded earlier by one staff member, applied later by another | Retain original bank date/sender/reference/recording staff/time, separately from the invoice-application actor and timestamp. |
| Download or repeat download | Receipts, postings and credit remain unchanged; each prepared download has its own export-history entry. |

The report describes recorded invoice/source history, rather than a complete bank statement. Blank actual dates stay blank when no provider date was recorded; staff-recording timestamps are separate. Later provider observations remain in the existing payment records. No new bank transfer, card collection, refund or customer message is performed by viewing or downloading.

Developer verification: **91 focused PostgreSQL/application/browser checks passed in 62.138 seconds** with the final code and compact layout, including all 15 new history/evidence cases, existing payment views/runtime grants, Zelle/source reports and the actual Chromium download scenario. The browser downloaded both CSV reports and verified original invoice funds $16.47, new money $1.97, converted credit created/applied $16.02, unused fee removed $0.06 and retained original fee $0.45. Receipt/posting counts stayed unchanged; two export audits were recorded. All four final 1440px/390px images were visually inspected, with no overflow, JavaScript errors, duplicate IDs or nested forms. All 580 Python files pass lint/format checks; system checks, model drift, diff whitespace, all 280 PNGs/gallery links, the nine-row actual-download review CSV and all 64 migration pins pass. All 64 previously published migration files/hashes are unchanged. All four GitHub checks passed for the prior published commit; the full suite for this new increment runs after publication. External provider requests were blocked/mocked and no customer email was delivered. Actual Banquest hosted fields/processor behavior remain unverified. Features and collection stay off by default; PR37 remains draft with the broader stage still in progress. No merge, deployment or live financial action occurred.


## Paid early-renewal review — samples 141–142

This is a temporary safeguard for the existing unanswered policy about a separately paid early renewal when an earlier term later develops arrears. It does not decide where either payment belongs or authorize a debt transfer.

| Check | Expected result |
| --- | --- |
| Buy a prepaid renewal early while the current monthly term is up to date | Future dates, the actual renewal receipt and accepted terms are recorded normally. Not-yet-due earlier installments do not block it. |
| An earlier required installment later becomes unresolved | The paid renewal shows Review with a direct link to the earlier membership; the owner Dashboard lists it. The renewal's own installment and receipt remain paid. New benefit use pauses. |
| An existing future booking already reserved a renewal benefit | Original price and reservation remain recorded; the owner explicitly resolves that booking using the existing ordinary-price, cancellation, payment-resolution or single-booking honor workflow. Staff cannot silently honor an unavailable benefit. |
| Record the known required earlier payments after normal verification | Review and Dashboard reminder clear. The renewal remains one original receipt; no replacement renewal payment is requested. |
| Review reports for an explicit date | Membership status and payment/benefit eligibility use that same date. |
| Already queued renewal confirmation during review | Delivery is withheld; no email claims the benefits are ready. Existing delivered history is not rewritten. Resolving payment does not silently resend an earlier cancelled message. |
| Complimentary renewal or unrelated purchase | Existing rules apply; no automatic arrears transfer or new fee is created. |

Developer verification: the complete PostgreSQL suite passed **1,756 tests** before the final own-payment eligibility distinction. The final expanded run then passed **103 checks**, including all eleven new paid-renewal review cases, renewals, reporting, benefit reservations with real PostgreSQL concurrency, per-booking owner decisions and collection preparation. An unpaid or known-failed renewal keeps its ordinary pending-payment state and is never labelled paid. The final native inventory is 1,757; a complete local 1,757-test run is not claimed. A separate actual Chromium scenario verified the paid receipt, parent link, Dashboard reminder and its disappearance after known earlier payments were recorded, without a second renewal receipt. All four final 1440px/390px images were visually inspected, with no overflow, JavaScript errors, duplicate IDs or nested forms. All 582 Python files pass lint/format checks; system checks, model drift, whitespace, all 284 PNGs/gallery links and all 64 migration pins pass. All 64 published migration files/hashes and the earlier CSV sample are unchanged. All four GitHub checks passed for the prior published commit; this increment starts its own checks on publication. External requests were blocked/mocked and no customer email was delivered. Provider behavior remains unverified. Features and collection remain off by default; PR37 stays draft, with the broader stage still in progress. No merge, deployment or live financial action occurred.


## Combined cash/check renewals — samples 143–145

For a later authorized staging release, open the customer’s **Memberships → Renew memberships together**. The source records remain separate. Choose the places to renew, type, whole-month duration and monthly/pay-in-full billing on the same page; review the original expiry, new start/end, terms and combined total.

| Check | Expected result |
| --- | --- |
| Different original expirations | Each renewal begins according to its own existing early/grace rules. Combining the checkout does not align or consolidate the terms. |
| Renew fewer places | Only the selected count is renewed; the remaining original places are available for a separate choice. |
| Split types or terms | Use Split this renewal, then choose each entry. The total selected from that source must fit its remaining places. The same source ID remains visible. |
| Monthly billing | Choose a permitted saved card for each row’s future installments. Those accepted schedules/cards stay separate; the initial grouped action records cash/check only. |
| Normal term minimum and late renewal | Existing minimums remain. Only the owner can explicitly select the shorter-term exception when applicable. |
| Change count, type, term, billing, method or source | The total refreshes and acceptance/verification reset. No receipt, purchased record, benefit usage or booking capacity is created by preview. |
| Final confirmation | Verify the full cash/check amount was actually received, accept the current terms and click the labelled final button once. See the same-page saved total/date and separate allocation links. |
| Repeat the same submitted action or reload | Return the existing result, rather than another renewal or receipt. A different checkout cannot spend already renewed original places. |
| Price, contact or original places changed | Review the complete current checkout again. A second-row issue rolls back the new group’s records and allocations together. |
| Prepared confirmation | One group email includes every accepted renewal’s actual dates and payment truth. Each renewed record shows this shared status, including the second or later record. A change in any included funding/cancellation is checked before delivery. |
| Changed customer email | Preserve the original queued snapshot/history and prepare one current combined replacement; do not duplicate separate member confirmations. |
| Email preparation paused | Known receipts and message history stay intact when email is paused. New sales still respect the existing workflow feature gates; preparation and delivery never record another receipt. |
| Another tender or no payment due | Use the existing individual renewal/owner complimentary workflow; no zero-dollar receipt or unsupported group card/bank transfer is fabricated. |
| Existing earlier term has unresolved required payments | Existing renewal/payment review safeguards apply; none of the unanswered debt policies is decided by combining checkout. |

Authorized membership/customer viewers can still read the saved receipt when new sales are paused; creation continues to require sale/collection permissions. The final recorded page links to each member, and each member links back to the combined payment. Original prices, terms, signed evidence and past usage are retained. Grouping is a checkout convenience, not owner cohort consolidation. Membership-only purchase does not bypass the normal booking, capacity or waiver flow. A prepared email is not a delivered email.

Developer verification: the complete PostgreSQL suite passed **1,795 tests** with the final application code, including all 38 new combined-renewal cases. The preceding focused run passed **84 checks**, covering existing renewals/parent review, actual concurrent submissions, used/unused schema reversal, runtime grants, read-only history and deployment compatibility. A separate final Chromium scenario exercised split preview, distinct start dates, actual form confirmation, reload and return links at 1440px/390px. It recorded fictional $17.99 + $39.99 once, prepared one shared confirmation and left original quotes intact; preview created no payment, booking or benefit usage. All six final images were visually inspected with no overflow, JavaScript errors, duplicate IDs or nested forms. All 589 Python files pass lint/format checks; system checks, model drift, JavaScript syntax, whitespace, all 290 PNGs/gallery links and all 65 migration pins pass. All 64 previously published migration files/hashes and the earlier CSV sample remain unchanged. All four GitHub checks passed for the preceding published commit; new checks run after publication. External requests were blocked/mocked and no customer email was delivered. Provider behavior remains unverified. Features and scheduled collection remain off by default; PR37 stays draft and the broader stage continues. No merge, deployment or live financial action occurred.


## Find more renewal records without losing entries — sample 146

For a customer with more than ten available records, the combined renewal page includes a membership-number/type search and **Show more memberships**. Records already fully renewed are removed before the page limit. Selected rows stay in place while unselected candidates change. Their detail controls expand only when selected.

| Check | Expected result |
| --- | --- |
| Select a monthly renewal, adjust places/months/card and choose check | Keep those entries while searching another membership number or type. The current total remains visible on the same page. |
| Load another page | Retain selected rows and payment method; show more eligible original records. Do not create a receipt, renewal, booking or benefit use. |
| Leave selected counts invalid or a required future card blank | Preserve the entered row and show its correction; never silently discard it. |
| Review after browsing | Refresh the current dates, available places, terms and price. Accepted-terms and received-money confirmations reset for the current review. |
| Confirm once | Record the reviewed positive cash/check allocations once and retain the existing shared-confirmation/history behavior. |

No schema, financial authority or additional group payment method is introduced by browsing.

Developer verification: the final expanded PostgreSQL run passed **109 checks in 48.736 seconds**, including eight new renewal-list cases, combined and individual renewal services/views, real concurrency, notices and booking renewal prompts. The earlier focused run passed 69 checks. Two actual Chromium scenarios passed in 13.413 seconds: search/show-more retained the selected monthly details, future card, payment method and request identity without recording money; final combined confirmation recorded fictional $17.99 + $39.99 once, with one shared prepared confirmation and no duplicate on reload. All eight refreshed/new desktop/phone images were visually inspected, with no overflow, JavaScript errors, duplicate IDs or nested forms. All 591 Python files pass lint/format checks; system checks, model drift, JavaScript syntax, whitespace, all 292 PNGs/gallery links and all 65 migration pins pass. All 65 published migration files/hashes and the earlier CSV sample remain unchanged. The published baseline passed the complete 1,795-test suite; the current native inventory is 1,803, and a complete local 1,803-test run is not claimed. All four GitHub checks passed for the prior published commit; new checks run after publication. External requests were blocked/mocked and no customer email was delivered. Actual Banquest behavior remains unverified. Features and scheduled collection stay off by default, PR37 stays draft and the broader stage continues. No merge, deployment or live financial action occurred.


## Combined renewals with one Zelle transfer — samples 147–149

For a later authorized staging test, choose **Renew memberships together → Zelle received**. Verify one new transfer for the entire reviewed amount in the business bank account. A transfer already recorded on another booking/payment is applied through its existing workflow. This does not access the bank.

| Check | Expected result |
| --- | --- |
| Two types with separate expirations | Review the $17.99/$39.99 allocations and $57.98 combined total. Each new term still follows its own original expiry. |
| Actual bank date/sender | Enter the receipt date (today or earlier) and sender shown by the bank. A future date or missing sender is refused. This date remains separate from when staff records the purchase. |
| Search or Show more | Keep bank fields, tender, selected renewal details and request identity on the same page; refresh review/acceptance. No receipt is created. |
| Confirm received transfer | Verify the full bank transfer and accept terms. One original source backs the two allocations, one combined confirmation is prepared and no card is charged. |
| Refresh the saved receipt | Show the original date/sender, full original received amount and both allocation links. Create no second receipt, renewal or email. |
| Open either payment | Identify its portion of the original transfer and return directly to the shared receipt. The payment CSV identifies the source; sum recorded transaction amounts, not the reference-only shared total. |
| Refund one membership allocation | Use the existing owner-reviewed cancellation and actual manual return controls. Preserve the original bank receipt and the other membership's funds; never return the whole shared transfer for one allocation. |
| Earlier release/schema | A used bank-source history refuses schema reversal or switching to code lacking the exact capability. With no such bank source, unused reversal restores the preceding published function. |

Cash/check continue to use today without extra date entry. The original source receipt is historical gross money; later actual returns remain in each allocation's financial history. No automatic refund, bank API action or repeat transfer is sent. Group card/gift/credit/split funding and no-payment grants remain unfinished; individual renewal paths continue.

Developer verification: The complete PostgreSQL suite passed **1,826 tests in 1,028.921 seconds** with the final application code. The final focused run passed **46 checks in 61.324 seconds**, including all 16 new bank-funding cases, five real transaction/concurrency/reversal cases and reviewed deployment compatibility. Three final actual Chromium scenarios passed in 19.880 seconds, covering cash confirmation, same-source split preview, search/show-more with preserved monthly selections, and the new Zelle flow: one fictional $57.98 verified transfer, $17.99/$39.99 allocations, actual October 29 bank date and sender preserved during browsing, one unsent shared confirmation, reload without duplication, shared-source payment links and $57.98 total in transaction exports. All fourteen refreshed/new 1440px/390px images were visually inspected with no overflow, JavaScript errors, duplicate IDs or nested forms. All 594 Python files pass lint/format checks; system checks, model drift, JavaScript syntax, whitespace, all 298 PNGs/gallery links and all 66 migration pins pass. All 65 previously published migration files/hashes and the earlier actual-download CSV sample remain unchanged. All four GitHub checks passed for the prior published commit; new checks run after publication. External provider/storage requests were mocked or blocked, no bank API was called and no customer email was delivered. Actual Banquest behavior remains unverified. Features/collection remain off by default, PR37 stays draft and broader stage work continues. No merge, deployment or live financial action occurred.


## Correct an unused membership's dates — samples 150–152

Open an unused standalone prepaid or complimentary membership whose current start date is today or later. Expand **Correct membership dates** on its existing page. Enter the intended start date and reason, choose whether to email the updated dates, review the current/new term together, confirm that the customer agreed and save once.

Expected results:

- The same M number remains. No new membership purchase or payment is created. Original accepted dates, terms, prices, cycle identities and receipt history remain intact.
- The current term and booking eligibility use the new dates. Date history retains both terms, the reason, staff member and time. A change to date, reason or email choice requires reviewing the current change and confirming the customer's agreement again.
- The existing prepaid payment stays received on its original receipt date. The original payment schedule is labelled separately from corrected benefit dates. Membership and payment history remain readable if sales are paused; paused mutations remain blocked.
- A booking outside the original term but inside the corrected term may use the corrected benefits. It reserves and consumes the existing cycle identity, preserving the normal quota. A booking outside the corrected term gets no benefit from this membership.
- Renewal/grace timing, expiry notices, member search/filter dates, private receipt dates and unused-term cancellation suggestions follow the corrected benefit calendar. CSV exports retain original start/end dates alongside the current dates.
- Selecting Yes prepares one date-only update with no repeated claim of newly received money. Selecting No prepares none. Earlier unsent original-date messages are retained as cancelled evidence. Current contact changes stay scoped to the correction; an attempted/unknown message is never automatically retried.
- Two simultaneous corrections cannot both use an obsolete review. A conflicting booking reservation and date correction cannot both commit. Used calendar evidence cannot be removed through database reversal or an incompatible code switch.

This is the initial bounded correction path. Monthly schedules, already used/started/expired terms, terms with linked additions/renewals, combined pending purchases and unresolved funding/refunds are not yet supported for date correction. General corrections, owner consolidation and nonpurchase grants remain within the unfinished third-stage scope. No new permission to collect, refund, deliver customer mail or deploy is implied.


Developer verification: the complete PostgreSQL suite passed **1,858 tests in 1,106.692 seconds** with the final application code. The related screen/accounting run passed **119 checks in 46.681 seconds**; the final boundary/browser run passed **36 checks in 15.891 seconds**, including actual desktop/phone review, save, reload, safe non-JSON failure/recovery and paused-history navigation; committed correction/reservation races; runtime grants; and used/unused reversal and release compatibility. Tests cover a booking after the original expiry but inside the corrected term, the current customer summary, unchanged original cycle IDs/receipts and credit alerts at corrected expiry without expiring the credit. All six new 1440px/390px images were visually inspected with no overflow, JavaScript errors, duplicate IDs or nested forms. All 602 Python files pass lint/format checks; system checks, model drift, JavaScript syntax, whitespace, all 304 PNGs/gallery links and all 67 migration pins pass. All 66 previously published migration files/hashes and the earlier actual-download CSV remain unchanged. All four GitHub checks passed for the preceding published commit; this update starts its own checks after publication. Provider/storage requests were mocked or blocked and no customer email was delivered. Actual Banquest behavior remains unverified. Features and collection stay off by default, PR37 stays draft and broader stage work continues. No merge, deployment or live financial action occurred.


## Received portion with a remaining card payment — samples 153–156

For later authorized staging tests, use an eligible same-day paid-visit membership purchase whose first card request has a known failed outcome. Open **Split the remaining payment** on the same membership page.

| Check | Expected result |
| --- | --- |
| Review $0.97 cash against $1.97 new principal | Show $1.00 remaining card principal, $0.03 card fee, $1.03 card request and revised $18.02 total. Remove only the unused $0.03 original fee. Preview records nothing. |
| Change amount, tender, card or bank fields | Refresh the current review and reset both received-payment and card authorization confirmations. An interrupted/non-JSON review disables the financial action until a fresh review succeeds. |
| Choose Zelle received | Require the actual bank receipt date and sender, retained in the receipt and exports. Cash/check use today without an extra date entry. A physically presented gift card requires actual staff verification. |
| Confirm once | Commit the actual received portion first, then create the exact remaining card request separately. Preserve the original paid visit and reserved funds until full funding is known. Reload/repeated submissions cannot duplicate either portion. |
| Card preparation fails locally | Keep the actual cash/Zelle receipt. Show no new card request when none was created; allow only an explicit request for the remaining amount. Do not collect or record the known received portion again. |
| Card declines or is unknown | A known decline permits an explicit remainder-only retry. An unknown result blocks another request until the existing transaction is reconciled. No automatic retry or fabricated success. |
| Complete after known exact funding | Show $2.00 new money separately from $16.02 applied credit. Preserve the original visit's gross receipt and retained $0.45 fee. Apply source funds/benefit once, prepare one confirmation, and retain all failed attempts as history. |
| Cancel before card funding | Reconcile the owner-selected actual refund or retained received amount. Remove the uncollected card principal and unused fee along with releasing original visit funds. Never label never-collected money as refunded. |
| Cancel after card funding | Preserve the actually charged card fee and reconcile actual refunds through the existing controls. Original visit funds remain independently protected. |
| Pause sales | Keep saved history readable; refuse new financial actions. Previously published full-card/full-received recovery controls cannot duplicate a saved split. |

Future scheduled-installment authority remains separate. This first split path uses an already eligible saved card; entering a new card inside a saved split, later-day conversions and additional source exceptions remain unfinished. The screenshots use fictional data and simulated outcomes, not actual Banquest verification.

Developer verification: the complete PostgreSQL suite passed **1,887 tests in 1190.246 seconds** with the final application code. The related cancellation/recovery/deployment run passed **98 checks in 66.442 seconds**; six actual-commit concurrency/reversal cases passed in **11.097 seconds**. The final **18-check run in 36.627 seconds** includes the 16 split service cases and two actual Chromium desktop/phone scenarios. It verifies read-only preview, changed-consent reset, non-JSON failure/recovery, exact separate receipts, original funds/benefits untouched before full funding, preserved known receipts after interrupted card preparation, explicit remainder-only retries and unknown-outcome blocking. Cancellation tests cover partial/full funding, actual partial refunds and exact unused-fee removal. Raw SQL rejects forged amounts, fee reductions and rewritten evidence. Used schema reversal is refused; unused reversal restores all six prior function definitions and reapplies.

All eight new 1440px/390px images were visually inspected with no overflow, JavaScript errors, duplicate IDs or nested forms. All **609 Python files** pass lint/format checks; system checks, model drift, JavaScript syntax, whitespace, all **312 PNGs/gallery links** and **68 migration pins** pass. All **67 previously published migration files/hashes** and the earlier actual-download CSV remain unchanged. All four GitHub checks passed for the preceding published commit; this update starts new checks after publication. Provider/storage requests were mocked or blocked, no bank or gift-provider API was called and no customer email was delivered. Actual Banquest behavior remains unverified: a fresh public hosted-field SDK GET returned a workspace-proxy 403; its tokenization host is absent from the current allowed-host list. No network settings were changed. Features and scheduled collection remain off by default, PR37 stays draft and broader Stage3 work continues. No merge, deployment or live financial action occurred.


## Owner date exceptions for unused terms — samples 157–159

For a later authorized staging test, open an unused standalone prepaid or complimentary membership as owner. Expand **Correct membership dates** on its existing page. A term that has started/expired, or a proposed past start, uses the explicit owner acknowledgment in the current review. There is no extra confirmation screen or second acknowledgment checkbox.

| Check | Expected result |
| --- | --- |
| Started or expired but never assigned to a booking | Owner may review a different start while retaining duration, places, prices, original receipts and the same membership number. The current and corrected term appear together. |
| Staff account | Ordinary future-date corrections remain available. Staff cannot approve a past start or change a started/expired term through this owner exception. |
| Change dates, reason or email choice | Clear the acknowledgment and disable it while review is pending. Show the current owner wording before allowing confirmation. Leaving an unchanged field does not discard a valid review. |
| Save once | Record the owner, reason, agreement, before/after dates and exception marker. Repeating or reloading cannot add a second correction/payment. Original accepted evidence remains available. |
| Email Yes/No | Yes prepares one current dates-only update; No prepares none. A prepared update is not delivered money/payment evidence. Existing current-contact and uncertain-message safeguards continue. |
| Active, Scheduled or Expired | Status, current benefit dates, reporting and renewal timing follow the corrected calendar. Original receipt dates and original payment schedule remain separate. |
| Existing cycle identities | Future eligible booking uses the existing corrected cycle identity and normal quota. No booking or benefit use is created by the date correction itself. |
| Existing benefit assignment, even if later released | Refuse this unused-term exception. Monthly schedules, linked additions/renewals, cancellations and unresolved funds also stay outside this path. Owner approval cannot bypass those guards. |
| Without JavaScript | Review the current dates on the same page, then use the displayed owner acknowledgment and Save. Normal JavaScript uses live review and one Save action. |
| Sales paused or older release | Saved dates/owner history remain readable; new date changes stay blocked. Used owner-exception authority cannot be removed by a database reversal or incompatible release switch. |

Used/monthly/linked-term corrections, owner consolidation and nonpurchase grants remain unfinished. No automatic historical repricing, financial collection, refund or customer-email delivery is performed by reviewing these examples.

A stale confirmation after a booking reserves benefits returns to the existing membership page with a clear explanation, preserving the original dates and payments.

Developer verification: the complete PostgreSQL suite passed **1,910 tests in 1188.100 seconds** before a final navigation-only fix. After adding a clear same-page return message for a stale JavaScript-disabled form, the final related run passed **83 checks in 36.757 seconds** with the final application code, including all 24 new owner-service/screen/database/race/release cases, existing calendar behavior and three actual Chromium scenarios. Browser checks cover owner approval of an unused expired term, preserved original payment/history under the same M number, JavaScript-disabled review/save, explicit past-date wording, non-JSON recovery, paused history and reload without duplicate records. Agreement stays disabled until the current wording is ready; unchanged blur events retain a valid review. The fallback's cached bound-field label was corrected and regression-tested. A stale confirmation after another booking reserves benefits returns an explicit explanation and changes no dates/payments. The current native inventory is 1,911; a separate full 1,911-test local rerun is not claimed.

Actual transaction races permit one current correction or conflicting benefit reservation, never both. Raw SQL rejects missing/false owner authority and forged staff authority. Runtime grants allow the intended append-only correction. Used owner history refuses reversal; unused reversal preserves ordinary correction history and restores the preceding scope exactly. Tests retain original accepted dates/cycle IDs/prices/terms, original cash/complimentary funding, current-cycle eligibility and correct Scheduled/Active/Expired reporting without new money or benefits.

All six new 1440px/390px images were visually inspected. All **612 Python files** pass lint/format checks; system/model-drift/JavaScript/whitespace checks, all **318 PNGs/gallery links** and **69 migration pins** pass. All **68 preceding published migrations/pins**, all **312 previous screenshot bytes** and the earlier actual-download CSV remain unchanged. All four GitHub checks passed for the preceding published commit; this update starts its own checks after publication. External requests were blocked/mocked, no customer email was delivered and no live financial action occurred. Actual Banquest behavior remains unverified; the latest public hosted-field SDK GET returned a workspace-proxy 403 and no network settings were changed. Features/collection remain off by default, PR37 stays draft and the broader stage continues. No merge or deployment occurred.


## Combined renewals using existing credit — samples 160–162

For a later authorized staging test, open **Renew memberships together** from a customer with actual recorded available credit and eligible prior memberships. Use **Customer credit** on the existing combined renewal page. This path covers the selected first payments in full; it does not receive new money or choose a cancellation refund destination.

| Check | Expected result |
| --- | --- |
| Select separate renewals | Review counts, type, dates, duration and accepted terms together. Prior-place limits and renewal minimums still apply, including split types from one prior membership. |
| Full-credit preview | Show credit to apply, $0.00 new money received and remaining available credit. Creating or changing a review writes no purchase, receipt, hold or application. |
| Prepaid renewal | Require no card when credit covers the full principal. Create no zero-dollar charge or new cash/check/Zelle receipt. |
| Monthly renewal | Accept a separate eligible future card. First principal is covered by credit without an unused card fee; later dates/fees and card authority remain visible and separate. |
| Insufficient or held credit | Clearly refuse the combined total. Retain selected entries so staff can adjust them or choose another method. Do not automatically charge a backup card. |
| Change counts, terms, card or funding source | Clear both acceptance and credit authorization while the current total loads. Leaving an unchanged field preserves the current review. |
| Final action | After current acceptance and credit authorization, apply the reviewed amount once and record all selected renewals together. A later-child failure rolls back every child and credit allocation. |
| Simultaneous submission or credit adjustment | One current result may commit. No overdraft, duplicate application or overcommitted prior places. Changed sources/contact require a fresh review. |
| Saved result and individual member | Display credit applied separately from money received and link to the same combined record. Original source receipts/dates stay original. |
| Shared email | Prepare one correctly worded confirmation for the selected renewals. Existing contact refresh/uncertain-delivery safeguards apply; queued is not delivered. |
| No JavaScript | Review on the same page, then accept the displayed terms and authorize credit before applying it. |
| Sales paused | Saved credit/funding history remains readable; new financial changes are blocked. Used history refuses reversal or incompatible code. |

Combined card/gift/mixed/no-payment funding remains separate remaining work. The unresolved credit-funded cancellation return destination remains guarded. No actual provider/bank action, customer-email delivery, merge or deployment was used to prepare these examples.

Developer verification: **129 focused PostgreSQL checks passed in 153.397 seconds**, including all 25 new credit service/screen/SQL cases, six actual-commit source/request/reversal cases, two release-capability cases, existing cash/check/Zelle renewals, initial credit purchases and the reviewed upgrade. Two actual Chromium scenarios passed with the final application/style code in **12.590 seconds**, exercising desktop/phone review, exact credit application, saved history/navigation/reload and a monthly JavaScript-disabled fallback. No page overflow or JavaScript errors were observed. Concurrent requests and credit removal cannot overdraw or duplicate funding; a later-child failure rolls back all selected renewals. SQL rejects incomplete graphs, changed accepted terms and inflated initial sources. Runtime append-only authority and used/unused reversal paths pass.

All six new actual-page images were visually inspected, including the final full-width phone card selector. All **617 Python files** pass lint/format checks; system/model-drift/JavaScript/whitespace checks, all **324 PNGs/gallery links** and **70 migration pins** pass. All **69 preceding migration files/pins**, all **318 preceding screenshot bytes** and the earlier actual-download CSV remain unchanged. The complete local regression is now running; its result is pending and is not claimed as a pass. GitHub checks for this new commit also start after publication. External browser requests were blocked and provider/storage gateways mocked; no customer email was delivered or live financial action performed. Features and scheduled collection remain off by default, PR37 stays draft, and broader Stage3 implementation continues.
