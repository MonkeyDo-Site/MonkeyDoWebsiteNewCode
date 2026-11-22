# Sixth batch: booking, waivers and payment review

Authorized November 21, 2026 after review of all 19 comments and 20 screenshots.

## Accepted scope

- Five responsive booking progress steps; step 4 is Waiver Details.
- Coverage pages distinguish new, unexpired, expired and mixed waiver history. New customers and customers whose waivers have all expired must select option 1 (sign now), with the shared-parent link optional. A selected sign-now option must be completed before continuing. Adult-only visits use the same form and navigation.
- Remove signer email/phone inputs from both booking and shared-parent forms. Shared signing is linked by its private booking link, not signer contact. Keep existing evidence unchanged. Shorten the age acknowledgment and remove Self relationship choices and self-only help text; retain complete legal text and explicit signature consent.
- Separate post-signing coverage confirmation from the signing form. Shared-parent completion shows only thank-you and appointment information within the normal site shell.
- Payment-method-specific explanations and cancellation wording, compact cream itemized totals, direct payment-method switching that preserves signatures, useful safe card errors, shorter hosted-card spacing and adjacent Save card securely / Confirm booking buttons. Confirmation is disabled until card setup succeeds. Card saving is not an issuer approval, charge or verification hold.
- Keep the owner's supplied public cancellation wording ($3 per each $15 or $18 admission plus membership sentence); all existing fee calculations and exceptions remain unchanged.
- Update confirmation screen, email correction wording, conditional socks reminder and branded HTML confirmation emails, keeping a plain-text version and actual paid/unpaid facts on later resends.
- Owner-only explicit retry of a verified declined card payment: review unpaid amount/card, preserve history, prevent duplicate/uncertain attempts and never retry automatically.
- Review browser Back/Forward across booking. Preserve earlier inputs and valid signatures, revalidate changed details, prevent stale forms and duplicate saves/signatures/charges.

## Release and acceptance

Develop in a draft PR. Show owner only updated Payment Details screenshots (including alternate-payment wording); other pages will receive owner acceptance after staging deployment. Preserve the browser ZIP download plus one PowerShell command. Do not merge or deploy automatically. Homepage design, active memberships and live payment activation are outside this batch.

Implementation and validation results will be added before review.

## Implementation decisions

- PR #32 extends the existing remaining-balance service with an owner-only Retry card route on both booking and payment detail. It rechecks declined/pending/corrected state and current amount/card inside confirmation; no provider request occurs on opening or reviewing the page.
- Waiver acknowledgment revision MD-WAIVER-2026-02 uses the unchanged legal release. Both it and MD-WAIVER-2026-01 remain eligible for current participant/date coverage. Original evidence and acknowledgment text are never overwritten. New parent signatures store no signer email/phone; existing historical contacts remain under the existing retention policy.
- Adult-only visits use the same form. Relationship is required when minors are entered; an adult signing without minors can leave it blank. No Self option or special adult-only screen is introduced.
- Public payment policies use MD-PAYMENT-2026-02, retaining earlier versions. Primary-card payment acceptance is the explicit Save action beside the shown terms; backup methods retain their checkbox. The stored policy includes both displayed variants and acceptance records the intended method. No tax, price, cancellation calculation, surcharge or issuer-hold rule changes.
- New confirmation messages use MD-EMAIL-2026-02 with deterministic branded HTML from the frozen message text and a plain-text alternative. Existing frozen messages remain intact; paid/corrected resends retain actual received and remaining facts.
- Browser history uses browser-session-owned step checkpoints, server-side stale-flow/edited-answer checks, no-store headers and back/forward-cache revalidation. It creates no financial GET action. Completed flows resolve to the saved receipt.
- The original provider frame was surrounded by excess height. The public payment frame has compact responsive sizing; genuine provider iframe/card-brand acceptance remains part of hosted testing. Local browser captures simulate provider card entry and both external adapters; no external requests or actual charges are claimed by those checks.
- No schema changes are required. Use the normal Functional deployment; preserve existing sandbox flags, credentials and disabled backups.

The owner-facing [testing guide](SIXTH_BATCH_TEST_GUIDE.md) covers the full batch. Only Payment Details images are supplied for pre-deployment design review.

## Verification completed

- 606 PostgreSQL tests pass, including new owner-only retry/unknown-outcome checks, shared-parent completion privacy, adult-only signing, preserved original waiver coverage, method-switch consent, frozen/escaped HTML email, browser checkpoint behavior and restricted runtime-role insertion of the new policy versions.
- Ruff, Django checks and migration-drift checks pass; no schema migration is generated. Existing deploy-helper tests remain in the full suite.
- Chromium checks pass at 1440px and 390px for Credit card, Cash, Check and Zelle, with no horizontal page overflow or JavaScript errors. Card-save validation, confirmation gating and an end-to-end browser booking/navigation flow pass with synthetic adapters. [Full payment-page images](design-review/sixth-payment-review/README.md).
- [Post-deployment test guide](SIXTH_BATCH_TEST_GUIDE.md) and [Word copy](SIXTH_BATCH_TEST_GUIDE.docx) were prepared after implementation and reopened for verification.

Hosted acceptance and payment-page design approval remain the owner's review. This work has not been merged or deployed by the agent.
