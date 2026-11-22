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

Develop in a draft PR. Initial visual review covered Payment Details; the owner later requested waiver-page and sample-email previews and approved the collected changes. Remaining functional acceptance is after staging deployment. Preserve the browser ZIP download plus one PowerShell command. Do not merge or deploy automatically. Homepage design, active memberships and live payment activation are outside this batch.

Implementation and validation results will be added before review.

## Implementation decisions

- PR #32 extends the existing remaining-balance service with an owner-only Retry card route on both booking and payment detail. It rechecks declined/pending/corrected state and current amount/card inside confirmation; no provider request occurs on opening or reviewing the page.
- Waiver acknowledgment revision MD-WAIVER-2026-02 uses the unchanged legal release. Both it and MD-WAIVER-2026-01 remain eligible for current participant/date coverage. Original evidence and acknowledgment text are never overwritten. New parent signatures store no signer email/phone; existing historical contacts remain under the existing retention policy.
- Adult-only visits use the same form. Relationship is required when minors are entered; an adult signing without minors can leave it blank. No Self option or special adult-only screen is introduced.
- Public payment policies use MD-PAYMENT-2026-02, retaining earlier versions. All public payment methods accept the displayed payment terms through the explicit Save action; no public payment-policy checkbox or booking-only-card disclaimer is shown. Staff retain their policy-reviewed control. The stored policy includes both displayed variants and acceptance records the intended method. No tax, price, cancellation calculation, surcharge or issuer-hold rule changes.
- New confirmation messages use MD-EMAIL-2026-02 with deterministic branded HTML from the frozen message text and a plain-text alternative. Existing frozen messages remain intact; paid/corrected resends retain actual received and remaining facts.
- Browser history uses browser-session-owned step checkpoints, server-side stale-flow/edited-answer checks, no-store headers and back/forward-cache revalidation. It creates no financial GET action. Completed flows resolve to the saved receipt.
- The original provider frame was surrounded by excess height. The public payment frame has compact responsive sizing; genuine provider iframe/card-brand acceptance remains part of hosted testing. Local browser captures simulate provider card entry and both external adapters; no external requests or actual charges are claimed by those checks.
- No schema changes are required. Use the normal Functional deployment; preserve existing sandbox flags, credentials and disabled backups.

The owner-facing [testing guide](SIXTH_BATCH_TEST_GUIDE.md) covers the full batch. The owner subsequently reviewed waiver-page images and one sample branded email as well as Payment Details. The email design and all collected changes are approved; no additional images are requested.

## Verification completed

- 612 PostgreSQL tests pass, including new owner-only retry/unknown-outcome checks, shared-parent completion privacy, adult-only signing, preserved original waiver coverage, method-switch consent, frozen/escaped HTML email, browser checkpoint behavior and restricted runtime-role insertion of the new policy versions.
- Ruff, Django checks and migration-drift checks pass; no schema migration is generated. Existing deploy-helper tests remain in the full suite.
- Chromium checks pass at 1440px and 390px for Credit card, Cash, Check and Zelle, with no horizontal page overflow or JavaScript errors. Card-save validation, confirmation gating and an end-to-end browser booking/navigation flow pass with synthetic adapters. [Full payment-page images](design-review/sixth-payment-review/README.md).
- [Post-deployment test guide](SIXTH_BATCH_TEST_GUIDE.md) and [Word copy](SIXTH_BATCH_TEST_GUIDE.docx) were prepared after implementation and reopened for verification.

Hosted functional acceptance remains the owner's post-deployment review. Visual design review and the collected follow-up changes are approved. This work has not been merged or deployed by the agent.

## Payment-image review corrections

- Only the lower Save card securely action appears, adjacent to Confirm booking. Initial primary/backup messages are consolidated below the buttons.
- Switch payment method is raised slightly and separated from the following backup-card note. The full booking-only-card disclaimer and public payment-policy checkbox are removed; retention/dependency behavior itself is unchanged. Saving records acceptance of the displayed terms, with cancellation and future-use consent separate.
- The disabled confirmation control becomes rose after saving, pulses gently three times, receives focus and scrolls into view only when needed. Reduced-motion preferences suppress the pulse. Success text explicitly instructs customers to click Confirm booking to finish. Nothing automatically confirms or charges.
- The staging sandbox acknowledgment is omitted from the production form.
- Phone interaction checks caught and fixed decorative-arrow pointer overlap; it no longer obstructs either button. A saved page can explicitly change/save another card without reusing the earlier nonce-exchange request key.

Updated browser checks also pass for a saved page changing cards after reload, primary/backup acceptance without the removed checkbox, no decorative-arrow obstruction, confirmation focus/visibility and reduced-motion suppression. The [animation preview](design-review/sixth-payment-review/confirm-booking-animation.webm) records the actual local transition using synthetic provider entry.

## Approved waiver follow-up and final handoff

The owner approved the sample email design and requested all collected changes in the same PR, with an updated ZIP and one deployment command and no further image review.

- Customer waiver selection pages now use “Sign Waiver” and “Every participating minor needs a signed waiver.” The signing form uses the same heading and sentence; minimal thank-you pages retain their approved thank-you headings.
- Current-waiver and post-signing summaries use “Signed by [adult] for [minors]”, with the existing expiry information where applicable.
- Parent signing asks for first names; legal guardian signing asks for first and last names and rejects missing surnames before storing evidence. The form updates its label/help with the relationship selection and also validates the posted role server-side. Neither role change nor summary formatting appends or removes surnames. Earlier signed names and evidence remain unchanged.
- The approved email design is unchanged. No new screenshots are prepared for this follow-up.

Final follow-up verification: all 612 PostgreSQL tests pass; 12 desktop/phone browser checks cover all four selection variants and both signing relationships, including dynamic label/help changes, guardian missing-surname rejection, preserved typed names, and updated signer summaries. No new screenshots or external provider operations were created.
