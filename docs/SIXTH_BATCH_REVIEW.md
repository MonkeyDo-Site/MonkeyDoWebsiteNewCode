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
