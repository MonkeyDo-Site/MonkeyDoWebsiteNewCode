# Ordinary and supervised booking completion — authorized implementation

The owner authorized the whole next booking stage on November 19, 2026, including
all accepted planning/accountant/reporting clarifications. Build and update draft
PRs alongside implementation; continue unblocked work without repeated go-ahead.
No email-question bridge exists: collect material questions in the chat. Provider
keys are entered privately at integration-testing setup, never chat or Git.

Owner review occurs after deployment to staging. Developer automated and browser
checks still precede each ready PR. Prepare the owner-facing as-built test guide
**after the stage is actually built/tested**, with the final PR/ZIP/single-command
handoff; do not prepare a planned-feature guide or imply planned features exist.

## Baseline and retained decisions

Start from owner-reported deployed PR #29 (reviewed ff8a7ce0e366bd8757afb5e81670eefab7f97128,
merge 7a475101808ba66d522f144ded6b5d5a7472fb29), carrying the subsequent accountant
and financial-reporting planning commits. No independent hosted verification is
claimed by that owner report. Existing improved customer matching, layouts,
filters, IDs/history, privacy, scheduling and Motzei Shabbos wording remain.
No homepage design changes, active memberships, later business workflows or
accountant reporting UI are included in this booking stage.

[Remaining scope](NEXT_PHASE_REVIEW.md), [shared standards](SHARED_WORKFLOW_STANDARDS.md),
[payments](PAYMENTS.md), [reportable financial facts](ACCOUNTANT_REPORTING_FOUNDATION.md)
and [waivers](waivers/README.md) remain the acceptance sources. No ordinary booking
charge online, issuer verification holds or automatic financial retries. Both
credit-card and alternate-tender/backup-card flows are required.

## Increment 1 — payment foundation (in progress, draft only)

Implemented locally so far:
- Sandbox-only frozen sale/line records, operation identities and append-only
  financial postings/events/observations, with PostgreSQL/SQLite guards. Quote
  acceptance alone is not a receipt. Preserve actual receipt/settlement dates,
  historical customer label, stable product categories and allocated item/fee tax.
- Provider-hosted card setup now exchanges a transient nonce, verifies method
  ownership/safe metadata, persists exact consent text/version, binds to the
  verified booking flow, supports retained versus booking-only methods and
  discards abandoned setup methods. Public endpoints and an SDK component exist;
  they are not yet attached to the final completed-booking path.
- Staff payment lists/detail, customer history and Dashboard attention use linked
  IDs, safe last-four metadata, existing search/paging and owner-only read-only
  provider reconciliation. Queued operations recheck booking/method eligibility.
- Backend service boundaries for actual tender confirmation, linked refunds/voids,
  remaining-amount reservation, verified provider evidence and uncertain outcomes.
  Original/test bookings have a stable legacy workflow marker; new integration
  must not charge them or manufacture their completion/signatures/emails.
- Banquest sandbox v2 transport: fixed TLS host, exact-decimal JSON, bounded
  responses, no redirects or automatic retries, saved-source charges and separate
  read-only reconciliation. Contract tests use mocked responses only.
- Signed bounded webhook inbox with immutable hashed/allowlisted facts and event
  deduplication; callbacks trigger read-only reconciliation. Only the exact
  enabled POST callback bypasses the private staging gate; signature verification
  remains mandatory and staff routes remain protected.
- Durable leased DB jobs. Recovering a sending job marks its outcome unknown;
  it does not replay the financial POST. Blocked jobs require explicit review.

Remaining in this increment: complete customer/staff integration and card
replacement/recovery UI; finalize resolved-obligation disposal, attention
resolution/alerts, operator/worker setup and reviewed schema/grants/compatibility
handoff. Migrations 0027 onward are not allowed by the older closed 0026 helper.
Keep the PR draft until the complete stage and reviewed deployment are ready.
Existing staging configuration has not changed.

Validation checkpoint: all 514 tests passed locally on PostgreSQL, including the new public booking, paper-mark and message controls.
Sixteen focused card/setup/public checks also passed after adding read-only saved-card
ownership/expiry validation; malformed metadata is not mislabeled as expiry. Twelve browser checks across
1440px and 390px passed for payment/waiver lists/details and public/shared signing
forms, including no page overflow, unchecked consent and shared-page privacy.
Ruff check/format and migration drift checks pass. CI formatting caught two new
migration files; those were formatted and are being rechecked on GitHub. No real provider credentials, signed R2 upload, delivered
email, hosted worker or deployment is claimed. Features default off.

## Increment 2 — waivers and private evidence (in progress)

Implemented locally: faithful approved full text and explicit acknowledgments,
version hashes, typed signer/relationship/minor metadata, one-year New York
anniversaries including leap years, conditional private R2 object creation and
byte-hash verification, metadata-only database storage, shared-parent privacy and
rescheduling-aware next-day expiry, staff search/paging/detail/evidence access,
and two-year file deletion with retained metadata/audit. SQL guards protect
signed facts and earlier versions. Storage/transport checks use synthetic mocks.

Public coverage/reuse/new-minor decisions, audited/stale-protected staff paper
marking, linked booking/customer records, shared completion notifications and
owner read-only pending-evidence recovery are now implemented locally. Remaining:
arrival integration and real configured-R2 acceptance. An online group-booking clarification is pending: all coverage before
confirmation versus a pending booking/link before all parents finish.

## Increment 3 — complete end-to-end booking (in progress)

Implemented locally: completed public self/family booking now binds secure card
consent and waiver coverage atomically, adds the approved Waiver progress step,
queues one confirmation and displays actual queued/sent/unknown delivery state.
Both public card-payment and alternate-tender/backup-card paths save the method
without charging admission. Browser checks completed Open Play/cash and
Supervised Play/card flows through signing and receipt at 1440px/390px, using
synthetic external SDK/API/R2 adapters only, with no browser errors.

Also implemented: a durable message snapshot/outbox, separate TEST-marked
Resend customer transport supporting approved test recipients and the unsigned
source PDF, current-contact refresh before sending, explicit sent/failed/unknown
states, no blind interrupted-send replay, and approved booking/waiver/owner-alert
content. Staff message tables/history/resend, current-contact snapshots, explicit duplicate-safe
booking-only resends and Dashboard failure visibility are connected.

Remaining: staff secure card/setup and final confirmation; actual provider-backed
confirmation delivery and public email-correction controls; arrival review/collection,
split payments and actual attendance versus payment state; cancellation/no-show/partial
arrival and approved comped/override behavior. The separate completed-booking flag
defaults off, as do its integration dependencies. Carry worker/backups/resource and
safe deployment checks throughout. Preserve all older booking records/history.

Only after the stage and developer checks are complete, prepare the as-built owner
guide and final handoff. Provider-backed sandbox tests require private Banquest/R2
configuration at that point; mocks are not presented as successful integration.

## Current implementation checkpoint — November 20, 2026

The earlier remaining-work lists above are historical checkpoints, not a claim
that those screens are still absent. Since then, local development adds:

- Booking-bound staff card setup/final confirmation, pending waiver instructions,
  explicit source replacement and future-use removal. Replacements preserve a
  previous retained source when the new choice is booking-only.
- Staff arrival, cancellation and no-show review/confirm flows. Preview does not
  record attendance or money. Actual receipt confirmation, proportional split
  tender allocation and remaining-balance collection preserve received cash if a
  card balance fails. Uncertain requests cannot be automatically replayed.
- Pending $3 partial-child cancellation fees, actual counts/capacity review,
  owner-only complimentary $0 status and required waiver handling. Positive
  special-price allocation awaits the separately asked scope clarification.
- Actual Zelle sender information and manual receipt dates, separate from visit,
  entry, provider charge and settlement dates. Missing provider timestamps stay
  unknown. Invoice fee adjustments do not masquerade as receipts.
- Owner-only verification/import of an already completed provider refund/void,
  with original-payment/component checks and no financial POST. Settlement
  refresh appends observations without reposting a receipt; external corrections
  raise an owner review rather than inventing refund/tax allocations.
- Completion-page email correction scoped to the current completed booking
  session, existing email uniqueness/history rules and one booking confirmation.
  A queued older-address attempt is superseded without sending two current copies.
- Signed Resend/Svix delivery/bounce events, message history and owner alerts,
  including tagged reconciliation of a lost send response. Only bounded delivery
  facts are stored. Authentication email recipient restrictions are unchanged.
- Private authenticated CMS AES-256-GCM encryption of a streaming PostgreSQL
  dump before R2 upload; separate backup bucket/read credentials, verified
  ciphertext hash/size, seven nightly/twelve distinct monthly retention, owner
  downloads/restore-report UI and a protected isolated-workstation verification
  script. No recovery private key is configured on DigitalOcean or R2. An owner
  restore report is labeled as such, not an automatic successful restore.
- Two-year waiver-file removal now purges contact/IP/browser details only after
  remote deletion is verified; minimal legal signing/history facts remain.

Validation: 557 tests passed in the latest complete local PostgreSQL run. Subsequent
focused tests cover signed mail events and completion email correction (7), card
replacement (3), and external corrections/encryption/retention (20). The encryption
check actually decrypts local synthetic bytes and rejects a wrong key/tampering;
it is not a real R2 upload or full PostgreSQL restoration claim. Ruff and migration
checks are repeated as implementation continues.

Still required before a ready-to-merge/deploy claim: remaining business-branch
answers, integrated browser/regression checks, staff permission/deployment grants,
worker/retention installation and resource preflight, closed checksummed schema
upgrade/rollback compatibility, private provider configuration/acceptance and the
final owner guide (prepared only after development completes). The PR stays draft.
No hosted migration, source charge, email delivery or offsite recovery point has
been made by these local checks.
