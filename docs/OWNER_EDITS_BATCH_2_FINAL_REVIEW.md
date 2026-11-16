# Final second-batch Word-document review

Source: the complete **Responses to Changes for Proposals for second batch of edits.docx**, all nine screenshots and the owner's subsequent answers. No private Word document or embedded screenshots are published. This increment follows the implemented initial batch and response-document follow-up on the same review branch.

**Local implementation and new screenshots only. Staging is unchanged. No PR or deployment command has been prepared; image review remains pending.** Earlier galleries remain unchanged as review history.

## Coverage and overlapping requests

| Word screenshot | Comment / approved answer | Implemented result | New gallery |
|---|---|---|---|
| 1 | Clarify earlier membership versions | Earlier details say exactly “This previously saved version is read only”, with a link to the latest details. Versions remain history within the same membership. | 01, 03 |
| 2 | Public-only progress; clarify final test screen and wording | Progress stays public-only. Customer completion says “You're all set for your MonkeyDo adventure!” with “Book another play session”. Test limitations remain visible; staff Setup pending is unchanged. Cancelled receipts do not show the success headline. | 20 |
| 3 | Remove repeated match success on Payment Details; rename edit action | Payment Details keeps the family/contact summary without the repeated name-match message. The edit action is “Change your session details or your payment method”. | 19 |
| 4 | Explicit returning/new-customer email examples | Show phone-match surname verification without email disclosure, verified family with email on file, and new-customer details after silent no-match lookup. | 16–18 |
| 5 | Open-only calendar wording and About link | Available slots without supervised availability and Open-only Session Details say “This session is open play only”. Group instructions are followed by linked About guidance. Closed/full/not-yet-open statuses are preserved. | 15, 17 |
| 6 | Supervised field order and referral meaning/ownership | Create/Edit booking place Supervised Play directly after Session. Optional referral belongs to the customer profile, collected once for new customers and editable by staff there. Existing booking answers stay on their original records. | 08–13, 18 |
| 7–8 | Compact Today/Bookings multi-select | One shared, initially closed dropdown with All sessions and wrapping selected-time summary. Popover choices do not expand the filter row; old helper sentence is removed. Native checkboxes and server-side All sessions retain fallback behavior. | 04–07 |
| 9 | Distinct membership ID pattern | Existing IDs display as #M1/#M2 on list, details, edit forms and customer cards. Underlying IDs, links and immutable version ownership are unchanged. | 01–03, 10, 14 |

These changes were handled together because the two selectors share one component, booking create/edit share a form, referral spans customer/public/staff flows, and membership identifiers appear on several pages. The approved customer-profile decision supersedes earlier booking-level collection; the M prefix supersedes plain numeric membership presentation.

## Referral data behavior

- New public customers see the optional question with name/email in Customer Details after the phone lookup. Returning customers are not asked again, including profiles with no recorded answer.
- Reviewing details creates no customer, referral record or capacity hold. Successful final submission saves the customer answer and audit atomically with the pending booking. A failed booking rolls it back; repeat submission does not duplicate the customer or reservation.
- Staff create/edit use the existing customer permissions, form validation, stale-edit checks and before/after history. Omitted referral parameters in older service callers preserve the existing customer answer.
- Existing Booking.referral_source values are retained and displayed as earlier-booking information. They are not moved, overwritten or automatically chosen as the profile answer. New booking forms no longer collect or edit them. Forged booking input cannot change the customer answer.

## Validation and images

Full local PostgreSQL suite: **361 tests passed**. Added cases cover profile referral audit/stale edits, preservation of earlier booking answers, forged input, final-save atomicity/idempotency, returning-customer behavior and explicit All sessions. Existing membership version, concurrency, email, pricing, permissions and scheduling checks continue to pass.

The separate [final-review gallery](design-review/owner-edits-batch-2-final-review/README.md) contains **40 JPGs: 20 states at 1440px and 390px**. Browser checks cover collapsed/expanded selectors, unchanged filter-row height, All sessions/multiple choices, summary updates, Escape dismissal, public-only progress, verified email disclosure, new-customer fields, approved copy, completion, JavaScript errors and document overflow. Wide staff tables scroll within their own region. All fixtures are fictional and local; these images do not establish hosted MFA, real payments, waiver completion or email delivery.

Ruff lint/format, Django system checks, migration drift and static collection passed. Screenshot verification is in the gallery's verification.json.

## Database and deployment boundary

New migration **0025_customer_referral_source** adds an optional Customer field after the earlier pending migrations **0023** and **0024**. It performs no booking-data rewrite or historical referral backfill. Existing customer answers start blank unless entered through the new workflow. No migration has been run against hosted staging.

After image approval, the eventual release must account for all pending migrations, current-email duplicate preflight, backup/recovery and the separate migration identity/runtime permissions. The ordinary deployment helper refuses pending migrations. No deployment guard was bypassed and no deployment command or PR was created for this image review.
