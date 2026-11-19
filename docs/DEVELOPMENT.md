# Staging application development

Current baseline: the owner reports PR #27 deployed on the existing shared staging
site. Pending public/staff test reservations, customer/staff/owner controls,
scheduling and editable membership drafts are available. Confirmed visits,
card/payment/waiver integration and active memberships remain unfinished.
See [remaining-stage plan](NEXT_PHASE_REVIEW.md) and the required
[shared workflow standards](SHARED_WORKFLOW_STANDARDS.md). The next phase has not
started; this update reconciles its plan only.

## Authorization and architecture

The owner explicitly authorized staging website/database development, then explicitly approved Django after discussing alternatives and costs. Django and PostgreSQL are free software running on DigitalOcean, not additional hosting subscriptions. This supersedes the earlier documentation-only authorization boundary; original transcript evidence is unchanged.

Start with staging on one DigitalOcean server, subject to review of the actual server price before purchase. A separate production server is not needed while only developing staging. Before launch, assess whether staging and production can safely share resources. If shared, retain separate application processes, databases, secrets, provider endpoints and R2 buckets. The existing Droplet/shared staging setup is owner-confirmed; production sharing
and any new worker/backup resource requirements still need assessment.

Selected foundation:

- Python 3.12+, Django 5.2 LTS, Django ORM and versioned database migrations.
- PostgreSQL 17, transactional reservations with session-row locks; SQLite allowed only as a local convenience, never as evidence of concurrency safety.
- Server-rendered responsive HTML/CSS with original owner-supplied images. No external font/CDN dependency.
- Custom owner/staff screens; Django admin is a temporary read-only inspector, not the final administrative portal.
- WhiteNoise static assets, Gunicorn and nginx/TLS on the existing shared staging
  deployment; no second public test site.
- Account mail uses owner-configured/verified Resend. Banquest sandbox payments,
  booking/member email delivery, private R2 signatures, offsite backups and durable
  jobs remain to integrate with the next relevant workflow.

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

Available: the protected shared public website and customer pending-test booking,
Today/Bookings tables and combined filters, unified booking edits with estimates,
customer contact/search/history, owner MFA/staff permissions, pricing snapshots,
weekly/date scheduling, custom interval blocks and generation coverage, and
editable immutable membership-draft revisions. PR #27's homepage redesign was
excluded; its deployed About/play design remains. The current public flow can
write a pending test reservation; it is not confirmed checkout or payment.

Not yet implemented: confirmed ordinary/supervised setup/arrival, secure card
methods and payment/tender operations, persisted waiver evidence/coverage,
booking/member communications and reconciliation, purchased memberships/benefits,
program/party/gift-card-sale/socks-sale operations, encrypted offsite backups and
durable workers/retention/monitoring. These remain planned requirements.

`APP_ENV=staging` uses PostgreSQL, explicit hosts, private secrets, secure cookies
and the independent shared password; staff sign-in/permissions and owner MFA are
separate. Account-email inbox receipt was owner-confirmed during setup. This is
not proof that booking emails or all provider/security scenarios are accepted.
`APP_ENV=production` remains deliberately disabled pending its separate approval.

Audit records are append-only through the application manager and a PostgreSQL update/delete trigger. A privileged database administrator can still alter schema or disable triggers; least-privilege deployment roles and operational controls remain necessary.

## Provider credentials: later setup, not needed now

Before functional sandbox-payment testing, install sandbox keys in protected staging-server configuration (existing functional configuration `/etc/monkeydo/functional.env`, root-owned and
restricted to the applicable service group). Provide exact secure installation instructions at the authorized integration step.
The functional environment already exists; no Banquest key is installed by this
planning change. The older staging.env is the retained design-service config.

Reserved configuration names: `BANQUEST_API_SOURCE_KEY`, `BANQUEST_API_PIN`, `BANQUEST_TOKENIZATION_PUBLIC_KEY`, `BANQUEST_WEBHOOK_KEY`. They are placeholders, not currently wired integration settings. Only the explicitly public tokenization key may reach Banquest's browser iframe setup. Private source/PIN/webhook keys stay server-side. No raw card/CVV fields may pass through Django.

Production credentials belong in a separately protected production environment only at separately approved live-payment setup. Do not put credentials/test-card PDFs in Git, PR comments, chat, screenshots, tutorial recordings or browser-visible errors. No live keys are needed for staging.

## Next implementation sequence

1. Retain the deployed foundation and review new owner findings against shared
   requirements; do not rebuild its customer, filter, layout or scheduling rules.
2. Complete ordinary **and supervised** booking: both card-payment setup and
   alternate-tender backup-card setup, saved waivers, confirmation/delivery,
   staff arrival review/collection, cancellations and no-shows. Build Banquest
   sandbox, private R2, communications, jobs and recoverable offsite backup work
   alongside these dependencies. Ordinary admission is still collected only
   after staff arrival review. Use new reservations; label older test workflow
   records without changing their history or generating external operations.
3. Active memberships: purchases/installments, benefits and member-information
   popup/pricing in booking, renewal/addition, conversions and customer credit.
   Inherit current tables/filters/edit/history/calendar and permission patterns.
4. Remaining operational party, physical gift-card sale, standalone socks and
   club enrollment/attendance workflows, reusing the payment/waiver infrastructure.
   Clubs remain hidden publicly until owner-enabled.
5. Throughout these stages, verify security, storage/retention, backups/restores,
   worker/reconciliation recovery and resources. Finish exports/printing,
   cross-browser/accessibility, owner testing/training and production readiness.

The detailed scope and inherited UX are in [NEXT_PHASE_REVIEW.md](NEXT_PHASE_REVIEW.md)
and [SHARED_WORKFLOW_STANDARDS.md](SHARED_WORKFLOW_STANDARDS.md). At each stage,
update main/domain/development/status/test documentation together and review
cross-page effects and screenshots. Use browser ZIP plus one PowerShell deployment
block, with a release-specific reviewed schema/recovery plan. Separate paid-service
and production/live-booking approvals remain. The owner approved this order;
next-phase application development has not started.

## Historical implementation increments

The entries below record how the foundation was built. Their local-only/no-email
statements describe those checkpoints; the current status above takes precedence.

## Customer-management increment

Staff customer creation/search/contact corrections, comments, readable audit history, default permissions and temporary login delays are now implemented. See [CUSTOMER_DEVELOPMENT.md](CUSTOMER_DEVELOPMENT.md) for setup and exact limitations. Today links to the pending test-booking tools; Dashboard/security alerts and customer corrections are functional locally. No messages or payments are sent.

## Owner/staff security increment

Owner MFA/recovery, staff account controls, versioned session revocation, password reset and shared staging password/rotation are locally implemented; see [ACCOUNT_SECURITY.md](ACCOUNT_SECURITY.md). Configure real test email before hosted owner acceptance. No console/code-printing workaround or staff recovery bypass is permitted.

## Pricing and staff test-booking increment

See [BOOKING_DEVELOPMENT.md](BOOKING_DEVELOPMENT.md). After migrations, rerun `configure_staff_group` for the new booking capabilities. Pending test reservations, versioned quotes and audited count/timing changes are now implemented locally. They do not confirm bookings, allocate membership benefits or process payments.

## Owner scheduling increment

Owner calendar controls now support one-time sessions, session settings and date closures. See [SCHEDULING_DEVELOPMENT.md](SCHEDULING_DEVELOPMENT.md) for usage, concurrency controls and deferred recurring/member/notification workflows. Existing test reservations remain Setup pending. No deployment or provider operations were enabled.

## Membership draft increment

Test membership planning and persisted calendar/price history are available; rerun `configure_staff_group` after migration for the new draft capabilities. See [MEMBERSHIP_DEVELOPMENT.md](MEMBERSHIP_DEVELOPMENT.md). These are inactive draft cohorts, not completed sales or active memberships.

## Weekly schedule increment

Owners can edit weekly templates, explicitly generate/apply dated sessions and configure the booking horizon. See [RECURRING_SCHEDULE_DEVELOPMENT.md](RECURRING_SCHEDULE_DEVELOPMENT.md). Generation retains booked/manual/independent sessions; it is not a recurring worker or a public checkout activation.


## Accountant reporting foundation — November 19, 2026

The owner may defer accountant report screens until after launch. When the next
payment phase is authorized, include the [source-data requirements](ACCOUNTANT_REPORTING_FOUNDATION.md)
from its start: actual receipt/tax/fee/tender facts and dates, safe provider
references, immutable linked refunds/voids/credits/conversions and test/live
separation. The existing booking quotes/drafts are not a payment ledger and
should never be reported as income. No separate reporting server or new provider
key is required merely for this planning need. Report presentation and accounting
basis can be agreed later; basic operational export scope remains unchanged.
