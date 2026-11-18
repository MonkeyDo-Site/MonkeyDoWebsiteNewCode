# Shared workflow and screen standards for the remaining stages

This is the carry-forward specification for improvements approved during the
first development stage, including PRs 25–27 and the subsequent owner planning
answers. It supplements [main requirements](MONKEYDO_REQUIREMENTS.md); it does
not authorize implementing the next phase. Business-specific rules remain in
[payments](PAYMENTS.md), [memberships](MEMBERSHIPS.md) and the waiver requirements.

The owner wants future features to build on the improved experience, rather than
restart from the original screen plans. A standard applies wherever it fits the
same operation; a page-specific exception must be stated. Proposed new fields,
statuses, date meanings and workflow extensions still need review before building.

## Inheritance matrix

| Area | Deployed convention to retain | Membership application | Waiver application |
| --- | --- | --- | --- |
| List layout | Responsive tables, meaningful headings directly above rows, compact filters, no redundant heading or Open column when the record ID already opens details | One row per membership, linked existing #M ID and permitted customer name, latest details only | Consistent list layout with linked waiver record/customer, coverage/version/validity information; do not collapse different signers or minors into one misleading latest-customer record |
| Search | Family name/ID, normalized phone and email; clearly labelled possible word/partial/typo matches in authorized staff searches | Reuse shared staff customer search and picker; preserve customer-type and permission checks | Add authorized signer/minor search from approved requirements, distinguishing signer identity from booking customer; never expose it through public lookup |
| Filters | Compact combined controls, Enter for text search, automatic valid date/session filtering, Clear actions preserving unrelated selections, keyboard/no-JS fallback | Reuse interaction pattern for applicable type/status/date/customer filters; start/expiry/charge date meanings must be explicit | Reuse for applicable coverage/version/signing/expiry filters; date meaning must be explicit |
| Default dates | Today stays today; Bookings defaults to today through next year and can clear to all history | Do not blindly copy that default: it could hide an active membership purchased earlier; specify the list's useful defaults at its design review | Do not blindly copy booking dates: current coverage can have an earlier signing date, and history must remain accessible |
| Customer pages | Compact at-a-glance cards, expandable history, one Bookings card and separate Membership, Waiver and Payment cards; no tabs or repeated clutter | Replace truthful draft-only information with actual current membership/payment information only when implemented | Replace placeholders with actual coverage and signed-file links; distinguish expired history from current coverage for everyone |
| Form structure | Short fields, familiar customer picker, sensible order, inline help, parent/detail navigation and retained fields on validation/back navigation | Reuse current draft editor's presentation for permitted operations; show financial/benefit impact where an active change needs it | Reuse visual language, but include complete accessible legal text and explicit signing; do not squeeze away required consent or signing information |
| Estimates | Public Session Details shows a low item-only estimate, without card fee or tax; final Payment Details includes applicable fee/tax | Preserve the membership estimate's applicable configured fee and accepted pricing rules; do not globally hide fees from staff or membership estimates | No duplicate payment estimate or card fields on shared-parent signing screens |
| Save and payment | Saving an edit/estimate is not charging; preview revised amount before Save and remind about expected payment method when applicable | Show new prospective installments/adjustments separately from payments already received; explicit financial actions only | Signing is its own explicit action; form navigation or booking Save cannot fabricate signature evidence |
| Histories | Readable actor/date/time and field descriptions; no Before for creation; before/after for edits; earlier version read-only | Same #M ID after an edit; current version on ordinary views, earlier details in history labelled This previously saved version is read only | Signed evidence immutable; new signing/version creates separate evidence without overwriting the original or its covered participants |
| Contact rules | Same profile, unique current email ignoring case; historical-only warning for staff and public-booking owner notice; customer-owned referral | Apply shared customer rules; do not ask referral on every purchase/renewal | Signers may be different parents; customer-email uniqueness is not a blanket uniqueness rule for signer contact addresses |
| Public verification | Email recovery reuses the already-entered matched phone; both must identify the same profile. Unmatched-phone recovery may reuse an already-entered surname. Never ask it again or reveal from email alone | Reuse approved public verification if customer lookup is needed, without broad suggestions | Shared signing links reveal only approved appointment context, never other families, customer contacts, payments or other signatures |
| Dates and language | New York dates and Motzei Shabbos throughout screens, summaries, histories and outputs; preserve numeric/ISO values | Apply to term/calendar, renewals, installment dates and emails | Apply to signing/expiry/appointment displays, generated output and emails without changing approved legal wording |
| Eligibility | Shared visibility, weekly/date closure, reservation blocks, cutoffs, capacities and concurrency controls | Membership prices/benefits never bypass session eligibility; reserve/release benefits atomically with booking changes | Coverage requirements integrate with booking/arrival gates, not a separate route that silently confirms an ineligible booking |
| Permissions | Server-enforced owner/staff capability checks; Add booking on Today; session configuration only in Owner Scheduling | Normal staff sale/renew/add and approved corrections remain allowed; owner exceptions/refunds/comping/consolidation remain owner-only | Approved staff signing/view/search/paper-coverage assistance; no public file access or implied export privilege |
| Status and notifications | Attendance, expected tender, money received, setup and delivery are separate facts; truthful empty/pending/failed states | A draft is not paid or active; unknown collection is not a decline or successful installment | A screen interaction is not saved evidence; paper marking is not electronic signing; sent/accepted email is not confirmed inbox delivery |
| Responsive review | Existing typography, compact cards/tables, accessible labels/focus, desktop and phone layouts; original assets preserved | Review affected screenshots before deployment, plus actual payment/benefit scenarios | Review staff and public signing/coverage screens, plus actual persistence/access/retention scenarios |

Exact new table columns and filter choices are to be shown in each stage's screen
plan. They are not permission to invent a second numbering scheme, add every
possible filter, expose staff data publicly or replace distinct waiver coverage
with a single yes/no customer flag. Existing customer, membership and booking IDs
must remain stable. The deferred homepage design is not reopened by this plan.

## Changes carried into every later booking-dependent feature

- Keep scheduling's distinct backend-only visibility, closed-for-reservation and
  source-specific custom/booking blocks. Preserve original times, IDs and booked
  exceptions; explicit reopening removes only the relevant block.
- Reuse date-to-session selection and final server-side eligibility checks. An
  eligible price, paid membership or signed waiver does not guarantee capacity.
- Preserve one coherent booking editor, accepted historical pricing, stale-edit
  protection, atomic audit and explicit count/timing/payment review. Paid money
  and consumed benefits require adjustments, not rewriting an old estimate.
- Preserve current customer matching, unique contact rules, School/Day Camp/Family
  handling, referral on the customer, linked profiles and readable histories.
- Keep public Session Details's estimate low and item-only. Card processing fees
  and tax are shown on final Payment Details. Backup-card entry alone does not
  turn an alternate-method estimate into a card-funded quote.
- Keep four current public progress steps; introduce the approved waiver step
  when signing is implemented, without adding a redundant visible Review step.
  Staff screens have no customer progress bar.
- Retain the approved completion headline and Book another play session action,
  with truthful setup/confirmation/payment/delivery explanations.
- Membership detection, any member-information popup and benefit-adjusted booking
  pricing belong to the active-membership stage, not the upcoming ordinary and
  supervised booking stage. Do not add an inactive placeholder popup now.

## Earlier test reservations

The owner chose new reservations for acceptance of the completed card/waiver flow.
At that phase's reviewed migration, identify all pre-existing test-workflow bookings, including cancelled records,
as the earlier workflow; preserve ID, status, dates, quote, customer and history.
Use explicit stored workflow provenance, not a guessed appointment date or a
hardcoded development-day cutoff. New integrated-workflow bookings carry their
own version so later deployments do not repeatedly classify all records as old.

Proposed compact presentation: **Old test booking** beside the linked ID in staff
Today/Bookings and in booking details/customer booking history, with an applicable
All / Old test bookings / New booking workflow filter. It describes the workflow,
not whether the appointment is in the past. Avoid another wide table column.
This classification is planned, not applied to the current database.

Earlier records keep their existing pending-test inspection/edit/cancel tools and
capacity effects. They are not automatically confirmed, charged, signed, emailed,
deleted, migrated to the new completion flow or turned into memberships. If they
occupy a test slot, staff can explicitly cancel them as before; do not clear the
database. Public pages retain truthful test-state explanations rather than an
internal development-version control. New tests use new reservations in the new
workflow; sandbox/live data are never interchanged.

## Keeping documentation and implementation synchronized

For each future feature/change, the implementation plan and PR must include:

1. **Trace the request:** link its source/owner clarification; identify page-only
   versus shared behavior and propose any unapproved cross-page extension.
2. **List affected pages:** cover public/staff, list/detail/editor, customer cards,
   Today/Dashboard, histories, email and relevant printing/exports. Mark genuine
   not-applicable cases, rather than silently skipping them.
3. **Update the same sources together:** main requirements and this shared
   standard, the relevant domain guide, development boundary, staged acceptance
   cases, decision record and current build status. Historical evidence stays
   historical, clearly labelled; it must not override the current summary.
4. **Reuse shared implementation:** tables/filters, customer picker/matching,
   navigation/date format, pricing/eligibility and history components/services.
   A new module must not introduce a competing rule or copy an obsolete prototype.
5. **Verify the rule where it matters:** use focused permission/privacy,
   concurrency and domain tests; cross-page/browser checks for a shared UI change;
   actual provider/file/delivery tests before claiming integration works.
6. **Review the result:** affected desktop/phone screenshots and workflows precede
   deployment. A screenshot does not prove payment, waiver storage or delivery.
7. **Release coherently:** identify schema/config/worker/backup changes and
   compatible recovery. Retain browser ZIP plus one PowerShell command; update
   its closed migration allowlist explicitly for that release. No automatic
   rollback can undo provider payments, signed evidence or sent messages.

The next-stage plan must use this matrix as acceptance criteria at its start,
not postpone consistency checking until the full website is finished. This
planning update changes documentation only, not application or hosted data.
