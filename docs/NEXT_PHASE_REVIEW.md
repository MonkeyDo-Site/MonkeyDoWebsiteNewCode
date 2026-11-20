# Review of the remaining development stages

Initial review: November 16, 2026. Updated after the owner-reported PR #27
deployment and the owner’s responses to this plan.

**Current status: the owner authorized the complete ordinary/supervised booking
stage on November 19, 2026. Implementation is in progress in draft PR #30.** See
[the implementation boundary](BOOKING_COMPLETION_DEVELOPMENT.md) for what exists,
what remains and actual test evidence. Earlier planning/baseline statements below
are historical and do not describe the newly developed code as deployed.

## Baseline and evidence

The owner subsequently reported PR #28 deployed, reviewed commit
`b706e5034875529d74d26c10d72064c118165c9b`, merge
`d92408c5545e9fa89140061595e1a6d8b8e52ca4`. The approved
[fifth-batch clarification](OWNER_EDITS_BATCH_5.md) updates customer verification,
recovery wording and quantity/estimate presentation; carry those rules forward
with [shared workflow standards](SHARED_WORKFLOW_STANDARDS.md). Fifth-batch
implementation does not authorize or start the next-phase integrations below.


The owner reported successful deployment of PR #27. Its merge commit is
`a605aef5d7c43bd42852ea132937e9277a5c1b53`; the reviewed deployment ZIP is pinned
to `01d5bd58a401b4e6ea2beb9d4d8cbde59c6a597f`. The PR included the final reviewed
code and passing GitHub PostgreSQL 17/native Windows checks. All 407 tests passed
locally on PostgreSQL 16.2. This is owner-reported deployment evidence, not a new
Droplet inspection or blanket acceptance of every scenario.

The shared functional site is `https://staging.monkeydoplay.com`, with separate
staff authentication at `/staff/`. The baseline now includes the third batch's
combined automatic filters/date controls, word/partial typo matching, School
customers, backend-only dates, custom session preview/conflicts/blocks, explicit
reopening, actual schedule coverage, and the revised public layout, item-only
estimate and email recovery. It also retains editable versioned membership drafts,
linked IDs/latest-details history, customer referral ownership and Motzei Shabbos.
Homepage design proposals were excluded: its deployed About/play design remains.

These are pending test reservations and inactive membership drafts. Confirmed
visits, saved cards, electronic waivers, actual payment collection, active
membership benefits, durable workers and booking/member emails remain unfinished.
Account-email delivery through Resend and sender-domain verification were
owner-confirmed during setup; customer communications are a different remaining
integration. No new integration is claimed by this documentation update.

## Material findings

1. **Move integrations earlier.** The original development/reconstruction roadmaps
   placed Banquest, R2, Resend and durable jobs after most business workflows. Card
   setup, saved waiver evidence, reliable operations and confirmations are
   prerequisites for completing the next booking workflow. Build and verify
   these together with it, rather than leaving integration until the end.
2. **Build on the deployed foundation.** Several older status/setup sections
   described public booking as disabled, staging as not deployed, the
   shared-site cutover as pending, and all external email as unconfigured.
   Historical checkpoint evidence should stay intact, with a clearly identified
   current summary and completed setup steps distinguished from remaining work.
3. **Supervised Play belongs with ordinary booking.** Its pending reservation,
   pricing, mode/capacity and cutoff checks already exist. Complete its waiver,
   confirmation, arrival and payment behavior alongside ordinary play; do not
   postpone it with club enrollment or rebuild it as a separate program.
4. **Draft editing is not paid-membership editing.** Draft revisions can change
   planned values without moving money or used benefits. Active memberships
   need the approved sale/addition/renewal/conversion/cancellation and correction
   actions, preserving accepted financial and usage history. The existing staff
   and owner permission matrix still applies; the draft editor does not grant
   extra active-membership financial powers.
5. **Operational work cannot all wait until handoff.** Workers, provider-event
   handling, persistent alerts, private storage, retention and recoverable
   backups are dependencies of the workflows that introduce them. Final restore
   evidence, monitoring, exports, accessibility and training still need their
   own acceptance before launch.
6. **The existing mail transport is too narrow for the full workflow.**
   `core/test_email.py` supports controlled account mail, requires allowlisted
   recipients and rejects attachments. The approved customer staging flow
   permits tester-entered recipient addresses and requires conditional unsigned
   waiver-PDF attachments. Add the appropriate transport and delivery-record
   behavior while retaining the TEST subject/banner, staging links and account
   security protections. Do not treat the current adapter as complete customer
   communications infrastructure.

## Accepted remaining order and proposed technical increments

The owner accepted the stage order. The subdivisions below are implementation
increments within those stages, not separate websites or production launches.
They can be reviewed and deployed as useful staging increments.

| Order | Work | What becomes testable |
| --- | --- | --- |
| 0 | Review the owner's current test findings; correct defects affecting shared rules; reconcile the current status and roadmap. | A reliable baseline with known remaining issues. Testing can continue while independent design/integration investigation proceeds. |
| 1A | Payment-operation/tender records with reportable line/tax/fee allocations and linked adjustment dates, durable jobs and message outbox, Banquest sandbox adapter, secure provider-controlled card setup, consent and method lifecycle, webhook/reconciliation handling and permissions. | Both card-payment setup and alternate-tender backup-card setup, plus explicit sandbox payment operations, including failure, timeout, replay and duplicate handling. No live payments. |
| 1B | Approved waiver text/version and signing evidence, private test R2 storage, coverage/expiry, shared-parent links, paper fallback, staff viewing and retention. Develop alongside 1A where independent. | Actual saved electronic evidence and correct coverage decisions, rather than the preserved unsigned prototype. |
| 1C | Complete ordinary and supervised public/staff booking, confirmations, customer email correction/resend, arrival review, actual collection, split tenders, cancellation/no-show and partial-arrival fees, owner comped/custom/exclusive booking behavior. | An end-to-end test visit: reserve, complete required setup, receive an accurate email, review attendance/coverage, explicitly charge or record payment, and inspect history. |
| 2 | Active membership purchase, accepted terms, monthly/prepaid collection, installments, benefit reservation/usage, renewal/addition, owner exceptions, conversion and customer credit. | Memberships actually affect bookings, including member information/popup and adjusted pricing at the appropriate booking step; failures, calendar boundaries, mixed benefits and conversion credit can be tested. Preserve existing calendar/price work and the shared filters/layout conventions. |
| 3 | Party/group operational workflows, in-person physical gift-card sales/redemption, standalone socks sales, and backend club enrollment/participants/attendance. Reuse shared payments, waiver and email infrastructure. | The remaining business workflows. Club marketing stays disabled for initial launch unless the owner enables it. Building backend capability must not enable marketing automatically. |
| Throughout, then final acceptance | Encrypted offsite backup/restore work alongside persistent integrations; security/log retention and resource checks; complete exports/printing, monitoring, browser/accessibility checks, owner training and launch readiness. | Demonstrated recovery and daily operation, not merely a running process. Production remains a separate approval. |

Phase 1 means **ordinary visit card setup online, collection after staff arrival
review**, not charging the admission when the customer books. Include socks
selected with that booking in the reviewed arrival balance. Membership and club
purchase timing remain their separately approved rules.

The first complete booking phase should cover the supported ordinary tender
choices and the required backup-card rules, including manual physical gift-card
verification. It need not invent a digital gift-card balance system. Standalone
gift-card sales and later customer-credit consumption belong to their dependent
increments. Shared ledger design must accommodate them from the start.

The owner allows accountant income/tax/refund report screens to follow launch.
[Financial source-data requirements](ACCOUNTANT_REPORTING_FOUNDATION.md) belong
in stage 1A before real receipts: preserve original sale/tax/fee allocations,
actual tenders and dates, linked refunds/voids/credits/conversions and safe
provider/settlement references. Estimates and credit reallocations are not new
cash receipts. Keep tax, customer fee, provider cost and deposit separate. Final
report layout/accounting presentation may wait without delaying the required
source-data capture. Existing operational exports/printing remain in their
previously approved acceptance scope.


## Both card paths belong to the next stage

The earlier phrase backup-card setup was incomplete shorthand, not a requirement
to build only alternate-payment bookings. Build and test both customer paths:

| Customer choice | At online booking | At staff arrival review |
| --- | --- | --- |
| Credit card | Secure provider-controlled card entry or approved saved-method use, applicable consent, itemized final fee/tax estimate and waiver setup; save the method, not an admission charge | Staff review actual attendees/socks/coverage and explicitly confirm arrival and charge the final reviewed amount |
| Cash/check/Zelle or supported alternate tender | Record intended method and required details (including Zelle sender name); secure backup-card setup/consent; quote the selected tender without charging or adding a card fee solely because a backup exists | Staff verify/record actual tender, or explicitly choose No alternate payment received — charge card on file; a card-funded amount then uses applicable fee/tax calculations |

A credit-card booking does not require a second extra backup card. Its saved card
serves the applicable booking/cancellation obligations. No ordinary online
admission charge, issuer verification hold or automatic retry is introduced.
Booking-only versus optional reusable methods, disposal/dependency rules and
card replacement remain as approved in PAYMENTS.md. Owner-comped $0 bookings are
the approved no-required-card exception; waivers still apply. Physical gift-card
verification does not create a digital gift-card ledger. Test both routes through
confirmation, arrival, payment success/failure and cancellation/no-show.

Public Session Details keeps its low admission/adult/sock subtotal, excluding
card fee and tax. Final Payment Details contains the complete estimate for the
selected intended method; arrival confirms actual tender and any revised total.
Do not show a card fee for a cash booking just because a backup card was saved.

## Shared experience and functionality must carry forward

[SHARED_WORKFLOW_STANDARDS.md](SHARED_WORKFLOW_STANDARDS.md) is the explicit
inheritance matrix and checklist for each future stage. It covers the improved
tables, compact combinable filters, date controls, customer pickers, word/typo
search, linked IDs/names, shorter form fields, navigation, customer cards,
readable history, current-only membership display, responsive layouts and
permissions as well as shared business rules.

For memberships, use the established list/detail/edit experience and #M IDs;
for waivers, use the same visual and search/filter conventions with actual
signer/minor/coverage/version/validity information. Exact new filter choices and
the meaning/default of their date range are reviewed in the stage's screen plan.
Do not copy Bookings' today-to-next-year default blindly: it can hide a current
membership or valid waiver saved earlier. Do not collapse multiple parents'
current coverage into a single latest-customer waiver row. Customer-email
uniqueness does not make all waiver-signer emails globally unique.

All later booking-dependent features must reuse the existing eligibility,
closure/visibility/block/capacity checks, customer matching/contact rules,
historical pricing, date formatting and source-specific reopening rules. Update
main requirements, domain/development guides, acceptance cases and current status
together in the relevant PR. Keep a per-change affected-page list and propose
unapproved extensions; do not defer consistency review until final launch.

Membership detection, the member-information popup and member-adjusted booking
prices are explicitly for the active-membership stage. They are not being added
in the upcoming ordinary/supervised stage. Homepage redesign stays deferred;
clubs stay hidden until owner-enabled.

## Draft editing versus purchased-membership changes

A draft is a saved plan. Editing its type, places, dates or billing produces a
new saved version; no payment or benefit has occurred. Current draft editing and
its familiar screens remain useful.

A purchased membership has obligations and history. For example, one paid
Subscription place may already have used its two free visits this month. Simply
changing the original purchase to two places or erasing its first month would
make the payments, visits and remaining installments inconsistent. Instead, show
the current details and use the approved add-place purchase, renewal, correction
or owner exception with a clear effective date and financial/benefit impact.
Preserve what was already paid/used, record adjustments and show readable history.

This does not remove editing or make every operation owner-only. Staff retain
approved ordinary sale/renew/add, method changes and permitted corrections;
refunds, complimentary/exceptional terms, consolidation and nonpurchase benefit
adjustments remain owner-only. The same membership ID remains after a correction;
versions stay inside history, not separate routine table rows. A genuinely new
purchase/addition is its own approved cohort/record. Do not convert a test draft
to a paid membership automatically.

Payment and communications rules remain settled: no card verification holds, no
automatic payment retries, no appointment reminders, no automatic renewal beyond
the purchased membership term, and no successful installment receipt emails.
Unknown provider outcomes require reconciliation before another charge. An
installment due under an accepted fixed term is different from renewing that
term. Customer credit and physical gift-card balances remain distinct.

## Data and deployment implications

- The owner chose **new reservations for the integrated workflow**, preserving
  all earlier records/history, including cancelled test bookings. Plan a compact **Old test booking** badge on staff
  lists/detail/history and an applicable old/new workflow filter. Capture stable
  workflow provenance in the reviewed migration; do not derive old/new from the
  appointment date or repeatedly relabel every record on each deployment.
  Preserve IDs, statuses, quotes and capacity; old pending-test tools remain.
  No automatic setup completion, charges, signatures, emails or deletions.
  This classification is planned, not implemented by this documentation change.
- Future stages require additional schema, provider settings and worker
  deployment work. The installed `-ApplyReviewedBatchThree` option is closed to
  reviewed migration 0026 from baseline 0025. Its compatibility guard refuses old
  code that would ignore new reservation restrictions. It is not a general
  future-migration option. Prepare each release's reviewed plan and recovery,
  including external operations and worker pause/resume.
- Preserve the requested browser-downloaded ZIP followed by one PowerShell
  command for unpack/install/deploy. Avoid the slow PowerShell download path;
  do not work around certificate failures by disabling TLS verification.
- Investigate a smaller runtime release bundle that omits historical review
  galleries and archives while retaining required code, templates and assets.
  Preserve original images and review artifacts in GitHub. The Functional
  bundle checks currently depend on preserved design artifacts, so packaging
  and its checks must be changed together, with Design/recovery compatibility
  retained.
- The existing helper makes a protected same-server database checkpoint. That
  is useful deployment recovery, **not** the approved encrypted nightly R2
  backup, retention and monthly isolated-restore system. A local restore test
  is also not evidence that the hosted disaster-recovery system is operational.
- Recheck the existing Droplet's resources before adding workers, signature
  rendering and backup jobs. The earlier 1.9 GiB memory snapshot is not a
  current load test. A necessary appropriately sized resize was preauthorized;
  additional paid services still require cost review/approval.
- Plan release compatibility, worker pause/resume, least-privilege runtime
  access, provider callback routing through the staging gate, and interrupted
  recovery. A code rollback cannot undo a completed payment, sent message or
  database migration.

## Documentation synchronization in this update

The current summaries and remaining order are reconciled across DEVELOPMENT.md,
BUILD_STATUS.md, main requirements, payment/membership/waiver guides, customer
booking and staff booking notes, email/security/VPS setup notes and the staged
acceptance plan. RECONSTRUCTION.md preserves its original historical roadmap
with a successor reference. Historical test counts and unperformed statements
are kept labelled as checkpoint history, not presented as today's hosted state.
The shared matrix supplies each future PR's affected-page and acceptance checklist.
No application regression suite is required or claimed for this documentation-only
update; link/scope/consistency checks are the relevant verification.

## Decisions and outstanding inputs

The owner settled both planning questions: complete ordinary/supervised booking
first, then active memberships; test the new completion flow on new reservations
and identify the older workflow clearly. Both card payment and alternate-tender
backup-card routes are included. No further business clarification is needed to
record this plan. Next-phase application development still requires the owner's
go-ahead; technical provider/backup investigation belongs to that authorized stage.

### Existing accounting inputs, not blockers to the ordinary sandbox phase

- Production sales-tax/UEZ rate: still needed before live billing. Continue the
  approved 6.6% staging rate for sandbox work; never silently promote it.
- Retained-fee tax is now resolved by the accountant answer supplied November 19,
  2026: reverse that tax when the admission payment is applied to the nontaxable
  membership; otherwise retain it. The original processing fee is nonrefundable.
  The supplied $16.47 transaction leaves $16.02 applicable to membership after
  retaining $0.45 and reversing $0.99 admission tax plus $0.03 fee tax. Preserve
  separate audit/reversal entries and existing credit/refund rules. See
  [payment requirements](PAYMENTS.md). This is a membership-stage acceptance
  criterion, not a remaining question or an implemented payment feature.

Banquest sandbox processor/3DS behavior, durable token and deletion semantics,
idempotency/reconciliation, proportional cent allocation and the protected
backup-restore runner are developer/provider investigation work. They are not
new requests to choose a payment provider, supply all email wording, change
waiver policy, buy a second website or paste existing credentials into chat.

## Review sources

Reviewed the current main requirements, reconstruction/build sequence, open
decisions, payment rules, membership rules, program rules, email templates,
hosting/storage/backup plan, account security guide, staging acceptance plan,
relevant booking/customer/scheduling/membership development notes, and the
second- and third-batch request/response/final-review records, the third-batch
release handoff, shared components and the owner’s latest planning answers. The
prior review compared booking/membership models, edit guards, routes and the
staging email adapter; this follow-up reconciles their documented boundaries.
The earlier Word documents were reconciled through their repository request
matrices and approved conversation clarifications; this review did not freshly
extract the private Word attachments. No new provider or hosted acceptance claim
is made.


## Readiness recheck before the next stage — November 19, 2026

The owner asked whether any other preparation is needed and clarified that the
accountant summary should use actual receipts, refunds, tax and remaining funds.
Internal original-price/discount detail supports reconciliation and correct
refund allocations; no extra report columns or new discount feature are needed.

No new owner business-rule decision was identified as necessary before coding
the already-agreed next scope. Technical preparation belongs to that authorized
work, not another owner approval checklist:
- Design actual payment/tender/refund records, safe operation identity, webhook
  deduplication and unknown-outcome reconciliation before making provider calls.
- Preserve private provider-controlled card fields, consent and booking-only
  versus retained-card lifecycle; plan signed provider callbacks through the
  private staging gate without opening staff routes.
- Carry the approved waiver text/coverage into private test R2 storage and verify
  booking-email delivery/attachments; do not ask again for new waiver wording or
  repeat the already-completed sender setup.
- Recheck host resources and plan workers, encrypted offsite backups/restore,
  migration compatibility and single-command deployment together. Code rollback
  cannot undo a charge, sent email or saved signing evidence.
- Keep old pending-test records separate from new integrated-flow reservations,
  preserving IDs/history. Exercise both card-payment and alternate/backup-card
  routes through arrival, cancellation, failure and recovery.

Sandbox keys, private storage credentials and callback configuration are required
for real integration testing, not to start local implementation. Provide exact
private setup steps then; do not ask for secrets in chat/GitHub. Production tax
rate and live configuration remain later launch inputs, not sandbox-development
blockers. Accountant report layout/recognition presentation may wait.
Next-phase application development still requires the owner's go-ahead.
