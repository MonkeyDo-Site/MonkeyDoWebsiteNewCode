# Ninth batch: arrival, card replacement and payment review

The owner authorized development and a concurrent draft PR after review of all 18 comments and 20 screenshots in Ninth Batch of Comments.docx. The screenshots predate PR #34 deployment. Build on merged PR #34, retain its corrections, and provide a numbered GitHub desktop/phone gallery. Update this PR during review; merge and prepare the pinned ZIP/single deployment block only after the owner approves.

## Accepted scope

- Fix arrival error handling and live price updates before waiver confirmation; use a specific waiver-required error, a rose final button and prominent selected-card information.
- Preserve unsaved arrival counts, tender choices and other entered fields through card replacement, signing and return navigation. A preserved draft is not attendance, a receipt or a charge.
- Replace staff card retention with required separate Yes/No choices for a new card. Combine booking-card saving/replacement into Save and use this card, remove the redundant confirmation checkbox, and return to the originating arrival or booking. Keep existing card responsibilities and no-repeat setup safeguards.
- Shorten staff card wording, tighten provider-field spacing and show applicable admission prices consistently. Fix displayed percentage precision/error focus. New prices apply to current public pricing/new bookings; accepted historical booking prices and evidence remain immutable.
- Every new waiver must identify the minors it covers. The previous blank-name adult-signature exception is superseded; adult-only visit behavior is awaiting a specific clarification. Do not rewrite existing signed evidence.
- Staff Yes is the coverage attestation. When attendee minor counts exceed distinct names in current connected waivers, show: There are more children in the visit than the children listed in the signed waivers connected to this booking. Do you want to go ahead? Require an explicit answer before final confirmation and record the staff attestation and any acknowledged discrepancy. Show when a shared waiver link was requested.
- Final arrival shows processing dots and the true payment outcome (approved, declined/action required or still pending) without another card request. Attendance and accounting/payment history remain truthful.
- Compact booking-detail cards: remove the floating saved-card sentence; Payment under Visit details, Waivers under Payment, Messages under the price estimate.
- Split payment uses compact method/amount rows with Add payment method and Use remaining balance. Multiple non-card methods can cover the visit; only the remaining card-funded amount has processing fees. Only final confirmation records money/requests a charge. Excess allocations remain rejected clearly; cash-change functionality is deferred. Changing the overall payment choice clears unsaved split inputs, not recorded receipts.
- Compact customer Dashboard notices into a table with expandable details and Mark reviewed beside each row.
- Add staff-visible searchable booking comments with author/date/time and edit history, following existing shared comment requirements.

## Review and boundaries

Use fictional local fixtures and synthetic provider/storage/email adapters for the gallery. Keep real Banquest field validation, consent and raw-card isolation. Preserve historical signed records, charges, receipts, frozen emails and the single reusable-card rule. No production/backup activation, credentials, automatic payment retries or active membership work. Future deployment preparation must account for any additive schema/runtime grants needed by booking comments; no hosted changes occur during screenshot review.
