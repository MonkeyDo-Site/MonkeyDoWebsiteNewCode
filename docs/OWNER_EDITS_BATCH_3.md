# Third owner-feedback batch — implementation and image review

Source: the complete **THird batch of comments.docx**, all twenty numbered items,
both final homepage design requests, all 26 screenshots, and the owner's answers
and development/image-review go-ahead. The private source document is not
published. Approved scope and clarifications: [review](OWNER_EDITS_BATCH_3_REVIEW.md).

**Implemented and tested locally; owner image review pending. No PR or deployment
has been performed for this batch.** The shared staging website remains on its
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
| 18 | Exact current email plus tolerant surname recovery on unmatched phone or failed phone-selected surname, then family confirmation. No historical-email identification, profile rename, phone rewrite, unrelated public suggestions or merge. | 25–26 |
| 19 | Read-only live itemized estimate inside Session Details, including applicable card fee, no displayed tax and Total before applicable taxes. Final Payment Details retains tax. | 27–28 |
| 20 | Compact shared Open/Supervised information cards outside the form; no duplicate booking buttons; phone stack below form. | 27 |
| Homepage | Compact 2×2 About areas and smaller play-card images/spacing on Home; standalone About layout and approved masters retained; play buttons remain aligned. | 01–03 |

## Verification

- **397 tests passed on local PostgreSQL 16.2.** GitHub CI runs PostgreSQL 17;
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
- **58 JPGs: 29 states at 1440px and 390px.** Chromium exercised actual local
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

The previous `-ApplyReviewedBatchTwo` path is pinned to 0023–0025 and intentionally
cannot prepare this migration. After image approval, prepare the new reviewed
schema/deployment path, private checkpoint, migration identity/runtime grants and
recovery checks. Keep the browser-downloaded ZIP plus one PowerShell deployment
command preference. Do not deploy or bypass guards during screenshot review.

Compatibility matters: the older release does not understand date-level private
visibility or reservation blocks. After those features have been used, a blind
code rollback could ignore their booking restrictions. Prepare compatible
recovery rather than reversing this migration or promising that old code enforces
new state. Reinstating a globally unique start is also invalid once custom and
standard sessions share a start. Production/live-payment approvals remain separate.
