# MonkeyDo DigitalOcean VPS Hosting Plan

Documentation-only checkpoint created on 2026-08-05. This file documents the requested DigitalOcean VPS direction. It does not provision infrastructure, create application code, add deployment configuration, or store credentials.

## 1. Confirmed hosting direction

The owner wants the website and backend hosted on a VPS using DigitalOcean.

Recommended interpretation:

- Use a DigitalOcean Droplet as the VPS for the web application and backend.
- Keep the public website and backend API/admin dashboard on the same deployed application unless the future implementation requires separation.
- Use Docker Compose or a similar process-managed deployment approach during implementation.
- Use HTTPS with automatic certificate renewal.
- Use environment variables or a secure secrets mechanism for credentials.

## 2. What can and cannot be set up now

This repository currently contains only documentation. The application has not been built yet by request.

Therefore, this checkpoint can document the DigitalOcean plan, but it should not add:

- Application deployment code.
- Dockerfiles.
- Reverse proxy configuration.
- Database migrations.
- Payment integration configuration.
- Production secrets.
- DigitalOcean API credentials.

Actual VPS provisioning requires access to a DigitalOcean account and several final choices listed below.

## 3. Recommended DigitalOcean production architecture

Recommended services:

1. DigitalOcean Droplet for the website/backend application.
2. PostgreSQL on the same Droplet for the initial production database, as selected by the owner to reduce initial cost.
3. DigitalOcean Spaces only if the project later needs file uploads, such as scanned in-person waivers or image/document storage.
4. DigitalOcean monitoring and backups/snapshots for operational safety.
5. DNS records pointing the production domain to the Droplet.

## 4. Droplet recommendation

For the initial production launch, use an Ubuntu LTS Droplet sized for a small business booking website.

Recommended starting size:

- 2 vCPU / 2 GiB RAM or better for the application VPS.
- New York region, subject to availability when the Droplet is provisioned.
- Backups enabled.
- SSH key authentication only.
- Root login disabled after initial setup.
- Firewall restricted to SSH, HTTP, and HTTPS.

DigitalOcean bills Droplets per second with a minimum charge. A powered-off Droplet can still incur charges because compute resources remain reserved; destroying the Droplet ends billing.

## 5. Database recommendation

The production database must be persistent PostgreSQL.

Selected initial option:

- Run PostgreSQL on the same Droplet as the application to reduce initial cost.

Accepted tradeoffs and required safeguards:

- Lower monthly cost, but more operational risk and maintenance responsibility.
- Application and database share CPU, memory, disk, and a failure domain.
- Requires automated encrypted backups stored outside the Droplet, a documented retention policy, and routine restore testing.
- Requires PostgreSQL security updates, monitoring, disk-capacity alerts, and maintenance by the operator.
- The architecture must allow a later migration to DigitalOcean Managed PostgreSQL without rebuilding the application.

DigitalOcean Managed PostgreSQL remains a future upgrade option for stronger isolation, managed backups, and reduced database-maintenance responsibility.

## 6. Object/file storage

DigitalOcean Spaces is not required for the basic booking website unless file uploads are added.

Use Spaces later if the owner wants to store:

- Uploaded/scanned paper waivers.
- Signed waiver PDFs.
- Uploaded customer documents.
- Large media files.

If the owner only needs an admin checkbox that a waiver was signed in person, Spaces may not be necessary at launch.

## 7. Required information before provisioning

The owner has confirmed:

- The existing DigitalOcean account can create Droplets, Managed PostgreSQL databases, backups/snapshots, and Spaces storage.
- The account currently has free credit; the owner will add paid billing when it is needed.
- The production domain is being purchased and is not yet available.
- The domain provider will manage DNS and point the production domain to DigitalOcean.
- New York is the preferred DigitalOcean region.
- PostgreSQL will initially run on the same VPS as the application.

To actually set up the DigitalOcean VPS, the implementer will still need:

- DigitalOcean account access or a scoped DigitalOcean API token.
- Final production domain name and the required DNS records applied by the owner/domain provider.
- SSH public key for server access.
- Confirmation of Droplet size.
- Backup/snapshot preference.
- Monitoring/alert email.
- Production environment variables once providers are chosen.

Sensitive credentials must not be committed to the repository.

Before the production domain is connected, testing can use the Droplet's public IP address or a deliberately configured temporary hostname. A browser-ready DigitalOcean URL should not be assumed to exist automatically; the exact temporary-access method will be confirmed during provisioning.

## 8. Proposed server hardening checklist

When provisioning is approved and credentials are available, the VPS should be configured with:

- Ubuntu LTS.
- Non-root deploy user.
- SSH key authentication.
- Password SSH login disabled.
- Root SSH login disabled.
- UFW firewall allowing only SSH, HTTP, and HTTPS.
- Automatic security updates.
- Fail2ban or equivalent SSH protection.
- Nginx or Caddy reverse proxy.
- HTTPS certificates with automatic renewal.
- Application process supervision.
- Centralized application logs with sensitive-data redaction.
- Database backups and restore testing.
- Monitoring and disk-space alerts.

## 9. Deployment approach for future implementation

Recommended future deployment flow:

1. Build the application in the repository.
2. Add production Dockerfile and Docker Compose configuration only after implementation is approved.
3. Configure environment variables on the server, not in source code.
4. Run database migrations against the production database.
5. Start the application behind Nginx or Caddy.
6. Configure HTTPS.
7. Configure provider webhooks for Stripe, email, and SMS.
8. Run smoke tests.
9. Document rollback and backup restore steps.

## 10. Production readiness guardrails

DigitalOcean hosting does not make payments, messaging, waiver, or cancellation/no-show workflows production-ready by itself.

The following are still required before live launch:

- Built application code.
- Persistent production database.
- Stripe account and approved consent wording.
- Email provider account and approved templates.
- SMS provider account, compliance approval, and approved text wording if SMS is enabled.
- Final waiver wording.
- Final cancellation/no-show policy.
- Zelle business details and payment deadline.
- Full security review.
- Automated tests.
- Production smoke tests.
