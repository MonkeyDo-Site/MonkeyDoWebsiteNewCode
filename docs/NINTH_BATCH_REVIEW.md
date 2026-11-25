# Ninth batch: arrival, card replacement and payment review

The owner authorized development and a concurrent draft PR after review of all 18 comments and 20 screenshots in Ninth Batch of Comments.docx. The screenshots predate PR #34 deployment. Build on merged PR #34, retain its corrections, and provide a numbered GitHub desktop/phone gallery. Update this PR during review; merge and prepare the pinned ZIP/single deployment block only after the owner approves.

## Accepted scope

- Fix arrival error handling and live price updates before waiver confirmation; use a specific waiver-required error, a rose final button and prominent selected-card information.
- Preserve unsaved arrival counts, tender choices and other entered fields through card replacement, signing and return navigation. A preserved draft is not attendance, a receipt or a charge.
- Replace staff card retention with required separate Yes/No choices for a new card. Combine booking-card saving/replacement into Save and use this card, remove the redundant confirmation checkbox, and return to the originating arrival or booking. Keep existing card responsibilities and no-repeat setup safeguards.
- Shorten staff card wording, tighten provider-field spacing and show applicable admission prices consistently. Fix displayed percentage precision/error focus. New prices apply to current public pricing/new bookings; accepted historical booking prices and evidence remain immutable.
- Every new waiver must identify the minors it covers. The owner explicitly reconfirmed that every waiver needs minors listed, superseding every blank-name exception, including adult-only visits and the booking adult requesting other parents’ signatures. Electronic and named paper entries require a Parent/Legal guardian and minor names. Do not rewrite existing signed evidence.
- Staff Yes is the coverage attestation. When attendee minor counts exceed distinct names in current connected waivers, show: There are more children in the visit than the children listed in the signed waivers connected to this booking. Do you want to go ahead? Require an explicit answer before final confirmation and record the staff attestation and any acknowledged discrepancy. Show when a shared waiver link was requested.
- Final arrival shows processing dots and the true payment outcome (approved, declined/action required or still pending) without another card request. Attendance and accounting/payment history remain truthful.
- Compact booking-detail cards: remove the floating saved-card sentence; Payment under Visit details, Waivers under Payment, Messages under the price estimate.
- Split payment uses compact method/amount rows with Add payment method and Use remaining balance. Multiple non-card methods can cover the visit; only the remaining card-funded amount has processing fees. Only final confirmation records money/requests a charge. Excess allocations remain rejected clearly; cash-change functionality is deferred. Changing the overall payment choice clears unsaved split inputs, not recorded receipts.
- Compact customer Dashboard notices into a table with expandable details and Mark reviewed beside each row.
- Add staff-visible searchable booking comments with author/date/time and edit history, following existing shared comment requirements.

## Review and boundaries

Use fictional local fixtures and synthetic provider/storage/email adapters for the gallery. Keep real Banquest field validation, consent and raw-card isolation. Preserve historical signed records, charges, receipts, frozen emails and the single reusable-card rule. No production/backup activation, credentials, automatic payment retries or active membership work. Future deployment preparation must account for any additive schema/runtime grants needed by booking comments; no hosted changes occur during screenshot review.

## Implemented review and verification

Draft PR #35 contains the accepted changes. The [numbered screenshot gallery](design-review/ninth-review/README.md) has 21 desktop/phone pairs, including a real focused pricing-error response. The original source screenshots predate PR #34; this branch retains the eighth batch. Invalid card input continues to be handled by Banquest's hosted fields; no verification hold or issuer approval is added.

Arrival preview and final validation now use distinct form modes consistently, including reconstructed forms. An invalid initial preview uses a bound error form, preventing an unbound-form exception from turning a capacity rejection into HTTP 500. The precise original hosted traceback was not available. Live pricing proceeds before waiver/tender verification while final confirmation still enforces those decisions.

Arrival drafts are private to the actor/session/booking/version, use unguessable tokens and expire after two hours. Requests are serialized before departure to avoid an older preview overwriting newer session data. Signing uses a protected staff return route; public parent links retain their limited public completion page. Card replacement retains the existing explicit booking binding but orchestrates it through one button; uncertain nonce exchanges are never replayed.

Staff Yes plus an explicit discrepancy acknowledgment is authoritative coverage confirmation. The recorded attendee/name counts, acknowledgment, actor and time are retained in checkout facts/audit. Every new electronic/paper waiver requires named minors and Parent/Legal guardian; this deliberately supersedes the previous blank-name exception, including adult-only visits. Existing signatures and their original evidence remain intact.

Payment results poll an authenticated read-only endpoint. Only final confirmation records attendance/received funds or queues a card operation. Pending/unknown/declined outcomes are not reported as received money, and status checks never dispatch/retry. Cash change remains deferred. Multiple non-card rows may cover the visit; only a real card remainder incurs the fee.

New policy presentation uses MD-PAYMENT-2026-05. Admission display prices follow the relevant quote's immutable pricing policy; a consent audit captures the exact displayed cancellation/retention wording, including a durable pre-exchange snapshot. New global prices update public pages/new quotes; historical booking prices, consents, messages and signed evidence are not rewritten.

Migration 0052 adds a nullable booking reference to CustomerComment, preserving all existing general customer comments. Booking comments use staff comment permissions plus booking/customer access, optimistic revisions and append-only audit. Searches include authorized booking comments; general customer comment editing and hidden booking histories do not leak their contents. The reviewed schema/checksum allowlist includes only this additive extension; deployment remains gated on final owner approval.

Validation: all 678 PostgreSQL tests pass, including new draft privacy, waiver attestation, no-write previews, full/partial split allocation, truthful status checks, retention choice, signing/card return, immutable pricing and comment permission/history cases. Ruff/formatting, Django checks and JS syntax pass. The complete gallery browser run has no page overflow or JavaScript errors at 1440/390px. All fixtures and outcomes are synthetic; no external provider operation or hosted deployment was performed.
