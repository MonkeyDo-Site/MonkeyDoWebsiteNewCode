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
- PaymentMethod stores private provider references and safe brand/last-four
  metadata, not PAN/CVV or expiry. Public hosted-card setup/lifecycle is still
  being connected; model existence is not completed consent/tokenization.
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

Remaining in this increment: public/staff secure card-setup binding/consent and
method lifecycle, attention/history screens and alerts, operator/worker setup,
reviewed schema/grants/compatibility/recovery handoff and acceptance tests.
Migrations 0027/0028 are newly introduced and not authorized by the older closed
0026 deployment option. Keep the PR draft until its reviewed deployment plan is
complete. Existing staging configuration is not changed by local implementation.

Validation: 45 targeted payment/adapter/callback/historical-upgrade checks passed,
including provider timestamps, actor revocation and malformed signed events.
An earlier full run reached 470 tests and exposed two historical-upgrade test
assumptions about the old schema; tests now use their frozen release graphs
without weakening the production migration guards. A full rerun is next. Record final counts and
GitHub results in the PR. No real provider credential/transaction or hosted worker
claim is made. Do not enable the flag until its setup/acceptance is ready.

## Increment 2 — waivers and private evidence (not started)

Faithful approved/versioned text and electronic consent, signer/minor evidence,
coverage/expiry and shared/arrival links, private R2 storage/access, paper fallback,
signing notifications, retention and corresponding failure/recovery checks.
No signed file in Git, application database, public folder or duplicate DO store.

## Increment 3 — complete end-to-end booking (not started)

Connect customer/staff card and waiver setup to completion, actual confirmation
emails and current-email correction/resend, arrival review/collection and split
payments, actual attendance versus payment state, cancellation/no-show/partial
arrival and approved comped/override behavior. Carry worker/backups/resource and
safe deployment checks throughout. Preserve all older booking records/history.

Only after the stage and developer checks are complete, prepare the as-built owner
guide and final handoff. Provider-backed sandbox tests require private Banquest/R2
configuration at that point; mocks are not presented as successful integration.
