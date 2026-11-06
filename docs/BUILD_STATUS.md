# Staging build status

Current checkpoint: Django/PostgreSQL foundation, customer management and locally tested owner/staff security controls. This is a local development checkpoint, not a deployed or complete staging application.

| Area | Implemented in this increment | Remaining |
| --- | --- | --- |
| Public pages | Home, About, combined programs, Contact and schedule preview | Final owner layout review; functional checkout |
| Branding | Exact original logo and original facility photos via static assets | Final crops/accessibility review |
| Database | Customer, session, booking, settings and append-only audit migrations | Full business-domain entities and immutable pricing/payment state |
| Availability | New York calendar horizon, Sunday opening, Saturday hiding, party/full labels, session end/supervised cutoff and capacity | Owner scheduling/closure/override screens and atomic rescheduling |
| Reservations | Internal atomic capacity check and audit | Integrated payment/waiver/benefit lifecycle; public booking remains disabled |
| Customers | Search/create/contact corrections, comments/history, revision protection, permission enforcement | Public returning-customer verification and booking-linked email resends |
| Staff/security | Owner MFA/recovery, staff account/permission controls, versioned session revocation, password resets, shared staging password/rotation; read-only Today and inspector | Real email delivery, retention/operational recovery and hosted security validation; capability expansion for unfinished features |
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
