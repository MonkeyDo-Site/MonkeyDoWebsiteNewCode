# Ordinary and supervised booking completion — implementation status

Updated November 19, 2026. The owner authorized this entire stage and parallel
draft-PR work on November 19. Continue all independent development without
repeated go-ahead requests. PR #30 contains the complete local implementation;
all business questions for this stage have been answered. Final GitHub checks
must pass before merge. No email-question bridge exists;
questions stay in the chat. Never request actual provider/recovery secrets in
chat, documents or Git.

Owner acceptance is after staging deployment. The as-built testing guide was
prepared after the full local stage and developer checks: [Markdown](BOOKING_COMPLETION_TEST_GUIDE.md)
and [Word](BOOKING_COMPLETION_TEST_GUIDE.docx). The [release handoff](BOOKING_COMPLETION_RELEASE.md)
uses a pinned browser ZIP and one PowerShell block. This implementation log is
not the owner testing guide.

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
Zelle selection collects sender information. Online groups can reserve places
immediately with Waiver pending, a shared signing link and unsigned PDF; complete
coverage is required before play and places do not automatically expire for
pending waivers. Final totals include applicable fee and tax; the live Session Details estimate excludes them as approved.

Staff setup/final confirmation, current-waiver selection, pending Single/Multiple
signing instructions, source replacement, actual arrival counts, waiver Yes/No,
capacity review and explicit price/tender confirmation. Cancellation/no-show fee
choice, pending partial-child $3 fees, no extra-adult cancellation fee, no double
partial/whole cancellation collection, owner-only special admissions totals and
complimentary $0 status and waiver handling. Special prices cover admissions only, with socks separate. Count
changes retain that total, prompt optional owner adjustment and add no automatic
partial-cancellation fee. Staff count changes notify the owner Dashboard.
Owner cancellation can reopen only its own blocks while preserving independent
closures. Today/customer arrival shortcuts are connected.

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
transactional additive changes/grants, database defaults allowing legacy inserts
during recovery, HTTPS checks, default-off flags and
compatibility refusal for older code once integrated records exist. Preserve the
approved browser ZIP plus one PowerShell command path. Configuration and operating
boundaries are in [BOOKING_STAGING_OPERATIONS.md](BOOKING_STAGING_OPERATIONS.md).

## Current evidence

- Latest complete local PostgreSQL run: **588 tests passed**. Focused checks also
  cover real upgrade/rollback-on-grant-failure and permission/concurrency isolation.
- Desktop Open Play/cash and phone Supervised/card browser paths completed signup,
  waiver, SDK setup, confirmation and email correction with **synthetic external
  adapters only**, no browser errors. Twenty-two staff page checks at 1440/390px
  passed without horizontal page overflow or JavaScript errors. Additional desktop/phone
  group bookings, independent parent signing, owner price adjustment previews and
  restricted staff price prompts passed with synthetic external adapters.
- Real local authenticated-encryption round trip rejects wrong keys/tampering.
  A real encrypted dump of fictional PostgreSQL fixtures, including a recorded
  fictional cash receipt, restored under an isolated non-superuser CREATEDB role:
  **62 tables, migration 0047**, payment/posting integrity checks passed; temporary
  database, local role and test private key were removed.
- The preceding pushed checkpoint passed GitHub PostgreSQL 17 and native Windows
  PowerShell wrapper checks; the final PR head must also pass those checks.
- Ruff, formatting, migration drift and whitespace checks pass.

These are local developer results. Separately, the setup operator executed protected
server setup and reported a Banquest sandbox read-only authentication check
(HTTP 200) and successful temporary-object R2 upload/read/deletion tests,
including backup read-only download and denied writing. See the
[credential checkpoint](BOOKING_STAGING_OPERATIONS.md#operator-executed-credential-setup-checkpoint).
Actual browser tokenization, signed-waiver persistence, payment processing,
booking delivery/webhook acceptance, hosted schema/worker activation and encrypted
offsite backup/recovery-key setup remain unverified. Default-off configuration
is not successful integration.

## Resolved business decisions and remaining operational inputs

The owner approved online groups reserving places immediately on final save,
receiving the shared parent link and unsigned PDF, and remaining Waiver pending
until coverage is reviewed. Everyone needs coverage before play. No automatic
waiver-pending capacity expiry is introduced.

An owner special price covers admissions only; socks stay separately priced.
Count changes keep that total unless the owner optionally adjusts it, with no
automatic partial-cancellation fee. Staff cannot adjust the price; count changes
notify the owner Dashboard. Full cancellation/no-show still requires its own
explicit charge/no-charge choice. Fully complimentary bookings remain distinct.

There are no remaining business questions for this stage. Private callback
configuration, owner recovery-key setup and actual hosted acceptance are still
needed; never replace missing
inputs with real customer records, invented email delivery or claims of production
readiness. The test guide and release handoff state which features remain disabled
until one-time callback activation or owner recovery-key setup is completed.
