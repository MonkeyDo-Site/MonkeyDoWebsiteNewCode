# MonkeyDo waiver source and status

## Tenth document — presentation follow-up

Post-signing coverage lists Yes before No. Booking completion reminds the customer to send the shared link without the previous Waiver pending introduction. Places remain held and outstanding coverage remains recorded. Every new waiver still requires minor names; legal text and historical signature evidence are unchanged.

## Ninth review — required named minors and staff attestation

The owner explicitly reconfirmed that every new waiver needs minors listed. Electronic signing and named paper entry require Parent/Legal guardian and minor names, retaining the first-name versus full-name distinction. This supersedes previous blank-name exceptions, including adult-only visits. Historical signed evidence is preserved; no names are invented for earlier records.

At arrival, staff Yes confirms actual coverage. If current connected waiver names are fewer than attending children/babies, require a separate explicit acknowledgment of the stated count discrepancy and retain actor/time/counts in audit/checkout facts. Shared-parent link requests are visible to staff. Protected staff signing returns to the private arrival draft; public parent links do not expose it. See [ninth review](../NINTH_BATCH_REVIEW.md).


## Eighth public-waiver presentation

Hide the internal waiver version label on customer signing pages, retaining version metadata, source documents and original evidence in staff/storage records. A visible disabled state accompanies Continue to payment when signing additional minors is selected. Required server errors scroll into view and receive keyboard focus. No waiver release, coverage rule, saved signature or source PDF is rewritten.


## Seventh review: named paper forms and arrival summaries

PR #33 records a real paper signature per adult: signing date, legal name, relationship and named minors. Parent first-name and guardian full-name rules match electronic signing. An adult-only waiver uses the same form with no minors. No upload, electronic signature, fabricated electronic consent or source evidence is created by recording a paper form. The named record is immutable; original electronic evidence and prior unnamed paper marks remain intact.

Paper records are scoped to the same customer and checked at the visit date against one-year validity and accepted waiver versions. They can be reused in public booking and staff setup and appear in customer history, staff waiver search, booking details and active arrival waivers. Public summaries say Signed by … for … without distinguishing medium; backend records say Signed paper or Signed electronically. Appearance-only capitalization never rewrites stored signed names. The minor-entry instructions appear above the textarea. See [seventh review](../SEVENTH_BATCH_REVIEW.md).


## Current sixth-review update

PR #32 implements the approved conditional coverage screens, separate post-signing completion, same adult-only form, and removal of signer contact fields and Self choices. Approved follow-up: customer selection headings say “Sign Waiver”; summaries use “Signed by … for …”. Parent signers enter minors’ first names; legal guardians enter first and last names, with relationship-specific instructions and server validation. Existing signed names are preserved. No active email/verification flow used the shared parent's contact; the completion notice goes to the booking customer. The legal release and source PDF remain unchanged. MD-WAIVER-2026-02 records the shorter age acknowledgment for new signatures; unexpired MD-WAIVER-2026-01 coverage remains usable. Existing evidence is unchanged. New/all-expired customers must sign now and may also request the shared link. See [accepted scope](../SIXTH_BATCH_REVIEW.md) and [testing guide](../SIXTH_BATCH_TEST_GUIDE.md). Historical planning/prototype notes below describe earlier checkpoints.


## Preserved source

- File: `source/MD Waiver (1).pdf`
- SHA-256: `f159515b1c1c531bc57fce6a8813aa63f38f25da014459807759495f028ccdb6`
- Accessible transcription/prototype: [`../../waiver.html`](../../waiver.html)
- HTML added by `a5b5f5e`, merged through PR #3; both PDF and HTML already exist in the verified baseline.

## Current approval versus implementation

During the history/reconstruction the owner approved the current wording and electronic-signature interaction, reported insurance-broker approval, and explicitly removed counsel review as an owner-required gate. Do not mislabel this as counsel review or keep asking for approval already supplied.

The existing HTML still carries historical **draft** labels and deliberately reports that it did not save a signature. This documentation-only PR leaves its code, legal transcription, labels and the source PDF unchanged. Wording approval is not proof of a functioning booking/signature system or production readiness. A separately approved implementation must faithfully use the owner-approved source, version it, persist signatures/coverage and validate full workflow before launch.

Preserve the source PDF unchanged. Later source versions must be separate versioned documents, not overwritten originals. Never commit signed customer waivers.

Current rules: one-year validity; new version signed at next booking; approved example label MD-WAIVER-2026-01; signed files private R2 only; two-year file deletion from signing, minimal historical metadata retained; accessible shared-parent and arrival workflows. Full requirements: [MONKEYDO_REQUIREMENTS.md](../MONKEYDO_REQUIREMENTS.md). Exact email/link content: [EMAIL_TEMPLATES.md](../EMAIL_TEMPLATES.md).


## Next booking stage and shared experience

Saved electronic waivers are part of the next ordinary/supervised booking stage,
not a later integration after memberships/programs. Reuse the deployed compact
tables/filters, linked customer records, responsive cards/forms, navigation and
readable histories from [shared standards](../SHARED_WORKFLOW_STANDARDS.md).
Review waiver-specific signing/expiry/coverage/version filters; booking date
ranges must not hide an earlier valid signature. Different parents/minors can
have multiple current coverage records. A signed document is immutable evidence,
not an editable membership draft; a new signing/version preserves the old record.

The owner approved wording remains unchanged. Private R2 evidence, full coverage
and shared-link privacy/retention, signing/arrival gates, jobs and recoverable
backups must be implemented and actually verified before claiming the flow works.
Use new test reservations; earlier test records remain visibly distinguishable
internally and receive no fabricated signature. Customer-email uniqueness does
not impose a unique email constraint across separate waiver signers. The
[remaining plan](../NEXT_PHASE_REVIEW.md) records this sequence; no waiver code or
signed file is created by the planning update.


## Authorized booking-stage implementation update

Draft PR #30 now implements separate Django signing, metadata/history, private R2
evidence, shared-parent pages and retention workflows locally. The original static
source prototype is preserved. Local tests/browser evidence and the outstanding
approved online-group pending/held-place exception are recorded in [implementation status](../BOOKING_COMPLETION_DEVELOPMENT.md).
No actual configured R2 upload, hosted waiver completion or production acceptance
is claimed by that local implementation.


## Approved online group exception

On final booking save, customers bringing other parents' minors may reserve
places and request the shared parent-waiver link and unsigned PDF by email.
The booking is visible as Waiver pending, with its capacity retained. Staff verify
actual coverage before play; incomplete waivers do not automatically release places.
Individual signing does not disclose other parents' contacts, signatures or payment
information, and does not itself attest that everyone in the group is covered.
