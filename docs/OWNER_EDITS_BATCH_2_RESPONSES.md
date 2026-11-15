# Follow-up to second-batch proposals — screenshot review

Source: the complete **Responses to Proposals for second batch of edits.docx**, including all twelve screenshots, and the owner's subsequent answers and approval of all four related-page extensions. The private Word document is not published. The owner authorized continued implementation and asked to review new images before PR/deployment preparation.

**Implemented locally; not deployed. No PR has been opened.** The earlier second-batch images remain unchanged and approved. This separate gallery contains only the follow-up work: [desktop and phone JPGs](design-review/owner-edits-batch-2-responses/README.md).

## Requested changes and coverage

| Request | Result | New gallery |
|---|---|---|
| Compact membership facts and remove the anonymous-places paragraph | Side-by-side facts on desktop, stacked on phone; removed the specified paragraph. Draft status remains accurate. | 01 |
| Working membership editing | Owner and staff can edit type, amount, months, start date, billing and expected payment method. Earlier versions remain readable; owner-only short-term exceptions remain protected. | 02, 19 |
| Membership table and linked IDs | Use the existing numeric membership ID, linked to its detail; customer name links to the customer. Editing retains the same membership ID. | 03 |
| Customer-picker wording on both forms | “Select a customer from the search results” on membership and booking forms. | 04, 10 |
| Creation history without a blank Before | Added comments and creation entries show their content; actual edits retain before/after values. | 05 |
| Price breakdown before saving | Booking edits show a live itemized estimate using the booking's saved pricing policy. Fetching an estimate does not save anything. | 06 |
| Payment-method reminder instead of an extra dropdown | An amount-changing Save shows a reminder with Review payment method and Save changes. Review returns focus to the existing selector. A server fallback works without JavaScript. | 07 |
| Bookings and Today layout | Add booking beside the title, Apply/Clear below contact search, filters above the table headings, Enter submits search. Multiple sessions may be selected; none means all. No misleading totals-below caption on Bookings. | 08–09 |
| Fee labels on staff forms | Card options state the applicable stored policy percentage on booking edits and membership edits; creation uses the applicable current policy. | 02, 04, 06, 10 |
| Shorter staff duplicate-email message | Staff see a short error and a link to the conflicting profile when authorized. | 11 |
| Four visible public steps | Choose Session → Customer Details → Session Details → Payment Details. Completion follows; no fifth Review step. | 12–18 |
| Returning-customer and missing-email wording | Requested success message appears before the missing-email prompt, with no empty email separator. | 13 |
| Full public duplicate-email recovery message | Requested longer public wording, without disclosing another customer's record. | 14 |
| Public play-type and group instructions | Open-only sessions show fixed “Play type: Open Play”; supervised instructions/choice appear only when available. Grip-sock instructions accompany that field; card choice includes its fee rate. | 15–16 |
| Payment Details step | Existing breakdown/save screen carries the fourth progress step. The payment-method selector stays within Session Details. | 17–18 |

The document's “Other settings” screenshot was an explanation request: the notice describes effective date-wide, weekly-default or Saturday restrictions separately from the individual session fields. No additional change was requested after that explanation; its previously approved screenshot is not duplicated here.

## Validation

- **355 PostgreSQL tests passed**, including immutable membership revisions, edit permissions, old pricing preservation, short-term owner exceptions, stale/concurrent edits, submission retries, rollback, estimate proofs, CSRF, multi-session filters, creation history, duplicate-email messages and conditional public play types.
- Ruff lint/format, Django system checks, migration drift and static collection passed.
- Real local browser captures: **38 JPGs, 19 states at 1440px and 390px**. Browser checks exercised Enter submission, multiple selected sessions, estimate updates, payment reminder/focus, profile links, four progress steps and pending-test completion. No document overflow or JavaScript errors were observed. Wide staff tables scroll within their own region.
- Fixtures are fictional and local. No hosted database, real payment, provider delivery, waiver or active-membership integration was exercised or changed.

## Database and release boundary

This follow-up adds migration **0024_membership_draft_revisions**, after the earlier batch's pending **0023_owner_feedback_batch_two**. It adds immutable revision records, preserving original membership rows and cycles; there is no historical-data rewrite. It grants the existing MonkeyDo Staff group the membership-draft edit permission while preserving its other permissions. Custom roles still require their corresponding view/customer/edit permissions.

Before a future release, review both migrations, current-email duplicate preflight, the separate migration identity and runtime grants, backup/recovery and the existing deployment guard. The routine functional deployment helper intentionally refuses pending migrations. No deployment command has been prepared for this review and no schema change has been made on the hosted site. The owner will review these images and give the next go-ahead before PR and deployment preparation.
