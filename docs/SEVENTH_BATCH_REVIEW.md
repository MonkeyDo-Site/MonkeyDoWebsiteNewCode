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

## Provider-field question pending

The owner clarified that after entering the second month digit, focus should move directly to the year without a click or Tab. The public Banquest v0.3 API reference documents styles, inline errors and input/change/ready events, but does not document an auto-tab/focus option. This does not prove Banquest cannot enable the behavior. The owner will ask Banquest; implementation of that specific behavior remains pending their answer. Continue all other work. Hosted fields remain provider-controlled. Card spacing and visible inline/site errors use documented styling options.

## First-round implementation and validation

- 625 PostgreSQL tests pass. Coverage includes partial prepayments, stale review proofs, owner-only supervised exceptions, public paper reuse, optional closure email, runtime-role receipt/application/refund writes and automatic cash dates. Existing deployment/schema and payment/waiver tests remain in the suite.
- Ruff, Django checks, migration drift and pinned migration checksums pass. Additive migrations are 0048–0051; use the reviewed booking upgrade for the eventual approved deployment. No schema has been applied to the hosted site by the agent.
- Twelve full-page Chromium screenshots cover six arrival/booking/edit states at 1440px and 390px, with no document overflow or JavaScript errors. The separate interaction check preserves changed counts while recording $10 Zelle in-page, collects only $32.30 cash on a $42.30 revised invoice, and resolves a manual refund's Dashboard notice only after actual completion is recorded.
- [First-round screenshots](design-review/seventh-review/README.md). PR #33 stays draft while the owner reviews images; update this PR for subsequent comments. Deployment ZIP and single PowerShell command follow review. Month-to-year focus remains pending Banquest confirmation.

## Arrival paper-entry follow-up

The owner noted paper entry was missing from arrival. The arrival waiver card now includes a visible Paper waivers signed checkbox that expands the named paper record fields. Saving records the signature in place and refreshes current coverage; it never submits attendance or payment, and preserves unsaved counts/tender choices. Controls belong to a separate paper-record form, preventing receipt/arrival validation from interfering. Unsaved paper details disable final arrival until saved or unchecked. Booking-detail paper entry remains available.

Validation: 33 focused arrival/waiver tests pass, including prefixed paper entry, replay protection, guardian-name validation and no attendance/payment effects. Desktop/phone Chromium checks verify form ownership, expansion, preserved counts/payment selection, active-list refresh, confirmation gating, no horizontal overflow and no JavaScript errors. New full-page v5 arrival images are linked in the screenshot gallery. No schema changes in this follow-up.

## Cumulative price-adjustment summary

The owner approved a compact Price adjustment section at the bottom of Visit payment details, ahead of payments received and remaining/refund amounts. Apply the same read-only comparison to arrival, the pre-arrival edit preview and saved booking details. Original booking total always means the first immutable saved quote, not the latest intermediate revision. Show combined additions and removals separately, existing cancellation fees, tax and processing-fee changes, explicit owner-price adjustments, then one Adjusted total. Replace the previous total row when this summary appears. Unchanged prices do not gain extra sections; historical quote snapshots remain unchanged.

The supplied example reconciles $55.29 − $15.00 admission + $3.00 fee − $0.99 tax = $42.30; an existing $55.29 Zelle receipt leaves the independently calculated $12.99 refund due. Count changes and play-price changes are distinguished, including mixed additions/removals that offset to zero. The presentation neither creates a cancellation fee nor collects/refunds money. New comparisons are not written into financial snapshots or review proofs.

Focused validation: 34 pricing/arrival/owner-price tests pass, including eight new arithmetic and workflow tests. Six Chromium desktop/phone checks verify the exact comparison in arrival, live edit preview and accepted booking details, one adjusted-total row, responsive layout and no JavaScript errors. Inputs revert to the standard display when the change is undone. [Updated summary screenshots](design-review/seventh-review/README.md).

## Completed-arrival received total

The completed booking’s Payment card shows Total received above the existing tender/operation breakdown instead of the standalone Zelle-received headline. The example is $42.30 total: $32.30 cash plus $10.00 applied advance Zelle. This read-only total includes successful net invoice receipts plus unused advance Zelle; applying a receipt does not count it twice. Pending/declined card requests are excluded. Unreturned excess remains received until an actual manual refund is recorded; the display then says “after refunds.” Upcoming bookings retain their advance Zelle receipt details.

Validation: 28 focused booking/arrival tests pass, including mixed cash/Zelle totals, pending-card exclusion and actual refund completion. Desktop/phone Chromium checks confirm the exact example, no overflow and no JavaScript errors. No schema or financial-write behavior changed. Updated v9 screenshots are in the review gallery.

## Backend capacity reminder wording

Staff booking capacity failures now use a concise capacity/booked-count reminder. Owners see “Check the owner override checkbox to proceed.” Non-owner staff see “Ask the owner to approve a capacity override to proceed.” Child, combined and supervised limits use their respective actual counts, excluding the booking currently being edited. Public customer guidance is unchanged. Edit-form errors span the full grid width. No capacity or permission rules changed.

Validation: 57 staff/public/seventh booking tests pass. Desktop/phone checks verify the exact 35/30 owner reminder, no horizontal overflow or JavaScript errors, and rejected edits create no saved booking/arrival/payment. Updated v11 images replace the earlier edit-capacity examples. The unrelated special-price notice now also requires an existing pricing-state record, preventing a blank amount notice on an ordinary booking. Three additional owner-pricing tests pass.

## Conditional supervised-exception control

The second Supervised Play checkbox is omitted from regular booking edits. Owner-only rendering is enabled only by a structured server warning for the supervised exception (Open-only session, zero supervised allocation or supervised cutoff before the session ends). The existing booking-scoped approval and other capacity/permission gates are unchanged. Already-approved exceptions remain saved on the booking.

Validation: 58 focused staff/public/seventh tests pass, including a new complete regular edit → warning → explicit owner approval → normal edit test. Six desktop/phone captures verify checkbox absence before warning, unchecked availability after warning, no overflow and no JavaScript errors. The requested public Continue capture shows existing behavior: a separate capacity-error screen with Choose a session, rather than an inline attendee-form error. No public-flow code changed. No successful edit, exception, arrival, payment or email was submitted by the browser capture.

## Public capacity-error recovery buttons

The owner requested two explicit actions on the post-Continue capacity-error screen: Adjust the amounts in my booking, and Choose another session. Capacity failures retain the current flow/session and latest validated attendee/play/sock/payment inputs, discard the rejected quote and remain at Session Details. Adjust returns to those inputs, including after editing previously accepted details; continuing still performs fresh capacity and pricing validation. Choose another session links to the schedule. Other error/restart routes retain their existing behavior. No booking, hold, signature, charge or email is created by these actions.

Validation: 46 focused public/completed/seventh tests pass, including child, combined-attendee and supervised capacity recovery and replacing earlier saved counts with the rejected attempt. Desktop/phone Chromium checks exercise both buttons, exact retained values, repeated capacity enforcement and session selection; no overflow or JavaScript errors. Updated v13 screenshots supersede the v12 public error capture.

## Public session date position

Moved the shared public booking page’s session date/time directly below Your play session, before the staging notice and error warning. The two capacity-recovery buttons remain below the warning. Desktop/phone Chromium checks verify the heading/date/warning order, responsive layout, retained amounts and both recovery actions, with no JavaScript errors. No application behavior or schema changed. Updated v14 screenshots supersede v13.
