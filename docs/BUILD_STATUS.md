# Staging build status

First increment: Django/PostgreSQL foundation. This is a local development checkpoint, not a deployed or complete staging application.

| Area | Implemented in this increment | Remaining |
| --- | --- | --- |
| Public pages | Home, About, combined programs, Contact and schedule preview | Final owner layout review; functional checkout |
| Branding | Exact original logo and original facility photos via static assets | Final crops/accessibility review |
| Database | Customer, session, booking, settings and append-only audit migrations | Full business-domain entities and immutable pricing/payment state |
| Availability | New York calendar horizon, Sunday opening, Saturday hiding, party/full labels, session end/supervised cutoff and capacity | Owner scheduling/closure/override screens and atomic rescheduling |
| Reservations | Internal atomic capacity check and audit | Integrated payment/waiver/benefit lifecycle; public booking remains disabled |
| Staff | Login, permission-checked read-only Today and inspector | Full custom portal, owner MFA/recovery, throttling, staff lifecycle and separate staging password |
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
