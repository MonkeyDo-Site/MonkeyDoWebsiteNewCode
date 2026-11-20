# MonkeyDo waiver source and status

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
online-group timing question are recorded in [implementation status](../BOOKING_COMPLETION_DEVELOPMENT.md).
No actual configured R2 upload, hosted waiver completion or production acceptance
is claimed by that local implementation.
