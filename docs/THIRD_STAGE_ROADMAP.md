# Third stage: active memberships — saved development roadmap

## Current authorization — November 26, 2026

The owner explicitly authorized building the entire mapped third stage while reviewing the latest booking deployment. Work should continue under one ongoing goal without repeated go-ahead requests; present the first representative functional samples early and update the same implementation PR during review. The earlier review hold below is superseded by this authorization. The owner confirmed the accidentally pasted email address and time are not project instructions or contact changes.

No new business-rule blocker was identified in the initial reconciliation. Production tax/live-account configuration remain launch inputs, not obstacles to local/sandbox development. Browser ZIP and single-command staging deployment follow explicit release approval. Existing test membership drafts remain plans until an explicit purchase; do not activate them automatically.

## Current implementation and review

Continue on draft [PR #37](https://github.com/MonkeyDo-Site/MonkeyDoWebsiteNewCode/pull/37), with the [functional desktop/phone gallery](reviews/active-memberships/README.md) and [owner testing guide](ACTIVE_MEMBERSHIP_OWNER_TESTING.md). Representative purchase, active membership, booking, arrival, renewal and addition pages are available now; later samples cover payment failures, source funds and refunds. Samples 129–132 add cancellation-linked release of unapplied paid-visit funds while retaining the booking and actual membership refunds. Samples 133–135 add explicit new-card storage and request for a known failed remainder, with future installments preserved. Samples 136–138 add verified cash/check/Zelle/physical-gift replacement of a known failed remainder, removal of only its unused card fee, and recovery of a known receipt without duplicate collection. Samples 139–140 add recorded bank evidence on existing payment pages and a filtered paid-visit history download that separates original funds, new receipts and converted credit. Samples 141–142 show the paid early-renewal review safeguard and owner reminder when earlier required payments become unresolved, without deciding the pending debt policy. Samples 143–145 add one-page combined cash/check renewals, separate saved allocations and same-source type/term splits. Sample 146 adds search/browsing with preserved selections; samples 147–149 add one verified shared Zelle source, separate allocations and original receipt evidence.

Development remains active. Mixed manual/card remainder, general payment date/source exceptions, remaining combined renewal funding methods, remaining owner corrections/consolidation/grants and broader credit/reporting work are still in progress. Three previously identified business policies remain guarded pending answers; do not infer defaults or repeat the questions. Provider verification and an explicit release decision remain separate from local developer checks. Features and scheduled collection stay off by default.

## Latest increment — preserve selections while finding renewals

The combined renewal page now searches membership number/type and loads further available records on the same screen. Selected type/count/term, future card, payment method and request identity survive browsing; current review resets acceptance and actual-receipt confirmation. Fully renewed records are filtered before the page limit. Sample 146 joins the refreshed 143–145 in the 146-pair gallery. The final expanded 109 checks and two actual browser scenarios pass; no schema or financial authority changed, and all 65 published migrations remain frozen. Broader group funding, owner corrections/cohort work, credit returns/redemption and final provider/operational validation remain active under the existing authorization.

## Latest payment increment — one Zelle source for combined renewals

The same combined page now records a manually verified Zelle transfer with its actual date/sender, allocates the exact amount to separate renewal histories and prepares one confirmation. Browsing preserves bank/renewal entries. Source-linked payment detail and CSVs identify allocations without duplicate gross receipt totals. Additive 0092 preserves all 65 earlier migration files and requires compatible code for used source history. The gallery now has 149 desktop/phone pairs. Group card/gift/credit/split and no-payment funding, remaining owner/cohort corrections, credit work and final operational/provider checks remain active.

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
