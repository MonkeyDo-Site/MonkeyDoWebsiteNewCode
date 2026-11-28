# Third stage: active memberships — saved development roadmap

## Current authorization — November 26, 2026

The owner explicitly authorized building the entire mapped third stage while reviewing the latest booking deployment. Work should continue under one ongoing goal without repeated go-ahead requests; present the first representative functional samples early and update the same implementation PR during review. The earlier review hold below is superseded by this authorization. The owner confirmed the accidentally pasted email address and time are not project instructions or contact changes.

No new business-rule blocker was identified in the initial reconciliation. Production tax/live-account configuration remain launch inputs, not obstacles to local/sandbox development. Browser ZIP and single-command staging deployment follow explicit release approval. Existing test membership drafts remain plans until an explicit purchase; do not activate them automatically.

## Current implementation and review

Continue on draft [PR #37](https://github.com/MonkeyDo-Site/MonkeyDoWebsiteNewCode/pull/37), with the [functional desktop/phone gallery](reviews/active-memberships/README.md) and [owner testing guide](ACTIVE_MEMBERSHIP_OWNER_TESTING.md). Representative purchase, active membership, booking, arrival, renewal and addition pages are available now; later samples cover payment failures, source funds and refunds. Samples 129–132 add cancellation-linked release of unapplied paid-visit funds while retaining the booking and actual membership refunds. Samples 133–135 add explicit new-card storage and request for a known failed remainder, with future installments preserved. Samples 136–138 add verified cash/check/Zelle/physical-gift replacement of a known failed remainder, removal of only its unused card fee, and recovery of a known receipt without duplicate collection. Samples 139–140 add recorded bank evidence on existing payment pages and a filtered paid-visit history download that separates original funds, new receipts and converted credit. Samples 141–142 show the paid early-renewal review safeguard and owner reminder when earlier required payments become unresolved, without deciding the pending debt policy. Samples 143–145 add one-page combined cash/check renewals, separate saved allocations and same-source type/term splits. Sample 146 adds search/browsing with preserved selections; samples 147–149 add one verified shared Zelle source, separate allocations and original receipt evidence. Samples 150–152 add same-page correction of an unused prepaid/complimentary term, retained original date history and readable saved history while sales are paused.

Development remains active. General payment date/source exceptions, remaining combined renewal funding methods, remaining owner corrections/consolidation/grants and broader credit/reporting work are still in progress. Three previously identified business policies remain guarded pending answers; do not infer defaults or repeat the questions. Provider verification and an explicit release decision remain separate from local developer checks. Features and scheduled collection stay off by default.

## Latest increment — preserve selections while finding renewals

The combined renewal page now searches membership number/type and loads further available records on the same screen. Selected type/count/term, future card, payment method and request identity survive browsing; current review resets acceptance and actual-receipt confirmation. Fully renewed records are filtered before the page limit. Sample 146 joins the refreshed 143–145 in the 146-pair gallery. The final expanded 109 checks and two actual browser scenarios pass; no schema or financial authority changed, and all 65 published migrations remain frozen. Broader group funding, owner corrections/cohort work, credit returns/redemption and final provider/operational validation remain active under the existing authorization.

## Latest payment increment — one Zelle source for combined renewals

The same combined page now records a manually verified Zelle transfer with its actual date/sender, allocates the exact amount to separate renewal histories and prepares one confirmation. Browsing preserves bank/renewal entries. Source-linked payment detail and CSVs identify allocations without duplicate gross receipt totals. Additive 0092 preserves all 65 earlier migration files and requires compatible code for used source history. The gallery now has 149 desktop/phone pairs. Group card/gift/credit/split and no-payment funding, remaining owner/cohort corrections, credit work and final operational/provider checks remain active.

## Latest correction increment — same membership, revised benefit calendar

An unused standalone prepaid or complimentary term can be corrected on its existing overview after recording the customer’s agreement and a reason. Current dates flow through booking benefits, customer summaries, renewals/notices, refund suggestions and remaining-credit alerts. Original accepted dates, cycle IDs, prices and receipts remain evidence under the same M number. Update email is an explicit Yes/No choice with scoped contact/outcome handling. Additive 0093 supplies immutable calendar facts and a guarded current projection; all 66 prior published migrations remain unchanged. The gallery has 152 desktop/phone pairs. Monthly/used/started/expired corrections, owner consolidation and nonpurchase grants remain unfinished, alongside the other active work above.

## Latest recovery increment — keep received money while requesting a card remainder

Samples 153–156 add same-page review of one verified received portion plus a smaller exact card request after a known failed paid-visit remainder. The receipt commits before separate card preparation, survives interruption and cannot be duplicated by retry. Unknown card outcomes require reconciliation. Exact known funding applies original funds once; cancellation preserves actual received/refunded amounts and removes never-collected principal/unused fees. Additive 0094 leaves all 67 earlier migration files and pins untouched. New-card entry within a saved split and general later-day/source exceptions remain unfinished. The gallery now has 156 desktop/phone pairs. Broader Stage3 work continues.

## Earlier owner's review gate — historical

The owner reports the seventh booking batch deployed and is reviewing it. Wait for explicit go-ahead before starting membership requirements reconciliation, representative screen design or implementation. Recording this roadmap does not start those activities. The owner will say when the review is complete.

“Third stage” here means active memberships, following the initial foundation and completed ordinary/supervised booking work. The numbered increments in NEXT_PHASE_REVIEW.md use a different breakdown; the agreed feature order remains unchanged.

## Owner's experience principles

Carry forward what was learned in the first two stages:

- **At a glance:** make the current state, relevant totals and next action immediately understandable.
- **Compact:** use the established concise forms, filters, tables, cards and aligned amounts. Keep wording short and avoid redundant information.
- **Avoid multiple screens:** combine related inputs, live calculations and review information on one page where practical, as with arrival. Keep explicit confirmations for signing, charging and other consequential actions.
- **Clear navigation:** make it clear where each action leads, preserve entered information when returning, and distinguish leaving an editor from cancelling the underlying booking or membership.
- **Few clicks:** reuse known customer details, cards and valid waiver evidence where permitted; avoid asking for the same information again. Show rare exception controls only when relevant.

Apply these principles to staff and public membership workflows, desktop and phone. Inherit the already approved customer matching, permissions, filters, pagination, history and financial presentation conventions. Page consolidation must preserve clear amounts and explicit financial actions.

## Saved intended scope

Active membership purchases and accepted terms; monthly/prepaid payments and installments; membership recognition and information in booking; benefit reservation/usage and adjusted pricing; additional places and renewals; approved owner exceptions; visit-to-membership conversions, customer credit and the agreed tax/processing-fee/refund treatment. Detailed business rules remain in the existing membership/payment requirements; this note adds no new rules.

Reuse the payment, card, customer, waiver, email, background-job and deployment foundation. Expect less setup and fewer repeated layout decisions. Membership term dates, benefit limits, installment outcomes and conversions still need careful scenario testing; no guarantee of shorter total development time or a fixed delivery date has been made.

## Authorized work sequence

1. Reconcile membership requirements with all accepted decisions and improvements from the first two stages; identify overlap and unresolved questions before building.
2. Review a small set of representative membership screens early, then reuse the approved layouts consistently.
3. Build and developer-test complete scenarios from purchase through booking, benefit usage and payment, including failures and adjustments.
4. Keep the implementation PR updated during review; prepare the final post-deployment testing guide and the familiar browser ZIP plus single PowerShell command.

The owner can continue testing the deployed booking changes. Address findings affecting shared customer, payment or waiver behavior before dependent membership work relies on them. Homepage redesign remains deferred; the later party/gift-card/standalone-socks/club workflows follow memberships under the existing roadmap.

## Related specifications

- [Remaining stages and accepted feature order](NEXT_PHASE_REVIEW.md)
- [Shared workflow and screen standards](SHARED_WORKFLOW_STANDARDS.md)
- [Membership requirements](MEMBERSHIPS.md)
- [Payment requirements](PAYMENTS.md)
- [Deployed seventh-batch review](SEVENTH_BATCH_REVIEW.md)


Developer verification: the complete PostgreSQL suite passed **1,858 tests in 1,106.692 seconds** with the final application code. The related screen/accounting run passed **119 checks in 46.681 seconds**; the final boundary/browser run passed **36 checks in 15.891 seconds**, including actual desktop/phone review, save, reload, safe non-JSON failure/recovery and paused-history navigation; committed correction/reservation races; runtime grants; and used/unused reversal and release compatibility. Tests cover a booking after the original expiry but inside the corrected term, the current customer summary, unchanged original cycle IDs/receipts and credit alerts at corrected expiry without expiring the credit. All six new 1440px/390px images were visually inspected with no overflow, JavaScript errors, duplicate IDs or nested forms. All 602 Python files pass lint/format checks; system checks, model drift, JavaScript syntax, whitespace, all 304 PNGs/gallery links and all 67 migration pins pass. All 66 previously published migration files/hashes and the earlier actual-download CSV remain unchanged. All four GitHub checks passed for the preceding published commit; this update starts its own checks after publication. Provider/storage requests were mocked or blocked and no customer email was delivered. Actual Banquest behavior remains unverified. Features and collection stay off by default, PR37 stays draft and broader stage work continues. No merge, deployment or live financial action occurred.


Developer verification: the complete PostgreSQL suite passed **1,887 tests in 1190.246 seconds** with the final application code. The related cancellation/recovery/deployment run passed **98 checks in 66.442 seconds**; six actual-commit concurrency/reversal cases passed in **11.097 seconds**. The final **18-check run in 36.627 seconds** includes the 16 split service cases and two actual Chromium desktop/phone scenarios. It verifies read-only preview, changed-consent reset, non-JSON failure/recovery, exact separate receipts, original funds/benefits untouched before full funding, preserved known receipts after interrupted card preparation, explicit remainder-only retries and unknown-outcome blocking. Cancellation tests cover partial/full funding, actual partial refunds and exact unused-fee removal. Raw SQL rejects forged amounts, fee reductions and rewritten evidence. Used schema reversal is refused; unused reversal restores all six prior function definitions and reapplies.

All eight new 1440px/390px images were visually inspected with no overflow, JavaScript errors, duplicate IDs or nested forms. All **609 Python files** pass lint/format checks; system checks, model drift, JavaScript syntax, whitespace, all **312 PNGs/gallery links** and **68 migration pins** pass. All **67 previously published migration files/hashes** and the earlier actual-download CSV remain unchanged. All four GitHub checks passed for the preceding published commit; this update starts new checks after publication. Provider/storage requests were mocked or blocked, no bank or gift-provider API was called and no customer email was delivered. Actual Banquest behavior remains unverified: a fresh public hosted-field SDK GET returned a workspace-proxy 403; its tokenization host is absent from the current allowed-host list. No network settings were changed. Features and scheduled collection remain off by default, PR37 stays draft and broader Stage3 work continues. No merge, deployment or live financial action occurred.
