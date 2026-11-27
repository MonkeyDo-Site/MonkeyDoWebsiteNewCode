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
| Existing Zelle | Keep $10 already recorded for the visit in this example. | Prior Zelle applies once to the visit; only $41.97 new gift-card funds are recorded. Choosing Zelle or split payment as the combined new tender remains under development. |

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

## Known unfinished areas

Zelle/split-tender combined purchase-and-visit checkout; combined multi-cohort renewal checkout; owner cancellation-date corrections, expired-term/general corrections, consolidation and nonpurchase grants; private public-booking benefit actions; combined already-paid first-purchase/visit conversion and uncertain-card cases; credit returns and ordinary-visit/broader credit redemption; remaining cross-workflow filters/exports and final provider validation remain in progress. Private customer renewal, inline booking renewal choices/requested reminders, staff replacement-card entry, owner decisions for affected bookings, current-term membership cancellation/refunds without credit applications, paid same-day reconciliation, explicit initial/due-installment credit application and owner unused-credit corrections are functional. Cancellation of credit-funded terms is blocked pending the credit-return flow. Actual Banquest source-return reconciliation of converted funds and whole provider voids including retained fees still need their separate owner correction workflow. The release feature switch stays off by default.

Actual Banquest hosted fields and installment processor flags are not verified by the fictional gallery. Three policy answers about later installments after failure, parent arrears after prepaid early renewal, and credit-funded cancellation refund destinations remain pending in the [implementation record](ACTIVE_MEMBERSHIP_IMPLEMENTATION.md). The disputed automatic branches are not enabled, and no credit-refund destination is assumed.

The final guide will add those completed flows, exact release prerequisites and the approved deployment handoff. Merging, deployment and live financial actions require separate explicit release authorization.
