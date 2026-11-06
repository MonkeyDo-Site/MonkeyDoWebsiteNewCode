# Private staging preview: deployment proposal

**Latest owner update:** an existing smaller DigitalOcean Droplet is already purchased; a necessary size upgrade and its higher hosting fee are authorized when needed. Assess it first and coordinate downtime. The estimates below describe the full proposed server price, not a verified incremental charge; the increase depends on the existing plan. No resize has been performed.

**Approval status:** development and configuration preparation, plus the deferred resize authorization above. No new service purchase/activation, deployment, DNS change or provider credential installation is authorized by this proposal. Nothing below has been installed on DigitalOcean.

## Preview timing

Planning estimate: **1–3 focused development days** remain before an initial protected, read-only browser preview is deployment-ready. This includes the access/security work needed for that restricted preview, reviewed deployment configuration, environment checks and acceptance smoke tests. Deployment after approval also depends on account/SSH access, DNS/certificate setup and provider availability. This is an effort estimate, not a guaranteed calendar delivery date or unattended background work.

A preview does not require completion of all business workflows. It can expose the five public page layouts, test-session availability and a read-only staff view while checkout/provider operations remain disabled. Full owner/staff security controls and the integrated transactional workflows remain required before functional staging acceptance. The broader booking/membership/payment/waiver/program build is still several weeks of development and review; the preview is an earlier checkpoint.

## Recommended configuration and estimated monthly costs

Use one Basic shared-CPU DigitalOcean Droplet, regular SSD tier, New York region, **2 vCPU / 4 GB RAM / approximately 80 GB SSD / 4 TB included transfer**, supported Ubuntu 24.04 LTS. Run Django/Gunicorn, nginx and PostgreSQL 17 on this server. PostgreSQL listens locally/private only; application traffic reaches Gunicorn through a Unix socket. A worker can be added on the same server when durable jobs exist, subject to load checks.

**Price verification limitation:** direct requests to the official DigitalOcean, Cloudflare R2 and Resend pricing pages returned proxy `403 Forbidden`. The following are budget estimates based on previously published prices, not current checkout quotes. Verify plan availability, taxes, account-wide allowances and actual prices before asking for final purchase approval.

| Item | Estimated monthly USD | Treatment |
| --- | ---: | --- |
| Basic Droplet, 2 vCPU/4 GB | $24.00 | Recommended staging server; confirm regular tier in checkout |
| PostgreSQL on that Droplet | $0 additional | Shares the Droplet's RAM/disk; database software is free |
| Django/Gunicorn/nginx | $0 | Free software; no Django hosting subscription |
| Cloudflare DNS/proxy and TLS | $0 on existing free configuration | No paid plan proposed; existing domain renewal remains separate |
| Dedicated staging R2 buckets | $0 within available free allowance | Later required for signed test waivers and encrypted backups; usage charges beyond allowance, not a guaranteed free account |
| Resend test emails | $0 within available free plan | Later email testing; current allowance/account/sender limits require confirmation |
| Banquest sandbox | Confirm existing account terms | No live processing; no new paid gateway plan proposed |
| External uptime monitor | $0 target using suitable free tier | Provider not selected; not required for first read-only preview |
| Optional weekly Droplet image backup | Approximately $4.80 | Historically 20% of Droplet cost; optional, separately approved and current price unverified |

**Base infrastructure estimate: approximately $24/month before tax and usage overages.** With the optional image backup: approximately **$28.80/month**. Budget around **$25–$35/month** for low-volume staging, with actual service/usage choices confirmed before purchase; this is not an approved spend or a hard billing cap. Do not buy optional services automatically.

The optional server image backup is not the approved application backup system. Application backups still require encryption before R2 upload, seven nightly/twelve monthly recovery points and tested restoration with the private key outside DO/R2. Before selecting image backups, review what they contain and how their provider protections fit the owner's backup requirements.

No separate managed PostgreSQL subscription, second Droplet, load balancer, paid Redis, Spaces bucket or paid SSL certificate is proposed for this phase. Self-hosted PostgreSQL means database upgrades, disk monitoring and backup/recovery are our operational responsibilities. Before production, evaluate shared staging/production resources and the need for a separate server or managed database.

## Steps after explicit approval

1. Present verified final plan/price and any paid options for approval. Confirm account ownership and scoped access without requesting the owner's password.
2. Review/merge the tested application increment and pin the release commit. Prepare a separate staging database/app identity, protected configuration and test-only seed data. No production data or credentials.
3. Assess the existing Droplet and resize only as needed under the owner authorization (coordinate downtime); do not purchase a second server. Then install supported packages, create a non-root deploy user and SSH access, firewall public database/Gunicorn access, enable security updates and review recovery access.
4. Install PostgreSQL and an isolated staging database with an application role. Use an administrative role for migrations where needed; do not grant the runtime role schema ownership merely to run the application. Do not expose port 5432 publicly.
5. Install the pinned Python environment and application release. Supply private server configuration and run reviewed migrations/static collection. Inspect the example systemd/nginx files before installation; they are not an automated deployment script.
6. Complete the separate shared staging-password gate and application authentication controls appropriate to the exposed preview. Restrict unfinished workflows. Do not describe the current temporary gate as the full required owner/staff security implementation.
7. With DNS approval, add only `staging.monkeydoplay.com` in Cloudflare. Configure strict HTTPS to the origin, reviewed trusted-proxy behavior and origin access restrictions. Leave the production hostname unchanged. Do not trust arbitrary client-provided forwarding headers.
8. Start/reload services only after deployment approval. Confirm staging redirects, private access, cookies, static assets, database migrations, no private caching/search indexing, no live keys, no outward customer emails and no production bucket/database access. Test failed login and direct-origin access.
9. Provide browser URL and securely communicated access instructions, build identifier, enabled/disabled feature list and the scenario checklist. Retain a rollback release and preserve test work across updates.
10. Add sandbox/R2/Resend credentials only when their integrations are ready. No live keys for staging. Additional paid plans require separate approval.

## What can be tested in the first browser preview

- Public layout/navigation, approved copy, original logo/photos, mobile/tablet rendering and image crops.
- Displayed test-session times, unavailable/full/party labels and calendar presentation, using artificial configured data.
- Sign-in and a read-only staff Today view appropriate to the restricted preview.
- Accessibility/layout feedback and the test-mode indicators.

Not yet an end-to-end test: completed bookings, public returning-customer verification and booking-linked emails, arrival charging, memberships/benefit/credit rules, clubs/parties workflows, electronic signature saving/private retrieval, real sandbox payments, emails, automated jobs, backups/restores or final permission/MFA flows. Enable and test each only when implemented, not through a simulated success screen. See [BUILD_STATUS.md](BUILD_STATUS.md) and [STAGING_TEST_PLAN.md](STAGING_TEST_PLAN.md).

## Preparation completed locally

- Added review-only nginx/systemd templates under `deploy/`; no installation/start/reload command was run on a host.
- Added an explicit `DJANGO_TRUST_PROXY` switch and tests. Default remains off; enable only with the reviewed proxy overwriting the header and Gunicorn reachable solely through a private socket.
- Protected server environment paths and credential timing are documented in [DEVELOPMENT.md](DEVELOPMENT.md).

Official pages to verify before purchase: [Droplets](https://www.digitalocean.com/pricing/droplets), [server backups](https://www.digitalocean.com/pricing/backups), [R2](https://developers.cloudflare.com/r2/pricing/), [Resend](https://resend.com/pricing). These links are references, not evidence of successful current-price verification.

Customer-management update: the local build now also supports staff customer creation/search/corrections/comments/history and Dashboard security alerts. Those can be included in the private preview once access protections are completed. Full booking/payment/waiver/member workflows remain unfinished.
