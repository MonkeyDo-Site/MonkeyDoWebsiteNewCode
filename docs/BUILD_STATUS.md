# Staging build status

Current checkpoint: Django/PostgreSQL foundation, customer management, owner/staff security, saved pricing, staff test reservations and owner calendar controls. This is a local development checkpoint, not a deployed or complete staging application.

| Area | Implemented in this increment | Remaining |
| --- | --- | --- |
| Public pages | Home, About, combined programs, Contact and schedule preview | Final owner layout review; functional checkout |
| Branding | Exact original logo and original facility photos via static assets | Final crops/accessibility review |
| Database | Customer, session, booking, settings and append-only audit migrations | Remaining business-domain entities and payment state |
| Availability | New York calendar horizon, Sunday opening, Saturday hiding, party/full labels, session end/supervised cutoff and capacity | Recurring schedule editor; integrated confirmed-booking lifecycle |
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
