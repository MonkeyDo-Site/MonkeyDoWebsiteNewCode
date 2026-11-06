# Staging application development

## Authorization and architecture

The owner explicitly authorized staging website/database development, then explicitly approved Django after discussing alternatives and costs. Django and PostgreSQL are free software running on DigitalOcean, not additional hosting subscriptions. This supersedes the earlier documentation-only authorization boundary; original transcript evidence is unchanged.

Start with staging on one DigitalOcean server, subject to review of the actual server price before purchase. A separate production server is not needed while only developing staging. Before launch, assess whether staging and production can safely share resources. If shared, retain separate application processes, databases, secrets, provider endpoints and R2 buckets. No provisioned DigitalOcean server is claimed by this increment.

Selected foundation:

- Python 3.12+, Django 5.2 LTS, Django ORM and versioned database migrations.
- PostgreSQL 17, transactional reservations with session-row locks; SQLite allowed only as a local convenience, never as evidence of concurrency safety.
- Server-rendered responsive HTML/CSS with original owner-supplied images. No external font/CDN dependency.
- Custom owner/staff screens; Django admin is a temporary read-only inspector, not the final administrative portal.
- WhiteNoise for public static assets and a WSGI entry point for later Gunicorn hosting. Reverse proxy/TLS setup remains to implement and review.
- No payment SDK, external email delivery, signed-file storage or worker has been enabled. These will be integrated with Banquest sandbox, Resend, private R2 and durable jobs in subsequent increments.

## Running locally

From the repository root:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_staging
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

The local fallback uses ignored `local.sqlite3`, with no real customer data. The seed command creates only test session rows, Sunday–Friday at the four approved times, and is idempotent: existing sessions/settings/bookings are preserved. It is not a reset or backup procedure. No default user/password is seeded. Create local credentials interactively and do not share them in chat or commit them.

The server binds to loopback only. It is not a hosted staging deployment. In development the public page previews can be viewed without logging in. Today requires login and the `core.view_booking` permission on an active staff user. A superuser can inspect all foundation records, but record edits are disabled in the inspector until audited workflows exist.

### PostgreSQL

Set `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST` and `POSTGRES_PORT` in the process environment, then use the same migrate/seed/test commands. Django does not automatically load `.env` files. `.env.example` documents variable names without credentials.

The database role used by Django's test runner needs permission to create its disposable test database. That privilege is for local/CI testing, not the eventual deployed application role. Never point tests or seed commands at production. CI uses an isolated PostgreSQL 17 service and artificial data. For the same formatter/linter checks, install `requirements-dev.txt` and run `ruff check .` and `ruff format --check .`.

```sh
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py test
```

The PostgreSQL tests verify concurrent requests for the last child place, transaction rollback and database-level audit protection. SQLite deliberately skips PostgreSQL-only checks. Do not interpret a SQLite-only test pass as a PostgreSQL pass.

## Current implementation boundary

Available: five public page previews, shared navigation/test banner, original logo/facility photography, New York schedule preview, customer/session/booking/settings/audit tables, Django session authentication, read-only Today/inspector, internal capacity reservation primitive and automated tests.

The internal reservation function is not a finished confirmed-booking workflow. It is not exposed publicly and cannot charge a card, save a waiver, send an email or calculate membership benefits. No public write endpoint exists. Checkout is visibly disabled. It must be integrated with immutable pricing revisions, payment/waiver state, benefit reservations and confirmation operations before customer booking is enabled.

Not yet implemented: custom staff account lifecycle and full permission matrix; owner MFA/recovery; outbound owner security emails; immediate permission/session revocation; shared staging access password/rotation separate from staff login; public returning-customer lookup and booking-linked confirmation resends; administrative edits/overrides/rescheduling; pricing/payment/tender ledgers; membership cohorts; clubs/parties workflows; waivers/R2; email/Resend; durable jobs; backups/restores/monitoring. These remain approved requirements, not dropped scope.

`APP_ENV=staging` requires PostgreSQL, explicit allowed hosts and a strong private Django secret, switches on secure cookies/HTTPS redirection and places page previews behind active-staff login. That temporary gate does not implement the final shared staging password or owner MFA. Complete and test the security/hosting controls before opening a hosted staging site for acceptance. `APP_ENV=production` deliberately fails startup; production activation is separate work and approval.

Audit records are append-only through the application manager and a PostgreSQL update/delete trigger. A privileged database administrator can still alter schema or disable triggers; least-privilege deployment roles and operational controls remain necessary.

## Provider credentials: later setup, not needed now

Before functional sandbox-payment testing, install sandbox keys in protected staging-server configuration (planned location `/etc/monkeydo/staging.env`, readable only by the deployment/application account). Exact installation commands and ownership will be provided with the server setup. No such file has been installed by this increment.

Reserved configuration names: `BANQUEST_API_SOURCE_KEY`, `BANQUEST_API_PIN`, `BANQUEST_TOKENIZATION_PUBLIC_KEY`, `BANQUEST_WEBHOOK_KEY`. They are placeholders, not currently wired integration settings. Only the explicitly public tokenization key may reach Banquest's browser iframe setup. Private source/PIN/webhook keys stay server-side. No raw card/CVV fields may pass through Django.

Production credentials belong in a separately protected production environment only at separately approved live-payment setup. Do not put credentials/test-card PDFs in Git, PR comments, chat, screenshots, tutorial recordings or browser-visible errors. No live keys are needed for staging.

## Next implementation sequence

1. Finish staff identity/security/settings controls and audited customer records before hosted access.
2. Implement versioned pricing/tax/policy snapshots, reservation lifecycle and ordinary booking/arrival workflows.
3. Add membership cohorts, benefit/calendar rules, renewals/conversions and customer credit.
4. Add supervised play, clubs/attendance, parties, physical gift-card tender and socks workflows.
5. Integrate Banquest sandbox, private R2 signatures, Resend and durable operations; verify outcome-unknown and duplicate handling.
6. Implement and demonstrate backups/restoration, acceptance testing, owner training and infrastructure handoff.

See [STAGING_TEST_PLAN.md](STAGING_TEST_PLAN.md) for acceptance coverage and [BUILD_STATUS.md](BUILD_STATUS.md) for actual verification evidence. Changes remain reviewable through PRs. Development authorization persists; production deployment, DNS, live payments, opening bookings and paid provisioning retain their approval boundaries.

## Customer-management increment

Staff customer creation/search/contact corrections, comments, readable audit history, default permissions and temporary login delays are now implemented. See [CUSTOMER_DEVELOPMENT.md](CUSTOMER_DEVELOPMENT.md) for setup and exact limitations. Today remains read-only for booking operations; Dashboard/security alerts and customer corrections are functional locally. No messages or payments are sent.
