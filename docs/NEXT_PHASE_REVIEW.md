# Review of the remaining development stages

Review date: November 16, 2026.

**Status: proposal for owner review, not authorization to develop the next phase.**
No application code, business requirements, database, provider configuration or
hosted service was changed during this review. The earlier deployment-download
preference notes in DEPLOYMENT_COMMAND.md and DECISION_LOG.md are separate work.

## Baseline and evidence

The owner reported successful deployment after PR #26. The merged commit is
`34a77c4d7c13872ef80ed837eccfc2973bbb89c5`; its tree matches the reviewed local
release. The owner's deployment output reports that reviewed database updates
and deployment verification passed. This is operator-reported deployment
evidence, not a new remote inspection or completed owner acceptance test.

The shared functional site remains `https://staging.monkeydoplay.com`, with
separate staff authentication at `/staff/`. Design updates and booking tests use
this same site. Historical design snapshots are retained as artifacts.

The deployed baseline includes customer and staff pending test reservations,
saved estimates, capacity protection, booking edits/cancellation, customer
matching/contact history, owner scheduling and bulk weekly-default editing,
Today/Bookings tables and filters, editable versioned membership drafts,
customer-profile referral information, and Motzei Shabbos naming/public-session
support. It does **not** complete confirmed visits, payment collection, saved
cards, electronic waivers or active membership benefits.

Owner account-email delivery through Resend was configured and its inbox receipt
was owner-confirmed during earlier setup. Booking/member emails and their
delivery tracking remain unfinished. The release had 376 passing PostgreSQL
tests before merge; that is not end-to-end acceptance of unfinished workflows.
The owner is now testing the deployed batch.

## Material findings

1. **Move integrations earlier.** DEVELOPMENT.md and the reconstruction roadmap
   put Banquest, R2, Resend and durable jobs after most business workflows. Card
   setup, saved waiver evidence, reliable operations and confirmations are
   prerequisites for completing the next booking workflow. Build and verify
   these together with it, rather than leaving integration until the end.
2. **Build on the deployed foundation.** Several older status/setup sections
   still describe public booking as disabled, staging as not deployed, the
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

## Recommended remaining sequence

These are proposed development increments, not separate websites or production
launches. They can be reviewed and deployed as useful staging increments.

| Order | Work | What becomes testable |
| --- | --- | --- |
| 0 | Review the owner's current test findings; correct defects affecting shared rules; reconcile the current status and roadmap. | A reliable baseline with known remaining issues. Testing can continue while independent design/integration investigation proceeds. |
| 1A | Payment-operation/tender records, durable jobs and message outbox, Banquest sandbox adapter, secure provider-controlled card setup, consent and method lifecycle, webhook/reconciliation handling and permissions. | Durable backup-card setup and explicit sandbox payment operations, including failure, timeout, replay and duplicate handling. No live payments. |
| 1B | Approved waiver text/version and signing evidence, private test R2 storage, coverage/expiry, shared-parent links, paper fallback, staff viewing and retention. Develop alongside 1A where independent. | Actual saved electronic evidence and correct coverage decisions, rather than the preserved unsigned prototype. |
| 1C | Complete ordinary and supervised public/staff booking, confirmations, customer email correction/resend, arrival review, actual collection, split tenders, cancellation/no-show and partial-arrival fees, owner comped/custom/exclusive booking behavior. | An end-to-end test visit: reserve, complete required setup, receive an accurate email, review attendance/coverage, explicitly charge or record payment, and inspect history. |
| 2 | Active membership purchase, accepted terms, monthly/prepaid collection, installments, benefit reservation/usage, renewal/addition, owner exceptions, conversion and customer credit. | Memberships actually affect bookings; failures, calendar boundaries, mixed benefits and conversion credit can be tested. Preserve the existing calendar/price work rather than replacing it with gateway defaults. |
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

## Changes that must carry into later pages and workflows

| Established behavior | Required future application |
| --- | --- |
| Linked booking IDs and #M membership IDs; one current membership row; earlier versions inside history | Keep these conventions in sales, active-membership views, payments, customer cards, exports and history. Do not introduce a new customer-derived numbering scheme or a new membership for every edit. If a draft is explicitly turned into a purchase, retain its displayed identity and original history. |
| Current-email uniqueness, historical-only warnings/notices, normalized phone and close-name matching | Reuse customer identification in membership/program/party assistance. Do not create competing customer records or apply a customer-email uniqueness rule to unrelated waiver signers. Preserve public privacy and staff profile-link permissions. |
| Referral belongs to the customer | Ask once for a new customer and edit on the profile. Do not reintroduce it on each booking, renewal or payment screen, or infer answers from older bookings. |
| Latest booking edit form, itemized estimate and payment-method reminder | Keep one coherent editing workflow as real payments and benefits are added. An estimate or Save is not authorization to charge; already collected money cannot be silently rewritten by changing expected payment method. |
| Accepted historical pricing and before/after audit | Preserve original policy, actual tender and used-benefit history. Revisions and financial adjustments must be explicit; future price changes must not rewrite accepted transactions. |
| Owner one/two-month membership exceptions | Render accurate accepted terms, calendar, installments and confirmation wording for either product and billing choice; do not show an unconditional three-month commitment to an exception customer. Ordinary public/staff minimums remain unchanged. |
| Closed default hides its linked slot; closed dated public session shows Not Available | Apply the same shared eligibility checks during booking finalization, rescheduling, membership benefit use and party/program blocking. Do not silently move booked sessions or automatically generate missing dates. |
| Add booking on Today; session configuration only in Owner Scheduling | Retain these boundaries while adding arrival, active memberships and programs. Expand staff capabilities only according to the approved permission matrix. |
| Motzei Shabbos display and owner-designated public sessions | Reuse the shared New York business-date formatter in new emails, waivers, rosters, histories, printed output and human-readable exports. Keep numeric/ISO dates unchanged; add no sunset/evening rule. |
| Four current public progress steps, with a waiver step when signing is implemented | Extend the flow for actual waiver work without bringing back an extra Review step. Keep expected-method selection in Session Details, itemization in Payment Details and progress out of staff screens. |
| Approved completion heading and Book another play session button | Retain the wording while making the explanatory message reflect actual saved setup, confirmation and email state. Never say payment was received or email sent merely because a screen rendered. Keep conspicuous staging-test notices. |
| Homepage design and club visibility | Reuse the approved components and current public copy. Leave clubs hidden for initial launch; parties remain public marketing while their backend workflow is built. |

Payment and communications rules remain settled: no card verification holds, no
automatic payment retries, no appointment reminders, no automatic renewal beyond
the purchased membership term, and no successful installment receipt emails.
Unknown provider outcomes require reconciliation before another charge. An
installment due under an accepted fixed term is different from renewing that
term. Customer credit and physical gift-card balances remain distinct.

## Data and deployment implications

- Existing pending bookings, customer profiles, quotes and membership drafts
  must survive future schema changes. Do not automatically turn old drafts into
  paid memberships, mark waivers signed, or generate charges/emails from old
  test records. Whether to offer an explicit completion path for old pending
  reservations is a review question below.
- Future stages require additional schema, provider settings and worker
  deployment work. The current `-ApplyReviewedBatchTwo` option is pinned to
  migrations 0023–0025; it is not permission or support for arbitrary future
  migrations. Prepare an explicitly reviewed update for each relevant release.
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

## Documentation and acceptance updates after agreement

Update DEVELOPMENT.md's current boundary and build sequence, BUILD_STATUS.md's
current summary, and the reconstruction roadmap's successor reference. Mark old
checkpoint descriptions as historical without rewriting their original test
evidence. Reconcile ACCOUNT_SECURITY.md, CUSTOMER_BOOKING_DEVELOPMENT.md and the
VPS/setup documents with the completed shared-site/Resend setup.

Carry the approved behavior into MONKEYDO_REQUIREMENTS.md, PAYMENTS.md,
MEMBERSHIPS.md, PROGRAMS.md, EMAIL_TEMPLATES.md and the relevant development
guides as each stage is specified. In particular, distinguish draft editing
from active financial corrections and finish the already-required delivery
variants, short-term exception terms and customer-facing date formatting.

STAGING_TEST_PLAN.md should show which cases are currently testable, blocked or
actually accepted, with build-specific owner evidence. Old blanket statements
that all hosted/provider steps are unperformed need a current summary; historical
local test counts must not be presented as current end-to-end coverage. Add
integration regressions for the latest shared UI/customer/scheduling behavior,
plus actual Banquest outcomes, waiver persistence/authorization, email delivery,
partial payment, worker recovery and existing-record preservation. No full
application test suite was rerun for this documentation-only review.

## Questions and outstanding inputs

### Decisions useful before the next phase

1. **Priority:** does completing ordinary and supervised booking first, including
   card setup, waivers, confirmation emails and staff arrival/payment handling,
   match the owner's priority, with active memberships next? This is the
   recommended order; it does not require a production launch between stages.
2. **Existing test reservations:** should the new completion workflow support
   explicitly finishing setup on an existing pending test reservation, or can
   acceptance use new reservations while the older records remain unchanged?
   Recommend new reservations initially, retaining existing records/history and
   their existing test-management tools. Neither option permits automatic
   conversion, charges or emails.

### Existing accounting inputs, not blockers to the ordinary sandbox phase

- Production sales-tax/UEZ rate: still needed before live billing. Continue the
  approved 6.6% staging rate for sandbox work; never silently promote it.
- On an already-paid admission converted to membership, must the tax on the
  retained original processing fee stay or be reversed? Example: retain the
  original $0.45 fee; the unresolved amount is its $0.03 tax. Obtain the
  owner/accountant decision before implementing/accepting that conversion case.

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
second-batch request/response/final-review records. Compared these with current
booking/membership models, edit guards, routes and the staging email adapter.
The earlier Word documents were reconciled through their repository request
matrices and approved conversation clarifications; this review did not freshly
extract the private Word attachments. No new provider or hosted acceptance claim
is made.
