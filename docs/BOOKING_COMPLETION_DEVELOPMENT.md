# Ordinary and supervised booking completion — implementation status

Updated November 20, 2026. The owner authorized this entire stage and parallel
draft-PR work on November 19. Continue all independent development without
repeated go-ahead requests. PR #30 is **draft, not ready to merge/deploy** while
the two business branches below are unresolved. No email-question bridge exists;
questions stay in the chat. Never request actual provider/recovery secrets in
chat, documents or Git.

Owner acceptance is after staging deployment. Developer checks precede the ready
PR. Prepare the owner's **as-built test guide only after the stage is actually
built/tested**, followed by the final pinned browser ZIP/one PowerShell command.
This implementation log is not that guide.

## Baseline and retained rules

Owner-reported deployed PR #29: reviewed
`ff8a7ce0e366bd8757afb5e81670eefab7f97128`, merge
`7a475101808ba66d522f144ded6b5d5a7472fb29`. Retain the subsequent accountant/reporting
planning commits and all approved matching, filters, layouts, IDs/history,
permissions, scheduling and Motzei Shabbos behavior. The deferred homepage design
has not been reopened. No independent verification of the hosted deployment is
claimed here.

No ordinary admission/socks collection online and no issuer holds. A card is for
reviewed arrival collection or alternate-tender backup. Staff explicitly review
attendees, waivers and actual tender before collection. Unknown is not declined;
never automatically replay an uncertain financial POST. Production/DNS/live-payment
activation remains separately gated.

## Implemented locally

### Financial facts and secure card lifecycle

Exact-cent sale/line snapshots; operation identities; immutable postings/events,
provider observations and SQL guards; separate actual receipt/provider/settlement
and record dates; sandbox-only constraints and stable product/tax categories.
Estimates and invoice adjustments are not receipts. Retain actual partial receipts
when a card balance fails. Proportional split tender inputs are actual inclusive
amounts, with deterministic fee/tax allocation and no fee on non-card funds.

Provider-hosted SDK entry, transient nonce/expiry exchange, method ownership/safe
metadata verification, exact consent versions, stale-tab/flow isolation, retained
versus booking-only sources, replacement and eventual disposal. No PAN/CVV/expiry
stored by the application. A booking-only replacement preserves a prior future-use
choice. Existing obligations prevent premature deletion or charging a stale source.

Owner-only verification/import of an already completed provider refund/void, exact
original-payment/component limits and no second refund POST. Settlement refresh
adds observations without reposting money. External credits/reversals raise owner
attention instead of inventing tax allocations. No false new debt is inferred
from a recorded refund.

### Complete public/staff visit paths

Public family booking binds card/waiver consent atomically, uses a Waiver progress
step, queues one confirmation and shows its actual delivery state. Both selected
card and alternate-tender/backup paths save without collecting admission online.
Zelle selection collects sender information. Final totals include applicable fee
and tax; the live Session Details estimate excludes them as approved.

Staff setup/final confirmation, current-waiver selection, pending Single/Multiple
signing instructions, source replacement, actual arrival counts, waiver Yes/No,
capacity review and explicit price/tender confirmation. Cancellation/no-show fee
choice, pending partial-child $3 fees, no extra-adult cancellation fee, no double
partial/whole cancellation collection, owner-only complimentary $0 status and
waiver handling. Owner cancellation can reopen only its own blocks while
preserving independent closures. Today/customer arrival shortcuts are connected.

Actual cash/check/verified Zelle/physical gift-card recording and card fallback;
split failures preserve received funds; explicit balance-only recovery never
recharges the earlier cash portion. Follow-up plans are distinct from money and
attendance. Card balance forms do not treat manual receipt dates as provider dates.

Old bookings retain stable IDs/history and an Old test booking marker/filter; they
are not automatically upgraded, signed, charged or emailed. Memberships remain
saved test drafts; active benefits/purchases are the following stage.

### Waivers and customer mail

Faithful full approved legal text, unchecked acknowledgments, typed signer/legal
relationship/minors, version/hash, New York anniversaries/leap-year handling and
private R2 evidence verification. Signed files stay outside PG/DO/Git. Shared
parent pages expose only appointment context; signing/expiry follow rescheduling.
Staff search/paging/coverage/history/private retrieval and audited paper marking
are connected. Staff family typo/partial-phone search reuses the shared matching
rules. Two-year verified evidence deletion purges contact/IP/browser details and
keeps minimal legal signing/history facts.

Durable immutable message snapshots and separate TEST-marked Resend transport;
unsigned source PDF only when applicable; current-contact refresh, one-booking
explicit resends and no blind unknown-send replay. Completion-page email correction
is limited to the current completed booking session, preserves uniqueness/history
and avoids two queued confirmations to the corrected address. Resends reflect
actual payments/corrections and complimentary status rather than claiming no
payment was ever received.

Signed/deduplicated Resend/Svix delivery/bounce/complaint/failure facts, tagged
unknown-send reconciliation, owner alerts and protected message histories. Account
MFA/reset recipient restrictions are unchanged. No appointment reminders or
installment receipts are introduced. Actual provider integration remains to test.

### Jobs, backup and reviewed deployment

Leased bounded jobs, interrupted-operation classification, owner-reviewed safe
queue recovery and read-only provider removal checks. Unknown financial requests
cannot be replayed. Separate reviewed jobs/retention/backup service/timer units,
resource preflight and a dedicated backup OS/DB identity. Web configuration gets
Get-only backup access; backup write/delete credentials stay with its separate UID.

Streaming PostgreSQL dump directly into authenticated CMS AES-256-GCM encryption;
no plaintext archive on the app server; no private recovery key on DO/R2. Conditional
random-key upload, full read-back hash/size verification before retention, seven
nightly/twelve distinct monthly points, private owner downloads/integrity files,
monthly desktop reminder, failure/issue-review history and owner-reported isolated
restore checks. An unattended monthly restore runner/key-access arrangement has
**not** been configured. The isolated verifier never starts app workers or replaces
a real database. Recovery hold prevents a restored Ready job from being treated
as proof its charge/email was never sent.

Closed 0027–0047 upgrade after 0026, pinned migration/unit hashes, private checkpoint,
transactional additive changes/grants, HTTPS checks, default-off flags and
compatibility refusal for older code once integrated records exist. Preserve the
approved browser ZIP plus one PowerShell command path. Configuration and operating
boundaries are in [BOOKING_STAGING_OPERATIONS.md](BOOKING_STAGING_OPERATIONS.md).

## Current evidence

- Latest complete local PostgreSQL run: **578 tests passed**. Focused checks also
  cover real upgrade/rollback-on-grant-failure and permission/concurrency isolation.
- Desktop Open Play/cash and phone Supervised/card browser paths completed signup,
  waiver, SDK setup, confirmation and email correction with **synthetic external
  adapters only**, no browser errors. Twenty-two staff page checks at 1440/390px
  passed without horizontal page overflow or JavaScript errors.
- Real local authenticated-encryption round trip rejects wrong keys/tampering.
  A real encrypted dump of fictional PostgreSQL fixtures, including a recorded
  fictional cash receipt, restored under an isolated non-superuser CREATEDB role:
  **62 tables, migration 0047**, payment/posting integrity checks passed; temporary
  database, local role and test private key were removed.
- Previous pushed checkpoint passed GitHub PostgreSQL 17 and native Windows
  PowerShell wrapper checks. Latest operator changes are being checked separately.
- Ruff, formatting, migration drift and whitespace checks pass.

These are local developer results. No real Banquest charge, R2 upload, delivered
email, hosted schema change, installed worker/offsite backup or owner recovery-key
setup is claimed. Default-off configuration is not successful integration.

## Two pending business branches

1. Online bookings involving other parents: all coverage before confirmation,
   versus saving Waiver pending/sending the link and confirming after coverage.
   Existing requirements contain both directions; the question was sent in chat.
2. Positive owner ordinary/group special price: admissions-only with socks separate,
   versus the entire pretax booking subtotal including socks. This determines later
   sock edits and taxable allocations. The separate fully complimentary $0 rule is
   clear and implemented.

Do not infer answers or label those branches complete. After clarification,
finish them, verify the full stage, update the ready PR and only then create the
owner test guide/release ZIP/command. Private sandbox/provider configuration and
actual hosted acceptance are still needed; never replace missing inputs with
real customer records, invented email delivery or claims of production readiness.
