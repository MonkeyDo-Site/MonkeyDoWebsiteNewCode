# DigitalOcean, Cloudflare, staging, storage, and backups

Current planning direction, November 5, 2026. This file is requirements, not provisioning or deployed configuration. The owner subsequently authorized staging development and approved Django/PostgreSQL. Paid provisioning and production actions retain their separate approvals.

## 1. Hosting and public addresses

- DigitalOcean hosts public application/backend/admin and initial persistent PostgreSQL. Keep a maintainable unified application; allow later migration to Managed PostgreSQL without rebuilding business logic. No production JSON-file database.
- **https://monkeydoplay.com** canonical; **www.monkeydoplay.com** redirect. Domain purchased. **Cloudflare manages DNS and proxies production/staging traffic**, with strict verified HTTPS from visitor to Cloudflare to origin. This replaces external-registrar/temporary-DigitalOcean-public-address launch language.
- **staging.monkeydoplay.com** is protected test site. Protected IP/temporary hostname may be used internally before approved DNS, never presented as final public address.
- Do not cache private/dynamic booking/customer/admin/payment/waiver/confirmation responses. Static public media/assets may cache. Email/verification DNS records follow provider instructions, not ordinary website proxy treatment.
- Prefer New York region, supported Ubuntu LTS, approximately **2 vCPU/4GB RAM** initial proposal. Final CPU/RAM/disk/region availability/current recurring price and backup costs need presentation/approval before purchase. Old2GB suggestion is superseded.
- Latest owner direction: start with one DigitalOcean server for staging only. Before production, assess whether it can safely host both environments with separate processes/databases/secrets/buckets; a second server is optional, not a requirement. Present actual costs before purchasing either arrangement.
- Latest owner update: an existing smaller Droplet has been purchased, and a necessary resize with its increased hosting fee is preauthorized for the appropriate development stage. Assess actual size/usage first, choose the smallest suitable upgrade and coordinate any required downtime. No resize is performed by this local increment. Additional services and deployment/DNS/live-payment approvals remain separate.
- Existing provider-account free-credit/billing statements are historical, not verification of current balance or a free-hosting promise.

## 2. Separation and staging

- Separate processes, databases, environment settings, provider credentials and buckets per environment. No production customer/participant/payment/waiver data in staging; use artificial test records. Staging never accesses production R2 buckets.
- **Banquest sandbox only** for staging; transactions cannot migrate into live. Before separately authorized launch validate production endpoint/key selection explicitly; do not “move” sandbox transactions/customers into production.
- Shared staging password known to owner, owner-changeable in settings, **90-day rotation**. Staging access password is separate from owner/staff authentication and permission checks.
- Real Resend test emails may go to **any tester-entered address**, not a mandatory allowlist. Prefix **[MONKEYDO TEST]**, visible **This is a test message from the MonkeyDo staging website. This is not a real booking, payment, membership, or reservation.**, staging-only links, conspicuous TEST MODE admin indicator. Distinguishable sender where supported. Test delivery/bounce/retry states.
- **Manual owner-confirmed staging resets** only, no automatic deletion of test progress. Reset affects artificial staging data, never production or original source artifacts. Decide exact reset scope/retention with visible preview during implementation.
- Owner visual review after staging: left-vs-top navigation, card arrangement/colors, spacing, image crops, print layout, responsive behavior. Do not recast approved business rules as unresolved because layouts have not been seen.

## 3. Storage ownership

| Data | Location |
|---|---|
| Application code, primary customers/bookings/memberships/participants/program/payment metadata | DigitalOcean/PostgreSQL |
| Signed completed waiver files | Dedicated private **Cloudflare R2** waiver bucket only |
| Waiver object reference/hash/status/signing/expiry/coverage metadata | PostgreSQL, no duplicate signed file |
| Encrypted PostgreSQL backups | Separate dedicated private R2 backup bucket |
| Future customer documents/paper scans if authorized | Separate private R2 documents bucket, not backup/waiver bucket |
| Original unsigned waiver/templates | Separate from signed files; DigitalOcean/repository-preserved source as appropriate |
| Public logo/ad/facility images | Website assets; originals preserved |
| Private backup recovery key | Outside DigitalOcean and R2, at least two protected owner-controlled copies |

No completed signed files in Spaces, public links/directories, repository, database or duplicate DO copies. Previously suggested Spaces for documents/scans is superseded by dedicated R2 documents direction. Bucket separation and least privilege do not guarantee a provider feature exists; verify supported retention/credential controls before claiming them configured.

Random waiver object IDs, no permanent public URLs; authorize every file access and issue short-lived access. Server-only R2 credentials. Isolated test buckets and no production waiver content in staging.

## 4. Database access and server hardening

- PostgreSQL local/private, not public Internet. Administrative database access via SSH/secure tunnel, scoped least privilege.
- Generate SSH public key and explain DigitalOcean installation only when setup is authorized. Never request/store owner's DO password; any API token project-scoped and supplied securely.
- Non-root deploy user, key-only SSH, disable password/root SSH after setup, firewall only required SSH/HTTP/HTTPS, security updates, process supervision, monitoring/disk alerts, TLS renewal, sensitive-log redaction.
- Reverse proxy such as Caddy/Nginx and process management/container approach to be selected later; no Dockerfiles/Compose/reverse-proxy configs/migrations installed by this documentation PR.
- Protected per-environment server settings for secrets, never Git/chat/logs/browser. Rotate previously exposed credentials; Resend replacement is already owner-reported created, not an outstanding instruction to create another token.
- Application operational logs90days, security logs1year, business audit indefinite. Don't log card/secret/password/waiver document contents.

## 5. Backup architecture and retention

Confirmed plan (not a working backup implementation):

1. Nightly consistent PostgreSQL backup on DigitalOcean.
2. Encrypt **before upload**, fresh random encryption material per backup, stable versioned public/private recovery-key arrangement. Public encryption key may be on application server; private key not on DO/R2.
3. Upload encrypted archive plus integrity-check metadata only to dedicated private R2 backup bucket. Unique nonreused object names, verify completion/integrity and record outcome before expiring old recovery points. Securely remove temporary plaintext.
4. Keep **seven rolling nightly recovery points**, replacing older30daily planning. Keep **twelve monthly backups**.
5. Monthly restoration test in isolated nonproduction database: decrypt, restore, integrity checks, clean up, record result; alert exceptions. This must not replace production or expose real data to normal staging users.
6. Dashboard and business-email alerts for backup/upload/verification/deletion/restore failures. Dashboard is persistent fallback if email unavailable.
7. Only owner may authorize/perform production restoration, access backup controls/downloads/delete/retention settings. Staff cannot operate backups.

Private-key handling and unattended restore runner remain a **technical design gate**: true automatic decrypt tests cannot be claimed while no permitted runner/key access has been established. Propose separate protected runner or explicitly owner-assisted procedure; do not put private key on DO/R2 just to satisfy automation. At least two protected recovery-key copies in separate locations; owner reports BitLocker desktop. Password-manager/encrypted offline copy are example mechanisms, not selected products.

No fixed routine two-year rotation requirement; owner rejected it. Exposure-triggered rotation procedure and old-key retention until dependent backups expire need operational design. Never keep recovery key with the R2 encrypted archive or email it.

Proposed R2 controls subject to capabilities/cost review: upload-scoped credentials separate from retention authority, unique names, minimum required deletion rights, retention/overwrite protection if supported, separate bucket credentials, deletion failure alerts. Do not claim unsupported object versioning or upload-only permissions are established.

Owner-approved investigation preservation action can pause expiry of selected recovery points for investigation; record scope/actor and release, avoiding silent permanent suspension.

### Desktop copy

Monthly reminder with **Download now**, owner-triggered encrypted download, dated filename. Keep **two newest** desktop copies; owner manually deletes oldest. Browser download settings choose destination folder; website does not silently select folders/delete local files. Desktop copies supplement R2, not replace nightly archive or alter server retention. Keep recovery-key protection distinct from archive storage.

### Production restore proposal for operational review

Preserve current database, restore selected backup into isolated temporary database, validate, present outcome to owner, explicitly authorize replacement, audit. Owner reauthentication/confirmation appropriate to restoration must be reviewed as part of procedure; it does not reinstate rejected export reauthentication. Staff cannot restore. Reapply expired-waiver deletion/retention after recovery; historical backup metadata may naturally persist until archive expires, but no duplicate signed files are created by PG backups.

## 6. Monitoring and approval gates

Business alerts to **monkeydoplay@gmail.com**. Dashboard retains failed/bounced/unknown email and operational issues without relying on Resend being able to email itself. External uptime monitoring would detect app/server outages where Dashboard cannot run; provider/cost still to propose, not a purchased service.

Before provisioning, present exact plan/price and scoped access, SSH/public IP/DNS records, provider settings, backup-key design, monitoring and restoration instructions. Django with its ORM/migrations and PostgreSQL are now owner-approved. Custom identity/security, durable jobs and deployment packaging remain implementation work.

Before launch: functional authorized staging, actual restore evidence, sandbox results, no production test secrets/URLs, sender verification, server secrets, approved production tax rate, reconciled provider/account behavior, WCAG/browser/mobile/security/concurrency/payment/waiver/owner acceptance. Require separate written approvals for production deployment, Cloudflare DNS connection, live payments and opening bookings. Publishing the Codex development environment is not any of those approvals.
