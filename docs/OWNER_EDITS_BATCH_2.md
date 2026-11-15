# Second owner-feedback batch — implementation and review

Sources: only the green-highlighted additions in **First Batch of edits (1).docx**, all twenty numbered items and screenshots in **Second Batch of edits.docx**, and the owner's subsequent clarifications. Original unhighlighted/yellow comments were not treated as new requests. The original Word files and their private screenshots are not published.

The owner approved development and requested desktop/mobile screenshots before deployment. The screenshot gallery uses fictional local data only. **Owner review, PR creation/merge and hosted deployment are pending.** Actual payments, active membership benefits, waiver integration and customer confirmation delivery remain deferred.

## First document — green additions

| Request | Implemented behavior | Evidence |
|---|---|---|
| Compact parent navigation throughout | Linked parent breadcrumbs on backend details; compact scheduling parent and three section tabs; Individual Date is the scheduling entry | Gallery 04–19; browser page/viewport checks |
| Date toolbar and smaller headings | Narrow date field, View date, lighter Edit date settings/Add one-time session on one wrapping row | Gallery 16 |
| AM/PM label correction | Actual local clock context formats ambiguous legacy labels without rewriting saved labels or appointment times | DisplayRulesTests; gallery 13/16 |
| Sunday first | Checkbox choices and displayed weekday lists begin Sunday | Gallery 13–15 |
| Active/inactive terminology and generation eligibility | Open for reservation/Closed for reservation labels; closed defaults cannot generate or accept bookings | ScheduleBatchTests; gallery 13/15 |
| Generated session missing | Confirmed owner's audit results: replacement conflicted with existing dated sessions. Generation now identifies the conflicting record, effective closure, time range, booking history and review link | ScheduleBatchTests; browser reproduction/gallery 35 |
| Generated-through date | Each default displays last generated date, explicitly listing missing expected dates; no automatic generation job | Gallery 13 |
| Similar surname confirmation and typo examples | Phone-selected surname and entered phone shown with Continue, no extra checkbox or rename. Customer/customir, Zorger/Zarger/Zharger/Zorge and Greenfeld/Greenfield tested across shared matching | DisplayRulesTests, PublicBatchTests, existing public/name tests; gallery 28–31 |

## Second document — all twenty items

| Item | Implemented behavior | Evidence |
|---|---|---|
| 1 | Phone/Email columns, linked Booking ID, row filters, required default-today date/range, optional recurring clock time, contact/name search, Open/Supervised and status checkboxes, count-sort toggles, clear filters, pagination retaining criteria | StaffBatchTests; gallery 01–03/34 |
| 2 | Open Play wording in booking display and scheduling play-mode choices | Gallery 01/04/15–16 |
| 3 | Inline checkbox inputs before labels, no checkbox label colon, shared backend field renderer | Gallery 05–06/11/15/18/37–43 |
| 4 | Unified Edit booking changes session, quantities, socks, play type, referral and expected tender. Changed estimate prompts keep/change expected method; no charge. Original price policy and immutable quotes retained | StaffBatchTests, staff booking tests; gallery 04–05/25 |
| 5 | Booking history shows actual before/after field changes and session times | Audit rendering; gallery 04 |
| 6 | Customer contact details and linked customer name; compact cancel section; confirmation works with JavaScript or server fallback | StaffBatchTests; gallery 04/26 |
| 7 | Booking customer picker searches name/normalized phone, returns bounded options and labels possible matches | StaffBatchTests; gallery 06 |
| 8 | Leading country-code 1 matches ten-digit phone; email digits do not accidentally become phone searches | StaffBatchTests and customer tests |
| 9 | Session edit screen explains effective weekly/date/Saturday restrictions separately from the individual fields and links governing settings | Gallery 17–18 |
| 10 | Owner daily-session rows link Add booking with session preselected; closed rows do not offer the action | Gallery 06/16 |
| 11 | Today has one filterable table, empty sessions in selector, session overview/selected-session totals independent of matching rows, contact search, linked names and Add booking for staff/owner | StaffBatchTests; gallery 01/34/44 |
| 12 | Searchable membership customer picker; Type/Amount/Months labels; explicitly audited owner 1/2-month exceptions for both products/billing choices, ordinary staff minimum 3 | StaffBatchTests; gallery 11/45 |
| 13 | Customer listing is a searchable table | Gallery 07 |
| 14 | Compact customer cards, expandable comments, distinct draft membership history and truthful empty payment history | Gallery 08 |
| 15 | Compact customer history with smaller action headings and before/after details | Gallery 09 |
| 16 | Public availability says Open; supervised availability sentence displayed when eligible | Availability/public tests; gallery 21 |
| 17 | Enter your phone number label | Gallery 28–29 |
| 18 | Returning unmatched phone offers alternative/prior phone or explicit new-customer continuation; silent new-customer lookup preserved | PublicBatchTests; gallery 28 |
| 19 | Entered phone included in name verification/failure; correct 848-238-5147 contact number | Public tests; gallery 29–30 |
| 20 | Inline current duplicate-email validation, case-insensitive database uniqueness, optional staff email, historical-only warning/owner notice, public missing-email collection; separate friendly CSRF 403 recovery | PublicBatchTests, StaffBatchTests, CustomerConcurrencyTests; gallery 20/32–33/36/43 |

## Subsequent owner clarifications

- Closing a **weekly default** hides its linked sessions. Closing an **individual dated public session** or **public one-time session** leaves it visible as **Not Available**. Backend-only sessions and public Saturdays stay hidden. No calendar placeholders for ungenerated closed defaults.
- Two booking play-type filters: Open Play and Supervised Play. Date ranges work with or without recurring time selection.
- Today has Add booking for owner/staff, not Add/Edit session. Session configuration remains only in owner scheduling; ordinary staff cannot access those endpoints.
- Current emails are unique ignoring case. Historical-only reuse is permitted: staff see a warning and may proceed; public reuse creates an owner-only Dashboard notice. Previous profiles/history are not revealed publicly or merged.
- Extend clickable customer links/email search to Bookings and friendly before/after history to customer/membership pages. Compact parent navigation applies throughout backend details.
- Multiple weekly slots can be edited together. Final schedule validation permits intermediate old/new overlap but rejects actual final overlaps. Dated updates preserve identity and are planned together; preserving a booked/manual session can block other moves, which are explicitly reported. No existing booking is moved or deleted by generation. New booking-history snapshots retain old/new session clock values so subsequent edits to an unused session cannot rewrite the meaning of the prior booking change. Older audit entries may only have session IDs and resolve the linked record.
- Every relevant generation result explains Created/Updated/Unchanged/Not generated and gives a review link where applicable. Top-of-page counts summarize the results.

## Validation and limits

Full PostgreSQL-backed suite: **339 tests passed** (including schedule swaps/rollback/stale final schedules, protected booked-session cascades, bulk-editor POST, phone/email filters, empty sessions, tender review, unified repricing, historical email notices, owner-only exceptions, CSRF, cancellation confirmation and concurrent email ownership). Ruff lint/format, Django system checks, migration drift and static collection passed. Browser verification and desktop/mobile JPGs are in `design-review/owner-edits-batch-2/verification.json` and its README.

Browser captures use 1440px and 390px viewports, real local forms/endpoints, a synthetic owner/staff session fixture and fictional customers. They are not evidence of hosted owner-MFA acceptance or production readiness. Tables scroll horizontally on phones; the staff menu collapses to reduce scrolling. The original hosted CSRF screenshot cannot establish its underlying browser/proxy/session cause; this increment preserves CSRF checks and supplies a tested recovery screen rather than claiming duplicate email caused it.

## Database/deployment handoff — do not deploy yet

Migration **0023_owner_feedback_batch_two** adds the owner-notice table, optional staff email field state, a partial case-insensitive unique index on nonblank current customer email, and relaxes the draft-term check to permit owner-authorized 1/2-month exceptions. Application permissions and explicit confirmation continue to enforce the exception. No existing bookings, customers, quotes or memberships are deleted, merged or backfilled.

Before migration, run `python manage.py check_customer_emails` using the new prepared release against the intended functional database. It is read-only and prints conflicting customer IDs rather than contact addresses. Migration also refuses existing duplicates before schema changes; owner review is required to resolve genuine duplicates, with no automatic data cleanup. The new command/model can read the existing customer schema before migration.

Use the separate migration identity and existing backup/recovery procedure, verify runtime access to the new notice table/sequence, then the reviewed Functional deployment helper. The ordinary helper intentionally stops when migrations are pending. This batch needs a schema-preparation step; do not bypass that guard or promise code rollback reverses the database. Do not reverse the minimum-term constraint after shorter drafts exist. Staging has not been changed by local testing or screenshots.
