# Seventh batch: arrival, receipts and waiver records

The owner authorized implementation and a PR on November 22, 2026 after reviewing all 19 document comments and 22 screenshots. Keep the same PR updated during screenshot review. Show the arrival, booking-detail and edit-booking pages. Deliver browser ZIP plus one PowerShell command after review and final validation; do not merge or deploy automatically.

## Agreed decisions

- One arrival page with four attendee/sock fields in a row, active customer waivers and adjacent Sign waiver now, live cream price breakdown and balance. Explicit final confirmation only; changing inputs never charges or records money.
- Cash/check receipt dates are automatic at arrival. Only Zelle exposes its actual bank receipt date. Before arrival use Record Zelle received; suppress empty generic money-received totals.
- Record actual verified Zelle amount before arrival without changing attendance. Apply it once to the final price; collect only remaining money, or calculate a manual Zelle refund. Cancellation/no-show retain only the selected applicable fee and return excess. Refund due stays on the owner Dashboard until actual completion is recorded within the booking.
- Owner-only booking-specific supervised exception may override Open-Play-only mode, absent supervised allocation and the supervised cutoff until session end. General child/total capacity still applies unless separately overridden. Public session configuration is unchanged.
- Paper waivers record one signing adult, actual date, relationship and named minors, valid one year and reusable within the same customer's future bookings. Follow parent/guardian name rules. Public summaries do not distinguish medium; staff records do. Preserve earlier electronic evidence and unnamed historical paper marks; never invent names or signatures.
- Cancellation/no-show asks Send customer email? Yes/No, neither preselected. No automatic customer email without that explicit choice. Current documentation and original supplied history did not contain an ordinary-booking Yes/No rule; the earlier explicit rule was for complimentary memberships. This direct decision governs this batch.
- All document wording/layout changes, descriptive capacity feedback on estimate and Continue, five steps on session selection, conditional Zelle sender, visible card errors, hosted-field spacing and provider-supported month advancement.
- Booking details show truthful accepted price breakdown after arrival, amounts aligned right, payment/waiver cards side by side and no $0 unpaid balance. Price history remains unchanged.

## Boundaries

No homepage redesign, active memberships, production activation, credential changes or backup activation. New source records must retain accounting dates and must not double-count prepayment applications as new receipts. Pending/uncertain card operations cannot be retried automatically. A calculated Zelle refund is not a transfer; completion requires an owner to confirm it was returned.
