# Fifth owner-feedback batch

Source: the complete New Fifth batch of comments.docx (15 comments and 15
screenshots), followed by the owner's four clarified answers and explicit
implementation/PR authorization. Review the related changes together. The owner
waived review screenshots for this batch and will test after deployment.

## Approved behavior and overlaps

| Comments | Result |
| --- | --- |
| 1 | Child age guidance says Ages 1–11 for Open Play \| Ages 3–11 for Supervised Play. Quantity label remains Number of children. |
| 2 | Quantity label is Grip socks; the help still explains that the quantity counts pairs. |
| 3 | On the two-column Session Details layout, the estimate begins level with the first input box, below its label. Phone stacking, item-only subtotal, fee/tax exclusion, right-aligned Continue and wider outside-card gap remain. |
| 4 | No redundant Start again action on initial phone entry, including its validation-error state. Later verification/recovery restart actions remain. |
| 5 | Retry copy says You can try another number below, enter an email address to find your customer profile, or continue as a new customer. The email link and inline new-customer action work; no duplicate action beside Continue. Explicit new-customer continuation uses the already checked unmatched number, not an unfinished replacement in the retry field. |
| 6, 11 | Explicit new-customer continuation and No/unmatched-phone Details start directly at Your details. Correcting an invalid initial phone does not introduce returning-customer guidance. |
| 7 | After a second unmatched number, show No customer was found with [second number], followed by the recovery-options sentence above Your details. Keep the second number and selected session. |
| 8, 14 | Suppress introductions in the specified unsuccessful email-recovery cases: unmatched-phone email search, and name-failed email retry. Keep the heading, field and relevant error. Preserve initial/other recovery introductions; this is not a blanket removal. |
| 9, 10 | Yes/current-phone verification starts We found a customer profile, including validation retries. Looks like you've been to Monkey Do in the past belongs to No/current-phone silent discovery. |
| 12 | Contact validation errors omit the recovery introduction. In the public duplicate-email error, go back to the booking page links to phone entry in the same selected session and clears previous verification/contact state. |
| 13 | No/current-phone and retry-number/current-phone entries use the same optional Last Name/Email verification as Yes/current-phone, requiring at least one. Remove the redundant separate email-recovery action there. |
| 15 | Public duplicate-email wording omits We can remove this email address from the other customer profile. |

The duplicate-email message/link changes also apply to an identified customer
adding a missing email, as approved. Staff retain their shorter permitted-profile
message. Current email uniqueness, historical-email handling, optional referral,
actual customer creation at final booking save and existing booking records are
unchanged.

## Verification boundaries

The owner explicitly extended the [fourth-batch matrix](OWNER_EDITS_BATCH_4.md)
to current-phone matches reached through Yes, No and retry-number entry. Name,
email or both can verify that phone-selected customer; partial names still need
confirmation. Keep accurate name/email/both success messages and appropriate
headers throughout recovery/confirmation steps.

The approved two conflict branches carry into these entry routes: simultaneous
name/email may reach the verified profile-choice exception; email-first conflicts
ask for a name and then require restart/help. Never show the other profile's
phone before its own name/email verification in the choice branch, or at all in
the email-first stop branch. Owner Dashboard alerts remain deduplicated/audited.
Verification does not reassign contacts, merge profiles or grant staff access.
Previous-phone confirmation and unmatched-phone recovery proofs stay distinct;
a current email alone does not identify a family when no phone/name proof exists.

The internal returning_current flow marker is retained for compatibility with
in-progress fourth-batch flows; new approved No/retry current matches now receive
it too. No model migration, provider, credential or configuration change is
required. Homepage/About design, active memberships, real payments and waivers
are outside this batch.

## Validation and release

441 local PostgreSQL 16.2 tests passed, including 13 new fifth-batch tests and the
updated fourth-batch scope regression. Tests exercise actual route transitions,
selected-session recovery, escaped linked validation errors, conflict privacy,
explicit verified choice and final booking association, preserved contacts and
unchanged previous-phone confirmation. Existing full-suite coverage includes
stale proofs/forms, email uniqueness races and deployment recovery.

Chromium checks passed at 1440px, 1024px, 390px and 320px: current-phone
verification, inline new-customer action, same-session linked recovery, both
failed-email contexts, supervised quantities and actual input/estimate alignment.
No page JavaScript errors or horizontal overflow; no screenshots created. The
portable PowerShell handoff test passed with SSH/SCP mocked, including the exact
fifth-batch block and duplicate browser filenames. Native Windows/GitHub results
are recorded separately in the PR.
The owner will perform hosted interactive acceptance after merge/deployment.
Use the [routine release handoff](OWNER_FEEDBACK_BATCH_FIVE_RELEASE.md): browser
ZIP download followed by one PowerShell block, with no reviewed-schema flag.
