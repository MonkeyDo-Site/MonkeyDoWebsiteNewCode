# Staging build status

Historical foundation checkpoint (see latest increment below): Django/PostgreSQL foundation, customer management, owner/staff security, saved pricing, staff test reservations and owner calendar/weekly schedule controls and membership draft calendars. This is a local development checkpoint, not a deployed or complete staging application.

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
