# Staging build status

Current checkpoint: Django/PostgreSQL foundation, customer management, owner/staff security, saved pricing, staff test reservations and owner calendar/weekly schedule controls and membership draft calendars. This is a local development checkpoint, not a deployed or complete staging application.

| Area | Implemented in this increment | Remaining |
| --- | --- | --- |
| Public pages | Home, About, combined programs, Contact and schedule preview | Final owner layout review; functional checkout |
| Branding | Exact original logo and original facility photos via static assets | Final crops/accessibility review |
| Database | Customer, session, booking, settings and append-only audit migrations | Remaining business-domain entities and payment state |
| Availability | New York calendar horizon, Sunday opening, Saturday hiding, party/full labels, session end/supervised cutoff and capacity | Hosted operational scheduling validation; integrated confirmed-booking lifecycle |
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
