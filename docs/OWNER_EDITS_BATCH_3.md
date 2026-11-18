# Third owner-feedback batch — implementation and image review

Owner subsequently reported this reviewed release deployed. The current baseline
and remaining stages are in BUILD_STATUS.md and NEXT_PHASE_REVIEW.md. Earlier
image-review/pending-deployment notes below are historical.

Source: the complete **THird batch of comments.docx**, all twenty numbered items,
both final homepage design requests, all 26 screenshots, and the owner's answers
and development/image-review go-ahead. The private source document is not
published. Approved scope and clarifications: [review](OWNER_EDITS_BATCH_3_REVIEW.md).

**Owner authorized PR and deployment preparation after image review, excluding
all homepage design changes.** Deployment was subsequently reported complete by the owner. The shared staging website remains on its
previous approved release. [Desktop and phone JPG gallery](design-review/owner-edits-batch-3/README.md).

## Coverage

| Comment | Implementation | Review screens |
| --- | --- | --- |
| 1 | Weekly single/bulk forms use Closed for reservation, checked means closed; existing open/closed state is preserved through inverse UI mapping. | 16–17 |
| 2, 14 | Shared individual-word/partial-name typo matching across Customers, Today/Bookings and booking/membership pickers. Exact/direct results first, possible matches marked. Brawn/Braun Customer and bnot/bnos miriam pass. | 05, 07, 10 |
| 3 | Remove the redundant visible Bookings caption, retain the accessible name. | 04–06 |
| 4 | Default today through same calendar date next year; optional bounds and all-history searches; compact Clear dates versus default-restoring Clear all. Dates refresh results/options; closing session picker applies selection. Today stays fixed. | 04–06 |
| 5 | Date-level Backend only hides current/later-generated sessions without closing authorized staff booking. Individual visibility is preserved when removed. | 13 |
| 6 | Calendar date then eligible session in staff create/edit/change timing, with async choices and explicit non-JavaScript fallback. | 11–12 |
| 7 | School customer type; existing owner type-edit permissions retained, staff can book for a School record. | 08–09 |
| 8 | Owner booking forms can close the session to additional reservations atomically with booking save. Other bookings remain; staff cannot forge the operation. | 11–12, 21 |
| 9 | Owner custom one-time interval previews its affected standard sessions; active-booking conflicts show linked IDs/family/times. Original records remain. Blocks have distinct sources; explicit reopening preserves independent closures. | 18–21 |
| 10 | Completion sentence uses active-leaf rose, preserving alignment and wrapping. | 29 |
| 11 | Owner Individual Date navigates on valid date selection; View date is only a no-JavaScript fallback. Actual date-setting edits still require Save. | Browser checks; 13/20 context |
| 12 | Separate contiguous current-schedule and furthest-existing dates, with expandable ranges showing actual timings, earlier settings, preserved exceptions, blocks and missing dates. Generation explains reservation blocks. | 14–15 |
| 13 | Create customer sits beside the heading, above search; All/Family/Day Camp/School filter combines with search. No unrequested future membership filter. | 07–09 |
| 15 | Ten-digit phone wording omits US, preserving Canadian and +1 normalization. | 22 |
| 16 | Approved new-customer continuation wording and go back link retain the selected session. | 23 |
| 17 | Success! Your details are ready. Please proceed with your booking. Customer/booking still save atomically at final submission. | 24 |
| 18 | Email-only recovery reuses the entered phone; email and phone must identify the same profile before family confirmation. An unmatched-phone branch can reuse an already-entered tolerant surname. No repeated name field, email-only disclosure, historical-email identification or phone rewrite. | 25–26 |
| 19 | Read-only live itemized estimate low beside socks/payment-method fields, showing the base item subtotal only, without card fee or tax. Final Payment Details retains the applicable card fee and tax. | 27–28 |
| 20 | Compact shared Open/Supervised information cards outside the form; no duplicate booking buttons; phone stack below form. | 27 |
| Homepage | Deferred by owner; restore deployed homepage template/styling, exclude earlier compact/cropped proposals. Standalone About page and assets unchanged. | Excluded |

## Verification

- **407 tests passed on local PostgreSQL 16.2.** GitHub CI runs PostgreSQL 17;
  record its separate results before PR readiness. This is not production or
  hosted owner acceptance.
- New coverage includes concurrent custom-session creation versus booking,
  source-specific reopening, independent manual closures, failed-save rollback,
  owner/staff permissions, duplicate custom/standard start times, stale preview,
  actual schedule comparison, all-history dates, School filtering, two-piece
  email recovery, historical-email refusal and read-only pretax estimates.
- Prior public-mismatch tests now assert the approved recovery branch while still
  forbidding unrelated-profile disclosure. The frozen batch-two migration test
  uses its historical graph; the batch-two runtime guard still refuses new
  unreviewed migration plans.
- Ruff lint/format, Django checks, migration drift, static collection, JavaScript
  syntax and whitespace checks passed.
- **52 JPGs: 26 states at 1440px and 390px.** Chromium exercised actual local
  forms, live estimates, filtering, picker searches, conflicts and completion;
  no JavaScript errors or document overflow. Additional 320px and staff access
  checks passed. Staff tables scroll within their own region.
- The fixtures contain fictional families and a frozen local review clock.
  Owner authentication is a synthetic verified test fixture, not evidence of new
  hosted MFA delivery. No actual card, signature, benefit or outbound booking
  email was created. Original source photos/approved image masters and earlier
  galleries are unchanged.

## Schema and eventual deployment

Migration **0026_owner_feedback_batch_three** adds date backend visibility,
custom-session state and source-specific reservation blocks; updates customer
choices/phone validation wording; and replaces unique session start timestamps
with an ordinary-session-only unique constraint plus a lookup index. This permits
an explicit custom interval to start at a retained standard slot's time while
ordinary creation/generation still enforce overlap rules under transaction locks.
It does not rewrite existing customer/booking/quote/membership records.

The explicit `-Target Functional -ApplyReviewedBatchThree` path now checks the
pinned 0026 migration and 0025 baseline, checkpoints the private database, applies
DDL/runtime grants atomically and verifies permissions before activation. The
previous batch-two option cannot authorize this migration. Routine migrations
remain refused. Use the browser ZIP plus one PowerShell block in the
[release handoff](OWNER_FEEDBACK_BATCH_THREE_RELEASE.md).

All code switches, rollbacks and interrupted recovery pause writes and check
compatibility. Older code is refused if backend-only dates, custom sessions or
active source-specific blocks exist; it would ignore the new restrictions. The
current pointer is preserved and service restarted on refusal. Automatic database
rollback is never performed. Production/live-payment approvals remain separate.


## Image-review follow-up — full homepage About photographs

Owner clarified that smaller images means scaling the full image down, not
cropping it to a short strip, and that the standalone About page was already
approved. Only the homepage About image styles were revised: maximum width
280px, proportional automatic height and no fixed aspect-ratio crop. The compact
2×2 layout remains. Existing photo files and standalone About styles are unchanged.
Homepage play cards were not changed by this clarification.

Browser checks at 1440px, 390px and 320px verify natural image proportions, full
loaded images, the desktop 2×2 arrangement, no page overflow and unchanged
standalone About styling. Screens 01–02 were refreshed at desktop/phone sizes;
other gallery images remain unchanged. This styling-only follow-up did not
require a new migration or another full application-suite run. Staging remains
unchanged; PR/deployment still await the owner's image review.


## Image-review clarification — new weekly default starts open

The owner confirmed that Add a weekly default session must start with Closed for
reservation unchecked. The form already behaved that way; its field now states
initial=False explicitly. The earlier review capture had intentionally checked
it to illustrate the closed state. Screen 16 desktop/phone now shows the actual
unchecked default. Existing closed defaults still render checked on editing;
explicit user selections remain intact. Browser checks and direct form checks
passed; no migration or deployment was performed.


## Image-review follow-up — inline email recovery link

Use exactly: You can continue below as a new customer, go back to try another
number, enter an email address to find your customer profile, or call/text us at
848-238-5147 for assistance. Go back and enter an email address are inline links;
the duplicate actions below this form are removed. Both keep the selected
session. Email lookup still requires email and surname, with no early customer
creation or saved-phone change. The 27 affected PostgreSQL public-flow tests
passed and Chromium checked both links at desktop/phone widths. Screen 23 and
its image checksums were refreshed. Staging and PR/deployment remain unchanged.


## Image-review follow-up — lower estimate and reuse the entered phone

The owner requested moving the estimate lower and removing the repeated surname
field from recovery. Clarification: after a phone matches but the surname fails,
the already-entered phone plus current email are the two matching details. The
recovery form now has just Email address, with You can try finding your customer
profile by entering your email address. It cannot reveal a different profile
whose email does not match the phone. Prior unmatched-phone recovery can reuse a
surname already entered earlier; email alone and extra forged recovery-name
fields cannot disclose a profile. Saved phone and customer creation timing remain
unchanged. Recovery completion says Your details match our records.

The estimate now starts lower beside attendee inputs through vertical alignment,
with the mobile order unchanged. Chromium verifies its lower position and the
one-field recovery/phone-email confirmation at 1440px and 390px; screens 24–27
were refreshed. The affected 30 public-booking/recovery tests passed, including
new disclosure/refusal cases. The full PostgreSQL regression suite passed: 400 tests. Staging remains unchanged and image approval still precedes PR/deploy.


## Further image-review adjustment — item-only estimate and restored lead-in

Owner requested the estimate even lower and no card-processing fee in that
estimate. The desktop panel is now bottom-aligned beside socks/payment method;
mobile remains after the inputs. Its rows and displayed total include only base
items (admissions, additional adults and socks). Card choice no longer changes
that live subtotal. The next Payment Details page and saved/staff quotes retain
their existing card-fee/tax calculations and full total. The payment-method
selector's previously approved percentage information remains separate.

After failed surname verification, restore the original first sentence, followed
by the owner's revised second sentence: We couldn't match that name to the
entered phone number. You can try finding your customer profile by entering your
email address. Direct email navigation without a name mismatch does not falsely
claim one. The form still asks only for email and reuses earlier matching details.

Thirty affected PostgreSQL tests passed, including equality of card/cash live
subtotals and fee/tax preservation on final Payment Details. Browser screenshots
24/25/27 were refreshed for desktop and phone; 26 was rechecked. No new migration,
PR or staging deployment was performed.


## Final release scope — homepage deferred

Owner authorized the PR and browser-download/one-command deployment preparation,
while excluding the homepage design proposals. The About/play template is restored
byte-for-byte to 34a77c4 and its existing CSS remains the exact deployed prefix,
with no third-batch homepage overrides. Screens 01–03 were removed from the active
gallery; earlier proposals remain in prior commits. The other 52 desktop/phone
screens and approved functional changes remain. Historical homepage follow-up
notes above describe proposals superseded by this release decision.
