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
