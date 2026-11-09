# Customer self-booking and isolated functional staging

This checkpoint connects customer self-booking to the existing owner/staff workspace. Reservations remain **Setup pending**, clearly marked as tests. It does not confirm a visit or take payment. The owner selected one shared staging site: design review and booking tests use `staging.monkeydoplay.com`, with protected `/staff` sign-in. Everyone sees the same deployed design. Frozen source files remain unchanged as historical artifacts; they will no longer serve the public staging root after cutover.

## Customer and staff workflow

Enable `MONKEYDO_CUSTOMER_TEST_BOOKING=1` only in the functional environment, with `MONKEYDO_DESIGN_ONLY=0`. The default is off. Customers start at the homepage and choose a session from `/book/`. Available sessions respect the existing New York horizon, closures, play types, capacity and booking cutoffs.

The flow collects phone number and returning/new status. A current-phone match requires the approved Last Name check. A previous-phone match shows the current phone and asks the approved Yes/No question. Ambiguous matches stop for staff assistance. The new-customer choice cannot bypass an existing phone match. This is the approved matching workflow, not independent proof of identity; use fictional customer records during testing.

Customers enter attendees, play type, socks, intended payment method and optional referral, then review a server-calculated itemized quote. They can revise before submitting. The explicit test acknowledgement creates one pending reservation and immutable quote. No customer record or capacity reservation is created merely by reviewing a quote. Duplicate submissions are idempotent; final submission rechecks pricing, contact revision, availability and capacity inside a transaction. Capacity races and failed writes do not leave orphan customer records.

Authorized staff find these records in Bookings and inspect the customer/test source and quote. They can use **Cancel booking** when cancellation is wanted; this is not a required review or approval step. A customer's same-browser receipt reflects a later cancellation. Receipt access is bound to the browser flow, not a public booking ID. Staff routes remain unlinked from public navigation and enforce staff permissions.

There is no checkout payment, stored card, waiver/signature, active membership allocation, arrival workflow or customer confirmation email here. Booking-linked customer email correction/resending remains future work. Pending records reserve capacity until staff cancel them; no automatic expiry/reset job is provided. Test with fictional data. Cancellation is optional and makes the cancelled booking’s spaces available again.

## Controlled account email

`MONKEYDO_EMAIL_TRANSPORT=resend` selects the staging-only transport for existing account MFA/reset mail. It requires a private `RESEND_API_KEY` and explicit comma-separated `MONKEYDO_TEST_EMAIL_RECIPIENTS`. Every To/CC/BCC recipient must be allowlisted; sender is fixed to `bookings@monkeydoplay.com`. Resend sender/domain verification is still required. No booking confirmation is sent.

The transport has a bounded timeout, rejects redirects and does not retry uncertain deliveries. Errors omit message bodies and secrets; existing account alerts report unconfirmed delivery. Provider acceptance is not proof of inbox delivery. Automated transport tests use mocked responses; **no real Resend call or email has been made for this checkpoint**.

## One-time shared-site cutover still required

The following is an operator checklist, not an executed deployment or a command to paste without preparing the host. Keep the existing design release/database intact for recovery. Replace its public routing only after preparing and checking the functional service. There will be one public staging URL, not a second testing hostname. See [SHARED_STAGING_CUTOVER.md](SHARED_STAGING_CUTOVER.md) for the activation/recovery sequence.

1. Prepare a distinct Linux/runtime SQL user `monkeydo-functional`, migration user/SQL owner `monkeydo-functional-migrate`, and database `monkeydo_functional`. Use peer authentication. Revoke public schema CREATE and give the runtime role only required row/sequence access; it must have no schema CREATE, superuser, CREATEDB or CREATEROLE. Set migration-owner default table/sequence privileges for future migrations. Keep migration credentials inaccessible to the application service.
2. Extract the exact approved release under `/srv/monkeydo-functional/releases/`, prepare its virtualenv/static files and initial `/srv/monkeydo-functional/staging/current` link. Apply migrations through **0021** using the separate migration role, after reviewing the migration and backup procedure. Migration 0021 adds customer-test source/referral/fingerprint fields and permits a null quote actor for customer-created quotes. It does not rewrite existing quotes. Do not migrate the design database for this functional setup.
3. Put actual values from `deploy/functional.env.example` in `/etc/monkeydo/functional.env`, owned root:monkeydo-functional, mode 0640. Generate a distinct Django secret. Enter the Resend key privately on the server, never in chat, source control or command history. Allowlist the owner/recovery and intended staff test addresses. Do not copy the placeholder values or the design environment's secret.
4. With this environment loaded, create exactly one active owner interactively (`manage.py createsuperuser`), run `manage.py configure_staff_group`, and set the shared gate with `manage.py set_functional_staging_password` (hidden prompt). The owner can create staff through the existing workspace. Do not copy real customers or staff passwords from another database.
5. Install the separate `deploy/monkeydo-functional.service.example` as `monkeydo-functional.service`. Its runtime user, environment, current link and Unix socket are isolated. Replace the existing staging nginx virtual host using the example, preserving a private copy of the prior configuration and its existing TLS certificate. Do not add a duplicate server_name block. No DNS or new certificate is needed. Preserve all other web/mail/DNS records. The socket must stay private; nginx must overwrite `X-Real-IP`. Never expose the Gunicorn socket through a public TCP listener or trust arbitrary forwarded IP headers.
6. Run `manage.py check --deploy`, `manage.py migrate --check` and `manage.py functional_staging_preflight` as the functional runtime identity with its environment. Preflight checks hostname, secure cookies/proxy, owner/gate/email configuration and actual runtime database privileges; it makes no external call or data mutation. Check service startup, private gate, HTTPS, static assets and unauthorized staff access.
7. Verify real allowlisted owner MFA/reset delivery and recovery behavior privately, then run the acceptance scenarios below. No tester should receive a functional link until the gate, permissions and complete pending-reservation journey pass on the host.
8. Reinstall the updated deployment engine/wrapper from the approved release, selecting `-Target Functional`. Installation requires the functional service/current release to exist already; it does not perform this bootstrap. Thereafter updates, status and rollback can use the existing wrapper with `-Target Functional`. Default commands continue to select Design. See [DEPLOYMENT_COMMAND.md](DEPLOYMENT_COMMAND.md).

The helper checks for pending migrations and **never applies them**. Rollback restores code, Python environment and service override only, not database schema or records. Functional releases/state are separate from design releases/state. No production deployment or paid-service purchase is included.

## Acceptance and verification

Use fake contacts and distinct browser sessions for customers and staff:

- New family: choose Open Play, review/revise attendees/socks, submit, find the same amount in staff Bookings, cancel, refresh customer receipt.
- Returning family: current phone plus Last Name; wrong name stops. Previous phone plus approved current-phone confirmation. Staff contact changes invalidate an already-verified flow.
- Supervised Play: only eligible slots, no accompanying adults, cutoff and capacity enforced.
- Two customers compete for the last space; only one reservation succeeds. Duplicate confirmation creates one record. Price/closure changes between review and submit require a fresh review.
- Another browser cannot retrieve a receipt; public sessions cannot open staff pages. POST without CSRF fails. No card fields or confirmation claims appear.
- Real host only: HTTPS/private gate, owner MFA/reset delivery, staff permission isolation, new account/recovery, proxy IP buckets and code rollback smoke test. These checks remain unperformed on DigitalOcean.

Local evidence: 278 tests passed on PostgreSQL 17, including concurrent final-space/duplicate submissions, transaction rollback, privacy/CSRF and mocked mail/deployment guards. Portable PowerShell wrapper tests passed with SSH/SCP mocked. Chromium completed customer review/revision/save, actual staff sign-in/search/cancellation and updated customer receipt at 1440px and 390px, without overflow or JavaScript errors. These results do not establish actual provider delivery, Windows execution, hosted TLS or real service switching.

Terminology follow-up: the planned action is **Cancel booking**, with status **Cancelled**. The staff message/history and customer receipt now match. Existing stored cancellation values and immutable audit records are preserved; no database migration or change to fee behavior is required. All 33 staff/public booking tests passed after the wording change. The browser evidence above predates this label correction.
