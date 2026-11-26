# Staging build status

## Current: ninth review and tenth-document follow-up — draft PR #35

PR #34 is merged; the ninth source screenshots predate that deployment. PR #35 covers preserved staff arrival/card/signing flows, named waivers and audited discrepancy confirmation, non-card splits/card remainders, true processing/results, pricing fixes, compact backend notices/cards and booking comments. The tenth document combines gallery corrections with deployed-site issues and stays in this same PR. It adds verified email-profile recovery/confirmation, the approved clear profile-choice wording, linked child/minimum pricing, card-only cancellation/no-show fees (with existing Zelle reconciliation), payment/layout/copy corrections and immediate attendee guidance. See the [updated gallery](design-review/ninth-review/README.md), [ninth scope](NINTH_BATCH_REVIEW.md) and [tenth follow-up](TENTH_BATCH_REVIEW.md). Actual Banquest field rendering remains pending access to its tokenization host; gallery card fields/outcomes are simulated. All 688 local PostgreSQL tests and desktop/phone browser checks pass. Migration 0052 remains the only schema addition; no hosted migration or deployment has been performed. The owner now authorizes merge and deployment while deferring the cloud-settings/actual Banquest layout check. See [the as-built test guide](NINTH_TENTH_TEST_GUIDE.md) and its Word copy; the pinned ZIP and one PowerShell block accompany the merged release. Cash change is deferred, and active membership stage work remains on hold.


## Seventh review — draft PR #33 and screenshot review

PR #32 is merged and the owner reports it deployed. PR #33 implements the seventh feedback batch; it is a draft during owner screenshot review. See [scope](SEVENTH_BATCH_REVIEW.md) and [arrival/booking/edit screenshots](design-review/seventh-review/README.md). New additive schema 0048–0051 requires the checksum-pinned reviewed booking upgrade with a private checkpoint and restricted runtime grants; no hosted migration is performed by the agent. Integration flags, credentials, backups, homepage and active memberships are unchanged. The owner will ask Banquest about automatic month-to-year focus. Final testing guide and deployment ZIP/one command follow completed implementation and review.


## Sixth review — PR #32 implemented, approved follow-up updates

Implements the complete sixth feedback batch and manual owner card retry. Previous PR #31 is merged; owner reports deployment and successful sandbox payment after Banquest's reset. This PR does not change live payment activation, schema, credentials, backup activation, homepage design or memberships. The owner approved the email design and all collected payment/waiver follow-up changes, with no further screenshots requested. 612 PostgreSQL tests pass. Final validation includes relationship-specific minor names, preserved signed history, and 12 desktop/phone browser interactions. See [scope](SIXTH_BATCH_REVIEW.md), [test guide](SIXTH_BATCH_TEST_GUIDE.md), [payment-page images](design-review/sixth-payment-review/README.md) and final PR check results before merging.


## November 20 staging collection fix

The operator reported PR #30 deployed from reviewed commit
`cd9bbfe2f3070e712cd7bde518c98924a34b3787` (merge
`6168d98fe0dae64b6928e936be06a168a420b126`). Sandbox card/waiver/booking-mail
configuration and signed callback routes were activated; backups remain disabled.
A new integrated booking and TEST confirmation succeeded, and the message showed
delivery reported by the provider. This is user-reported hosted evidence, not an
independent server inspection or blanket provider acceptance.

Final arrival confirmation then returned HTTP 500. The read-only diagnostic
showed no saved checkout, sale or payment operation for the reported booking.
A local non-admin role with the reviewed grants reproduced
`permission denied for table core_financialsale`: PostgreSQL row locking required
UPDATE permission on an append-only sale. The code-only patch replaces that lock
with a transaction-scoped per-sale advisory lock, retains booking-first ordering,
and limits correction row locks to the mutable operation. Financial facts retain
their existing UPDATE/DELETE prohibitions. No migration, grant, credential or
manual data cleanup is needed. See [fix details](PAYMENT_CONFIRMATION_FIX.md).

## Booking completion stage — implemented in PR #30

The local stage is complete: public/staff card/waiver/confirmation flows, held
online groups with Waiver pending, arrival/split and balance-only payment review,
owner special admissions/complimentary pricing, linked corrections, immutable
financial facts, private evidence retention, mail delivery/bounce history,
encrypted backup/isolated restore tooling and closed reviewed deployment.
**588 local PostgreSQL tests pass**, including actual upgrade, legacy-code insert
compatibility, rollback-on-grant-failure and permission/concurrency checks.
Desktop/phone synthetic-provider browser flows and isolated encrypted restore
checks pass. Final GitHub PostgreSQL 17/native Windows checks precede merge.

The operator reported successful Banquest sandbox read-only authentication and
R2 temporary-file/read-only restriction checks; the Resend domain is Verified.
No end-to-end hosted card, signature, collection or booking-delivery acceptance is
claimed. New integration flags remain disabled until callback/activation setup.
Backups remain disabled pending owner recovery-key setup and hosted restore
acceptance. No hosted schema or worker activation has been performed by the agent.

[As-built owner guide](BOOKING_COMPLETION_TEST_GUIDE.md) ·
[Word guide](BOOKING_COMPLETION_TEST_GUIDE.docx) ·
[Browser ZIP / one-block release](BOOKING_COMPLETION_RELEASE.md) ·
[Implementation evidence](BOOKING_COMPLETION_DEVELOPMENT.md) ·
[Private operator setup](BOOKING_STAGING_OPERATIONS.md).

## Subsequent planning: accountant tax clarification and future reports

Owner supplied the retained-processing-fee tax answer; payment/membership rules
now document reversal when the admission payment is applied to membership.
Accountant report screens may be built after launch. The next payment foundation
must capture [reportable financial source facts](ACCOUNTANT_REPORTING_FOUNDATION.md)
from the start; existing price estimates are not real receipts. These updates
change documentation only. No ledger, report, payment operation, migration or
provider configuration was implemented by this planning review.


## Fifth batch — implementation and PR authorized

The owner reported PR #28 deployed to staging. Reviewed commit
`b706e5034875529d74d26c10d72064c118165c9b` merged as
`d92408c5545e9fa89140061595e1a6d8b8e52ca4`; its GitHub PostgreSQL 17/native
Windows checks passed. This is owner-reported deployment, not a fresh host check.

The fifth batch refines public quantity labels/input-aligned estimate, entry-path
introductions, inline retry actions and linked duplicate-email recovery; it extends
guarded Name/Email verification to No/silent and retry current-phone matches.
441 local PostgreSQL 16.2 tests passed. Chromium passed at 1440/1024/390/320px
without screenshots, overflow or page JS errors. The routine PowerShell handoff
passed with transport mocked. No schema or provider change is required.
No review screenshots were requested; owner acceptance follows deployment.
[Complete scope](OWNER_EDITS_BATCH_5.md) ·
[Browser ZIP and routine command](OWNER_FEEDBACK_BATCH_FIVE_RELEASE.md).

## Fourth batch — archived local implementation and image-review evidence

The full fourth batch is implemented locally, with the owner-authorized narrower
booking form/play controls, scoped matching branches and owner conflict notices,
compact customer search, shared four-list pagination and immediate session
filtering. **428 tests passed locally on PostgreSQL 16.2.** Chromium checks passed
at 1440/390px plus 320px; eight JPGs show only the customer booking page as
requested. Staff/matching flows were exercised without publishing extra screen
images. The routine browser-ZIP PowerShell handoff passed with transport mocked;
GitHub PostgreSQL 17/native Windows CI is separate release evidence.

The subsequent booking-image correction left-aligns the panel, places all four
quantity fields left and estimate/payment right, places Your Group above the
play choices and separates age help from quantity labels. The latest owner
correction removes Start again only from Session Details and widens the desktop
gap before the outside play cards to 120px. A further CSS-only revision
right-aligns Continue and adds space above/below the play choices, moving
quantities and estimate down together. Refreshed browser checks and 1440/390px
captures plus 320px checks cover this CSS-only revision. The prior template
follow-up passed 41 affected tests; the existing full-suite result above precedes
these presentation revisions. GitHub rechecks the new head.

At this checkpoint the owner requested one draft PR updated during image review;
no hosted deployment or schema change had occurred yet. PR #27 below was the
hosted baseline. The later owner-reported PR #28 deployment is recorded above. No next-phase payment/waiver/active
membership integration or Old test booking classification has been built.
[Scope](OWNER_EDITS_BATCH_4.md) · [Images](design-review/owner-edits-batch-4/README.md) ·
[Routine deployment handoff](OWNER_FEEDBACK_BATCH_FOUR_RELEASE.md).

## Current deployed baseline — third owner-feedback batch

The owner reported PR #27 deployed after confirming the PR merge. The deployed
reviewed content is pinned to `01d5bd58a401b4e6ea2beb9d4d8cbde59c6a597f`, merged as
`a605aef5d7c43bd42852ea132937e9277a5c1b53`. GitHub PostgreSQL 17 and Windows
PowerShell checks passed; 407 tests passed locally on PostgreSQL 16.2. Hosted
completion is owner-reported, not an independent Droplet inspection or every
scenario's acceptance. The homepage retains its preceding approved About/play
design; third-batch homepage proposals were excluded.

Current functionality: protected shared staging and /staff, customer/staff pending
test reservations, pricing/edit/history, customer records/matching/contact rules,
School/type/search filters, owner weekly/date/custom scheduling and reservation
blocks, and editable inactive membership drafts. Account Resend/sender verification
and inbox receipt were owner-confirmed earlier. Actual card collection/setup,
signed waiver coverage, confirmed visits/arrival, booking/member emails and active
memberships remain unfinished. Review evidence: [third batch](OWNER_EDITS_BATCH_3.md)
and [52 desktop/phone images](design-review/owner-edits-batch-3/README.md).

The reviewed deployment helper includes the private checkpoint, atomic schema
and limited runtime grants and compatibility checks; it refuses old code that
would ignore new schedule restrictions. It does not implement encrypted nightly
offsite backups, durable workers or external-operation recovery. The latest
[release handoff](OWNER_FEEDBACK_BATCH_THREE_RELEASE.md) is completed per owner
report; ordinary future releases need their own reviewed migration/config plan.

The owner accepted the remaining order: complete ordinary/supervised booking
with **both** card-payment and alternate-tender backup-card routes, then active
memberships, then remaining operations. Use new integrated test reservations and
plan an Old test booking distinction without changing existing financial/setup
facts. Carry the improved filters/layout/forms/customer/history/scheduling rules
through [shared workflow standards](SHARED_WORKFLOW_STANDARDS.md). The updated
[next-stage plan](NEXT_PHASE_REVIEW.md) is documentation only; no application,
provider or hosted changes occurred and next-phase development has not started.

The earlier checkpoint entries below are historical; their undeployed/no-public-
booking statements describe those increments, not today's shared staging site.

Historical foundation checkpoint (see latest increment below): Django/PostgreSQL foundation, customer management, owner/staff security, saved pricing, staff test reservations and owner calendar/weekly schedule controls and membership draft calendars. This is a local development checkpoint, not a deployed or complete staging application.

| Area | Implemented in this increment | Remaining |
| --- | --- | --- |
| Public pages | Home, About, combined programs, Contact and schedule preview | Final owner layout review; functional checkout |
| Branding | Exact original logo and original facility photos via static assets | Final crops/accessibility review |
| Database | Customer, session, booking, settings and append-only audit migrations | Remaining business-domain entities and payment state |
| Availability | New York calendar horizon, Sunday opening, Motzei Shabbos labels and owner-controlled public visibility, party/full labels, session end/supervised cutoff and capacity | Hosted operational scheduling validation; integrated confirmed-booking lifecycle |
| Reservations | Staff pending test reservations, atomic create/edit/reschedule/release, saved pricing and audit | Integrated payment/waiver/benefit lifecycle; public booking remains disabled |
| Customers | Search/create/contact corrections, comments/history, revision protection, permission enforcement | Public returning-customer verification and booking-linked email resends |
| Staff/security | Owner MFA/recovery, staff account/permission controls, versioned session revocation, password resets, shared staging password/rotation; Today, booking management and inspector | Real email delivery, retention/operational recovery and hosted security validation; capability expansion for unfinished features |
| Providers | No external operations enabled | Banquest sandbox, Resend, R2, durable workers and real integration evidence |
| Infrastructure | Local databases only | Cost-reviewed DigitalOcean staging, TLS/DNS, backups/restore and monitoring |
| Training/testing | Scenario document started | Owner video and completed acceptance results after working workflows exist |

## Verification record

- Initial migrations applied to a disposable local PostgreSQL 17 database; artificial Sunday–Friday sessions seeded without deleting existing records.
- Automated test suite: 36 tests passed on PostgreSQL 17, with no skips. Local SQLite also passes with two explicitly skipped PostgreSQL-only tests. Coverage includes PostgreSQL concurrent last-space requests, atomic audit rollback, database constraints, audit mutation guards, schedule/DST rules, permissions and public page rendering.
- Chromium checks at desktop 1440px and mobile 390px: six page routes rendered, no horizontal overflow or JavaScript errors. This is not full WCAG or cross-browser acceptance.
- No Banquest calls, live transactions, provider credentials, outbound customer emails, signed customer documents, production data or infrastructure purchases.
- Original logo/photos, source waiver PDF and preserved standalone waiver HTML remain unchanged. The standalone waiver is not the new application's signature implementation.

Future work must update this record rather than describe planned workflows as completed.

## Private-preview deployment preparation

Prepared the [deployment/cost proposal](STAGING_DEPLOYMENT_PROPOSAL.md) and review-only nginx/systemd examples. Added explicit opt-in trusted-proxy configuration, default off. All 37 tests pass on local PostgreSQL after this change. No server configuration was installed and no service was started on DigitalOcean. Official live pricing verification was blocked by the environment proxy, so listed costs are estimates awaiting checkout verification and purchase approval.

## Customer records and login protection

All 76 tests pass on PostgreSQL 17 after this increment, including concurrent contact creation/correction and concurrent sign-in attempts. Local Chromium workflow checks passed for customer creation, email correction, comments, history/search and desktop/mobile layouts. Details and remaining boundaries: [CUSTOMER_DEVELOPMENT.md](CUSTOMER_DEVELOPMENT.md). No DigitalOcean resize/deployment, paid-service activation, live transaction or outbound email occurred.

## Owner/staff account controls

Added owner email MFA and recovery, staff management, password resets, immediate next-request session revocation, permanent usernames/single-owner database guards and the separate 90-day shared staging password. Details: [ACCOUNT_SECURITY.md](ACCOUNT_SECURITY.md). Local email is in-memory only. Browser workflows pass on desktop/mobile; PostgreSQL one-time-code and identity races are covered. No hosting change, resize, deployment or external mail occurred.

Verification for this account-security checkpoint: all **130 tests pass on PostgreSQL 17**, including concurrent one-time codes/reset redemption. A separate isolated Chromium test completed owner MFA, recovery-email editing, staff creation and independent visitor staging access; owner screens passed desktop/mobile layout checks. Actual hosted HTTPS and external email delivery remain unverified.

## Saved pricing and staff test reservations

Added versioned staging prices and immutable itemized quotes, staff create/edit/reschedule/release screens, owner capacity overrides and stale-edit/idempotency guards. All reservations created here remain **Setup pending**. See [BOOKING_DEVELOPMENT.md](BOOKING_DEVELOPMENT.md) for setup, test limits and deferred integrations. Public checkout, arrivals, payments, waivers and membership allocation remain disabled/unfinished. No deployment or infrastructure change occurred.

Verification: the full 156-test suite passed on PostgreSQL 17; two subsequently added permission/CSRF tests also passed with the 17-test booking module on PostgreSQL and SQLite (158 tests total). The earlier full SQLite run passed with 12 explicit PostgreSQL-only skips. Ruff, migration-drift and static collection checks pass. Isolated Chromium testing completed create/quote/edit/move/release and desktop/mobile booking/pricing layouts. This is local verification, not hosted acceptance or live-provider evidence. Original source assets and standalone waiver remain unchanged.

## Owner calendar controls

Owner one-time sessions, per-session times/visibility/play types/capacity, private date closures and date-level Chol Hamoed marking are implemented locally. Existing bookings and quotes survive closures. Owner changes and reservations coordinate with PostgreSQL transaction locks. See [SCHEDULING_DEVELOPMENT.md](SCHEDULING_DEVELOPMENT.md) for limits, particularly recurring schedules and deferred membership/notification integration.

Verification for this checkpoint: **177 tests pass on PostgreSQL 17**. SQLite passes the same suite with 15 explicit PostgreSQL-only skips. Calendar tests cover overlap/date-edit races, committed closure enforcement, capacity protection, stale revisions, privacy, owner-only permissions/CSRF, DST validation and audit rollback. Isolated Chromium completed owner sign-in/MFA, one-time session creation, date closure/Chol Hamoed marking and desktop/mobile layouts. Ruff, migration drift, static collection and diff checks pass. No hosted deployment, Droplet resize, provider request or outbound email occurred.

## Membership draft foundation

Added staff-created test membership drafts, separate immutable draft cohorts/cycles, monthly/prepaid estimates and owner versioned product pricing. The approved short-month/leap-year/original-anchor rules are implemented in civil-date calculations. All records explicitly remain inactive drafts, with no accepted terms, payment, benefit allocation or scheduled job. See [MEMBERSHIP_DEVELOPMENT.md](MEMBERSHIP_DEVELOPMENT.md) for setup and deferred operational workflows.

Verification: **194 tests pass on PostgreSQL 17**; SQLite passes with 16 explicit PostgreSQL-only skips. Coverage includes original-anchor/leap-year/short-month calendars, grace-renewal date helper, monthly/prepaid estimates, pricing immutability, permissions/CSRF, atomic rollback and concurrent duplicate submissions. Isolated Chromium passed owner MFA, draft creation/review, future product-pricing changes and desktop/mobile layouts. Ruff, migration drift and static collection checks pass. No deployment, Droplet resize, external payment/email/storage operation or paid service occurred.

## Weekly schedule and horizon controls

Owner weekly templates, explicit dated generation/application and the 1–10 day booking horizon are implemented locally. Generation protects bookings, manual overrides, program sessions and independent sessions, with auditable results. Reverting to one day requires confirmation. See [RECURRING_SCHEDULE_DEVELOPMENT.md](RECURRING_SCHEDULE_DEVELOPMENT.md) for generation/update semantics and remaining hosted/notification/benefit work.

Verification: **212 tests pass on PostgreSQL 17**; SQLite passes with 17 explicit PostgreSQL-only skips. Coverage includes repeated/concurrent generation, protected booked/manual/program sessions, date closures, template changes, DST rejection/rollback, owner-only permissions/CSRF, default-horizon confirmation and booking/quote preservation. Isolated Chromium passed owner MFA, weekly-template creation, dated generation, horizon change/reset and desktop/mobile layouts. Ruff, migration drift, static collection and diff checks pass. No hosted deployment, Droplet change, provider operation or paid service occurred.

## Stable design review V1

Prepared 16 read-only rendered layouts plus desktop/phone captures, pinned to source `7a7b674` (PR #15), with artificial sample records. See [gallery](design-review/v1/README.md) and [feedback tracker](DESIGN_FEEDBACK.md). Application layouts/copy/assets and backend behavior are unchanged. Local browser checks validate assets/links, disabled forms, responsive widths and no scripts/CSRF tokens. A hosted URL still awaits secure DigitalOcean/SSH access; no deployment, DNS change, paid service or resize occurred.

## Hosted read-only review release preparation

Added an opt-in design-only URL mode, using the existing shared staging gate, with no operational staff/customer/booking routes. Frozen V1 files remain unchanged. An interactive owner CLI sets the shared password without printing it. [Host setup checkpoint](HOSTED_DESIGN_PREVIEW.md) records operator-reported Ubuntu/PostgreSQL/firewall/account setup and the remaining guided upload/configuration steps. All 219 tests pass on local PostgreSQL 17; targeted gate tests pass on SQLite. Browser checks pass for password access, desktop/phone snapshots, asset loads and disabled operational routes. Hosted TLS/DNS and real-host deployment remain unverified.

## Deployment/rollback preparation

Added a Windows upload/install/update wrapper and design-only server controller with separate per-release environments, validation, private-gate/HTTPS checks, durable recovery checkpoints and code rollback. It refuses pending migrations and does not reverse database schema/data. See [DEPLOYMENT_COMMAND.md](DEPLOYMENT_COMMAND.md). Host installation and actual systemd switching remain operator verification steps; preparation/testing has not changed the live V1 release.

Verification: **243 tests pass on local PostgreSQL 17**, including 23 deployment unit/integration checks plus the real pending-migration guard on the disposable database. Actual frozen V1 files pass the bundle guard. Official portable PowerShell 7.6.9 passes wrapper tests with mocked SSH/SCP; CI also runs the wrapper under Windows PowerShell. No helper installation, live release switch or database migration occurred during preparation. The installation-only command checks the existing site without deploying it.

## Staff portal discovery

Added `/staff/` as a protected staff-login entry, using the existing throttled
staff authentication and owner verification. Removed staff/login/logout links
from the customer layout even for signed-in staff; sign-out remains in the staff
layout. Existing noindex headers and HTML tags cover login, staff, admin and
account pages; no public sitemap exists. Requirements explicitly exclude those
routes from any future sitemap. No frozen V1 files or hosted server changed.

Verification: all 246 tests passed on disposable PostgreSQL 17; Django system
checks, Ruff lint/format and whitespace checks passed. New checks cover removal
of staff links from anonymous and signed-in customer pages, noindex login,
customer credential rejection and the staging entry gate boundary.

## Design review V2: first owner typography and homepage edits

Use locally hosted Nunito as an explicitly temporary match for the rounded ad
body/button lettering. Homepage hero uses the original ad's photo composition
and sage border, isolated from surrounding promotional text, with no generated
or retouched people. Original ad/logo remain unchanged. V2 is a new frozen review
folder; V1 remains preserved. Additional five inline child/activity photos still
need file uploads before About/card placement; their bytes are unavailable in
the workspace. This is not a completed photo-placement change or deployment.

V2 browser validation: all 16 pages checked at desktop 1440px and phone 390px;
all images loaded, no horizontal overflow or JavaScript errors. The existing
deployment helper's bundle validation passes for both V1 and V2. Initial test
run raced screenshot generation (one missing-artifact error); the affected hosted
preview tests were rerun after artifact generation, with the result recorded in
the PR. No migration is introduced.

## Design review V3: uploaded child/activity photographs

Received all five photos in New ImagesMonkey.zip. Preserved originals with
checksums, added photos to Come play / Play more / Celebrate together, and replaced
matching Imaginative Play, Climbing Area and Toddler Zone images. Game Room keeps
its matching facility photo. V3 preserves the ad hero and Nunito from V2; V1/V2
artifacts remain unchanged. No text/pricing or database changes; no deployment.

V3 verification: all 246 tests passed on disposable PostgreSQL 17. All 16 pages
passed Chromium checks at desktop/phone widths; Nunito loading and all three
card-photo aspect ratios were explicitly checked. Static collection, Ruff
lint/format, whitespace checks and deployment-bundle validation passed.

## Design review V4: remove card numbers and add optional motion

Removed decorative 01/02/03 labels from the homepage cards. Added a brief hero
entrance, card lift/shadow for mouse hover and keyboard focus, and slight button/
intro-link movement. Motion is scoped to homepage classes and enabled only when
reduced motion is not requested; reduced motion also disables smooth scrolling.
There is no looping animation, hidden content or JavaScript dependency. Frozen
captures use reduced motion for stable screenshots; interactive CSS is retained.
No deployment or operational behavior changed.

V4 checks: all 21 public-page/hosted-preview tests passed on PostgreSQL 17. All
16 pages passed desktop/phone Chromium validation; dedicated browser checks
passed for animation, hover, keyboard focus and reduced-motion behavior. Existing
deployment helper validates every preserved review bundle. Ruff and whitespace
checks passed. Full 246-test suite passed at the preceding photo checkpoint.

## Design review V5: About play choices

Added “Choose open play or supervised play, when available.” above the two play
options and renamed the first heading to Open play. Pricing/rules unchanged.
All 14 public-page tests passed on PostgreSQL; all 16 review pages passed phone/
desktop browser asset and overflow checks. Ruff, whitespace and deployment-bundle
validation passed. Older snapshots preserved; no deployment.

## Design review V6: line-by-line Open Play copy

Applied the owner's exact Open Play heading and individual lines, with a separate
paragraph for baby-only $15 admission. No price/operational rule changes.
All 14 public-page tests passed on PostgreSQL; all 16 review screens passed
Chromium phone/desktop layout and asset checks. Ruff, whitespace and deployment
bundle checks passed. No deployment.

## Design review V7: Supervised Play wording

Applied the owner's exact four lines and separate session-availability paragraph.
Heading: Supervised Play. Booking cutoff and other operating rules unchanged.
All 14 public-page tests passed on PostgreSQL; all 16 review pages passed phone/
desktop Chromium layout and image checks. Ruff, whitespace and deployment-bundle
validation passed. No deployment or database changes.

## Design review V8: homepage booking button and ages

Booking button moves 10px lower and includes the original logo monkey as a
small decorative icon. Age line is enlarged to 18px (responsive minimum 15px).
Measured before/after positions at 1440px, 390px and 320px: hero paragraph, age
line, intro and cards moved 0px; only the button moved 10px. No overlaps/overflow.
All 14 public-page tests passed on PostgreSQL; all 16 review screens passed
Chromium phone/desktop asset and layout checks. Ruff, whitespace and deployment
bundle validation passed. No deployment or database changes.

## Design review V9: homepage card wording

Updated Come play link to “See available play sessions” and Celebrate together
copy to “A private party filled with MonkeyDo fun, family and friends.” Retains
earlier number removal and all prior requested visual changes. All 16 review
screens passed desktop/phone Chromium asset and overflow checks; Ruff, whitespace
and deployment-bundle validation passed. No deployment or business-rule changes.

## Design review V10: approved membership benefits

Restored both membership marketing cards to the approved semantic bullet lists
and per-child/month prices in MEMBERSHIPS.md/AG, including party discount,
three-month minimum and Unlimited exclusions. Pricing/eligibility rules unchanged.
All 14 public-page tests passed on PostgreSQL; all 16 review screens passed
phone/desktop Chromium image/layout checks. Ruff, whitespace and deployment
bundle checks passed. No deployment or database changes.

## Design review V11: separate pages and scrolling homepage

Memberships and Clubs & Parties now have separate routes/navigation. Homepage
continues through full shared About, Memberships, Clubs & Parties and Contact Us
content in that order. The existing combined URL remains unlinked for bookmarks.
Clubs visibility works on dedicated/legacy pages and homepage, leaving parties
visible. Earlier owner wording and business rules remain intact.

All 247 tests passed on disposable PostgreSQL 17 after correcting a missing
shared-section body caught by the new page test. All 17 review pages passed
Chromium desktop/phone image/layout checks. Ruff, whitespace and deployment-bundle
validation passed. PR #20 now targets main after the parent PRs merged. No
migration, deployment or provider operation occurred.

## Design review V12: play jump and homepage Gift Cards

Come play says “See play sessions” and jumps to #play-sessions on the homepage,
where both types and the existing booking link are present. Gift Cards now has a
separate section after Clubs & Parties and before Contact Us. Reuses the approved
in-person purchase notice, also preserved on the dedicated/legacy program pages.
All 15 public-page tests passed; all 17 review pages passed phone/desktop browser
asset/layout checks. Browser click checks verified the anchor lands at both play
options, the booking link remains and Gift Cards is in order. Ruff, whitespace
and deployment-bundle validation passed. No deployment/business-rule changes.

## Design review V13: colored photo play cards and membership headings

Added a thin divider, Ready to play eyebrow and full-size Open play or supervised
play heading. Play options now have sage/coral backgrounds and supplied activity
photos; subtitles sit 6px below titles with 24px separation before details.
Memberships has More ways to go bananas above it and decorative original monkeys.
Removed named-children sentence from public copy without changing allocation.
All 15 public-page and seven hosted-preview tests passed on PostgreSQL. All 17
review pages passed Chromium phone/desktop asset/overflow checks; dedicated browser
checks verified colors, images, heading text, spacing, removed copy and jump link.
Ruff, whitespace and deployment-bundle validation passed. No deployment.

## Design review V14: selected play-card photo crops

Open Play now shows the child tossing soft green foam blocks; Supervised Play
shows the child on monkey bars, cropped from the original uploaded photograph.
Use 4:3 proportions to retain the selected subjects. No generative edits or
business-rule changes. All 17 phone/desktop review screens and dedicated card
layout checks passed in Chromium; seven hosted-preview tests passed on PostgreSQL.
Ruff, whitespace and deployment-bundle validation passed. Nothing deployed.

## Design review V15: play-option buttons

Open Play uses “Book your session now →”. Supervised Play now has “See available
sessions”. Both target the booking schedule; button width/gap adapts to phones.
All 17 review pages and dedicated card checks passed on desktop/phone Chromium.
Seven hosted-preview tests passed on PostgreSQL; Ruff, whitespace and deployment
bundle checks passed. No deployment or business-rule changes.

## Design review V16: hero age-line order and booking arrow

Ages 1–10 now appears on the next line of the introductory paragraph, above the
booking button, with inherited paragraph typography. The button keeps the original
monkey and ends with an arrow. Dedicated Chromium checks passed at 1440px, 390px
and 320px: correct order/font/line spacing, visible icon/arrow and no overflow.
All 17 desktop/phone review pages and seven hosted-preview tests passed. Ruff,
whitespace and deployment-bundle checks passed. Updated homepage JPGs captured;
no deployment.

## Design review V17: scroll motion throughout remaining homepage sections

Added progressive CSS view-timeline fade/slide effects to 22 homepage section
headings/cards and the intro. All remain fully visible without animation support;
reduced motion disables effects and keyboard focus stops motion on that card.
No scripts were added or preview restrictions weakened. Standalone pages are static.
All 22 public-page/hosted-preview tests passed on PostgreSQL. All 17 desktop/phone
review screens passed Chromium checks. Dedicated normal/reduced-motion browser
checks verified actual scroll progress, focus, scope and no overflow at both
widths. Ruff, whitespace and deployment-bundle validation passed. Nothing deployed.

## Design review V18: proposed darker pink and hero spacing

Added 14px before the ages line, still above booking in paragraph typography.
Proposed #AA405A rose replaces brown accent and colors the eight selected area,
play and club headings. Contrast ratios: cream 5.47:1, sage 4.82:1, coral 4.58:1.
This is a color preview for owner review. All 17 desktop/phone review screens,
specific color/gap/order/font browser checks and seven hosted-preview tests passed.
Ruff, whitespace and deployment-bundle validation passed. Nothing deployed.

## Design review V19: approved edited photos and preserved originals

Saved approved full-scene and close-up PNG masters separately with checksums.
Use WebP derivatives for the Home Celebrate together card, Climbing Area on
Home/About, and Supervised Play on Home/About. The different-child Open Play
crop stays unchanged. All 17 original-image checksums and two approved-master
checksums passed. Originals and historical reviews remain untouched.
All 15 public-page and seven hosted-preview tests passed on PostgreSQL. All 17
review screens and dedicated image-placement checks passed desktop/phone Chromium
validation. Ruff, whitespace and deployment-bundle checks passed. Assets saved in
the repository, not uploaded to R2; no deployment or database changes.

## Pending customer self-booking and functional staging preparation

Customers can now create pending test reservations from the session schedule, using approved returning-contact checks, server-calculated review/revision, atomic capacity enforcement and idempotent submission. Staff can inspect and release the same booking; the customer receipt reflects release. The opt-in flag defaults off, and frozen design-review files remain unchanged.

Added a staging-only allowlisted Resend account-email transport, read-only functional preflight, hidden shared-password command and isolated Functional deployment target with separate configuration templates. No provider call, actual email, server setup, database migration on DigitalOcean, DNS/TLS change or functional deployment occurred. Initial migration 0021 and isolated runtime/bootstrap remain operator work. Current design deployment completion is not asserted here.

Verification: 278 tests passed on PostgreSQL 17, including customer privacy/CSRF, last-space/duplicate races, stale quote/profile rollback and mocked transport/target guards. Portable PowerShell wrapper tests passed with SSH/SCP mocked. Chromium completed customer review/revise/save and actual staff login/search/release at desktop 1440px and phone 390px, with updated customer receipt and no overflow/JS errors. Native Windows CI and hosted/provider acceptance are separate evidence.

Payments, waivers, active membership benefits, arrivals, booking-linked customer email corrections/resends and automatic test-reservation expiry remain unfinished. See [CUSTOMER_BOOKING_DEVELOPMENT.md](CUSTOMER_BOOKING_DEVELOPMENT.md) for setup and acceptance.

## Shared staging URL follow-up (supersedes two public URLs)

The owner selected a single `staging.monkeydoplay.com` homepage for design review and booking tests, with separately authenticated `/staff`. Functional helper configuration, preflight, nginx/TLS example and environment template now use that existing hostname. Internal functional release/database isolation remains for recovery; no second DNS record or paid service is needed. Historical frozen HTML remains in Git but will not serve the root after cutover.

The owner supplied a host memory snapshot showing 1.9 GiB total and 1.4 GiB available. This supports attempting the initial test setup, not a load-test or disk-space claim. The coding environment has no Droplet SSH identity. Functional host setup, real account-email delivery and nginx cutover remain unperformed. Deployment and recovery steps are in [SHARED_STAGING_CUTOVER.md](SHARED_STAGING_CUTOVER.md).

## Motzei Shabbos update — local verification

Shared human-readable date formatting and weekly labels use Motzei Shabbos without changing stored civil dates, timestamps, ISO values or weekday indices. Owner-designated public sessions now use the ordinary availability/booking rules; private sessions remain hidden. The default Sunday–Friday schedule and staff scheduling permissions are unchanged. Full PostgreSQL suite: 367 tests passed; additional focused checks covered Today, current owner scheduling, generated sessions, public booking/receipt, staff booking/customer records and New York/UTC boundaries. Lint/format, Django checks, migration drift and static collection passed. No new migration is needed for this update; earlier pending batch migrations still apply to the eventual release. No screenshots were created, as requested. Staging has not changed.

## Single-page backend booking — PR #36, awaiting owner review

Backend creation now combines the existing customer/session/count controls, live price estimate, inline owner pricing/complimentary controls, named/current/paper waivers, secure card choice and one Confirm booking action. Visible capacity counts, owner capacity override and closing the session remain. The owner's clarified backend rule reserves selected places for 30 minutes; expiry releases them automatically, while confirmed bookings retain capacity. Public booking keeps its existing 20-minute form timeout and reserves places at successful confirmation.

The private draft retains choices after validation errors and reopening. Electronic signing stays in a dialog; paper details are recorded atomically with final confirmation. Confirmation consumes only its own hold, binds the reviewed card, queues one email and collects no ordinary admission payment. Expired holds, concurrent last-place attempts, repeat confirmation, owner pricing, runtime grants and migration deployment checks are covered. Migration 0053 adds only operational capacity holds and is pinned in the reviewed deploy helper.

Local verification: **709 PostgreSQL tests passed**; Ruff, format, Django checks, migration drift and static collection passed. The [gallery](design-review/single-page-staff-booking/README.md) contains nine desktop/phone pairs, with no overflow or JavaScript errors in the walkthrough. Payment fields/outcomes and storage are simulated; actual Banquest iframe verification remains deferred. No external provider or live deployment was used. The draft PR remains open for owner screenshot feedback; merge and release ZIP follow review.

### PR #36 waiver review correction

The owner requested current waiver summaries without individual selection boxes, followed by a clear coverage/email-link choice. The page now lists current electronic and paper waivers, requires everyone-covered versus include-link, and automatically uses the current customer-owned records for a covered booking. The link answer persists `share_requested` and includes the secure signing link in one queued confirmation. Single-customer and other-parent instructions appear only for the link choice; on-page electronic and paper signing remain available. All **712 PostgreSQL tests passed**, including automatic coverage, explicit link delivery/idempotence and draft-answer recovery. The gallery now has **10 desktop/phone pairs** with fresh v2 filenames; Screen 10 shows the requested link option. No live deployment or external provider call was performed.
