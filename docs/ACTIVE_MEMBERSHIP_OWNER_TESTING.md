# Active memberships — owner testing guide in progress

Draft [PR #37](https://github.com/MonkeyDo-Site/MonkeyDoWebsiteNewCode/pull/37) remains under development. The [gallery](reviews/active-memberships/README.md) uses fictional records and simulated card outcomes; no live payment or email delivery was performed. Review images now. The steps below are for a later authorized staging release, with test customers and Banquest test cards. This is not a deployment or live-payment instruction.

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

Combined multi-cohort renewal checkout; owner cancellation-date corrections, expired-term/general corrections, consolidation and nonpurchase grants; combined already-paid first-purchase/visit conversion and uncertain-card cases; credit returns and remaining broader redemption; remaining cross-workflow filters/exports and final provider validation remain in progress. Private customer renewal, explicit private-receipt benefit reservation, inline booking renewal choices/requested reminders, staff replacement-card entry, owner decisions for affected bookings, current-term membership cancellation/refunds without credit applications, paid same-day reconciliation, explicit initial/due-installment and ordinary/supervised arrival credit application, and owner unused-credit corrections are functional. Cancellation of credit-funded terms is blocked pending the credit-return flow. Actual Banquest source-return reconciliation of converted funds and whole provider voids including retained fees still need their separate owner correction workflow. The release feature switch stays off by default.

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
