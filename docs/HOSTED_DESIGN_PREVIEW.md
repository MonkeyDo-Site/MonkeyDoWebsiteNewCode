# Hosted design preview preparation

The owner authorized a private design preview and has been configuring the new DigitalOcean Droplet through their own Windows SSH session. Cloud-agent SSH is not configured; commands run by the owner must not be described as agent-verified deployment.

## Operator-reported host checkpoint

- Replacement host **107.170.1.143**; the earlier **67.205.159.250** is not the deployment target.
- Ubuntu 24.04.5 LTS, approximately 2 GB RAM/50 GB disk, updated kernel 6.8.0-149-generic.
- UFW active: SSH/80/443 allowed; PostgreSQL 17 main online, listening on 127.0.0.1/[::1] only.
- SSH login `monkeydo-deploy` tested by the owner, using their own existing public key. No personal private key was shared.
- Internal Linux/SQL accounts `monkeydo` and `monkeydo-migrate`, staging database `monkeydo_staging` owned by the migration role. Local peer-auth application connection succeeded.
- Operator applied public-schema USAGE plus migration-role default table DML and sequence USAGE/SELECT grants to application role. Runtime does not own schema. These facts are owner reports/screenshots, not a remote audit.

## Design-only release

Set **APP_ENV=staging** and **MONKEYDO_DESIGN_ONLY=1**. This selects a restricted URL configuration: only the existing shared staging-password gate and frozen V1 HTML/screenshots are available. Operational staff/customer/booking/admin/login routes are absent. Customer, booking and membership samples come from the immutable V1 files, not an operational record query. Existing access expiry, ticket rotation, rate limits, CSRF and Secure/HttpOnly cookies remain in use. No second Basic Auth password or real staff-MFA bypass is introduced.

The source CSS/original images are collected from the same pinned release. The HTML asset paths are normalized at response time, without rewriting V1 files. Frozen pages are GET/HEAD only and send no-store/noindex plus a restrictive CSP. File serving is allowlisted from the V1 manifest and screenshot IDs; arbitrary project files and directory browsing are not exposed.

Create the owner account privately through Django `createsuperuser` after migrations. Then run `manage.py set_design_review_password --owner <username>` interactively. Password input is hidden and never accepted through command-line arguments. This configures the existing shared gate only; the design-only release exposes no operational staff login. Future functional staging still requires verified owner email/MFA setup.

## Remaining operator sequence

1. Prepare `/srv/monkeydo/releases` owned by `monkeydo-deploy`. Download the pinned release archive through the owner's authenticated GitHub browser; upload from a separate **local Windows PowerShell** with `scp`. No GitHub token/private key goes in chat.
2. Extract to a named immutable release. Create `/srv/monkeydo/staging/venv` as deploy user, install pinned requirements, and point `/srv/monkeydo/staging/current` to that release. Application/migration users read code but do not own the deployment checkout.
3. Generate a strong Django secret on the server into protected `/etc/monkeydo/staging.env`; never print it or overwrite an existing secret blindly. Set explicit staging hostname, CSRF HTTPS origin, trusted local proxy and design-only mode. Use POSTGRES_HOST=/var/run/postgresql and POSTGRES_USER=monkeydo for peer authentication; no database password is needed. Keep configuration outside Git/releases.
4. Run migrations as Linux/SQL `monkeydo-migrate` with POSTGRES_USER=monkeydo-migrate. The owner's previously applied default grants give runtime access to resulting tables/sequences. Collect static assets into the pinned release. Verify runtime schema CREATE privilege is false and required table permissions work.
5. Create the owner account and configure the shared preview password interactively; retain credentials privately. Do not seed operational customers/bookings; sample screen data is already frozen.
6. Inspect/install `deploy/monkeydo-design-review.service.example`, verify Unix-socket permissions and the design-only environment flag. Do not expose Gunicorn or PostgreSQL publicly.
7. Confirm the domain's actual DNS provider. Add only staging.monkeydoplay.com → 107.170.1.143; preserve root/www/email records and nameservers. Configure a trusted certificate and HTTPS before entering any preview password. Keep HTTP at challenge-only/redirect, with no operational app exposed.
8. Review/install nginx configuration with the local Unix socket and overwritten HTTPS header. Recheck TLS/origin/host handling, gate denial, no-store/noindex, asset loads, disabled operations and runtime database privileges on the actual host. Local tests are not hosted TLS evidence.
9. Provide the verified URL and access instructions, keeping the password out of chat/logs/screenshots. Serve this release unchanged while backend work uses separate branches/releases. No additional paid service is proposed.

## Verification boundary

Local tests exercise the restricted routes/gate, safe file allowlist, read-only responses, CSRF, secure ticket, password rotation and hidden CLI input. Browser checks exercise the gate and desktop/phone snapshot layouts. No host installation, HTTPS certificate, DNS change or service startup is claimed by repository preparation.

## Subsequent deployment automation

The owner reports HTTPS/private access is now working after guided nginx/Certbot configuration. The agent has not directly audited that host. [DEPLOYMENT_COMMAND.md](DEPLOYMENT_COMMAND.md) prepares a Windows update wrapper and root-owned design-preview controller. Installation alone leaves the existing release unchanged; no automated host deployment is claimed until the operator runs and verifies it.
