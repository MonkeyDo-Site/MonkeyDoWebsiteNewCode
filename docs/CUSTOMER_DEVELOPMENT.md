# Customer records and login protection increment

This increment adds functional staff-only customer operations to the local staging application. It does not deploy a server or enable public checkout, payment, waiver or email integrations.

## Implemented customer operations

- Customer list/search and creation, Last Name-only records, database-generated six-digit display IDs, normalized current/previous phones, current/previous emails and Family/Day Camp type.
- Search by Last Name, customer ID, current/previous email/phone and authorized comments, including phone punctuation normalization inside comments. Results label the matched fields. Public returning-customer verification remains separate future booking work.
- Customer detail cards: information, waiver placeholder, comments, one expandable Bookings card with the first booking today, additional today bookings and always-visible upcoming/previous counts. No waiver coverage is claimed until actual waiver records are integrated.
- Contact corrections ask the approved Yes/No question on a phone change. Yes moves the old current number into Previous phone; No preserves the existing Previous phone even when returning to the same number. Displaced previous phone preservation in comments remains manual. Automatic before/after audit still records corrections.
- Email changes move current email to Previous email. A displaced older Previous email is preserved in an automatically dated, staff-visible system comment. That history comment is immutable through the correction UI.
- Owner-only previous-phone correction allows an old reference to be resolved before another customer uses the number. Cross-customer current/previous phone conflicts cannot be silently reassigned. PostgreSQL serializes contact-ownership changes; its unique current-phone and normalized-phone constraints provide additional integrity checks.
- Explicit revision checks reject stale customer/comment edits rather than silently overwriting another staff member's changes.
- Staff comments and edits preserve original author, timestamps, old/new text and correction actor in append-only audit. Normal comments are editable with permissions; no deletion endpoint is exposed. History shows readable before/after information.
- Customer/comment changes and their audit entries commit atomically. A failed audit write rolls back the customer operation.

**Email boundary:** updating a contact does not send a confirmation yet. The UI states this explicitly. Affected-booking-only resend/delivery handling will be connected with the booking/email workflow, not replaced by a bulk resend or a success message without delivery.

## Permissions and local staff setup

Run migrations, then:

```sh
.venv/bin/python manage.py configure_staff_group
```

This idempotent command configures the `MonkeyDo Staff` group with view/create/change customer, view/add/change comments, customer correction-history and read-only booking-view permissions. It creates no user or password and preserves separate individual-account grants. No export, deletion, pricing override, security-alert resolution or backup permissions are granted.

Every route and mutation service enforces active staff status and the relevant capability. Comment read permission also governs comment search/history/edit disclosure. Customer type and previous-phone reassignment are owner-only. In this increment the owner is represented by the local Django superuser; final single-owner onboarding, staff-account lifecycle and nonreused usernames remain to implement. Do not create real production owner/staff identities for this local checkpoint.

Today and Dashboard are separate. Today remains read-only for booking/arrival/payment actions and links to permitted customer records. Dashboard contains persistent owner-only security alerts; payment/email monitoring is not yet connected. Reviewing an alert is an owner-only, CSRF-protected POST with audit.

## Login protection

The application staff form is the sole password endpoint. `/admin/login/` redirects to it, so the temporary database inspector does not bypass throttling. Nonstaff users cannot sign in through that form.

- Account bucket starts delays after five failed credential checks: 1, 2, 4 seconds and so on, capped at five minutes.
- Network bucket starts delays after 25 failed checks across usernames, using the connection's `REMOTE_ADDR`. Arbitrary visitor forwarding headers are not trusted.
- Counters reset after 15 minutes without a failed check; a successful sign-in clears its account failures. There is no permanent automatic account lockout.
- Unicode-normalized/case-folded account buckets prevent equivalent username spellings from bypassing the delay. Unknown usernames get the same temporary-delay behavior; raw unknown usernames/passwords are not persisted in bucket keys.
- Blocked requests return HTTP 429 plus Retry-After without verifying a password. Network-blocked requests do not create additional username buckets.
- PostgreSQL row locks serialize concurrent checks. Ten account failures or fifty network failures in the active window create an owner Dashboard alert and audit fact. Known existing account usernames may identify an alert; raw submitted unknown usernames are not stored.

Remaining security work: owner email MFA/secondary recovery/offline codes, password-reset delivery, full staff management/session revocation and username archival, shared staging password management/90-day rotation, security log/bucket retention jobs and outbound owner security emails. Existing 12-hour session settings remain a foundation, not proof of all session requirements. Hosted preview still requires the reviewed access/TLS/origin controls. Full operational staging acceptance is not complete.

When nginx/Cloudflare are introduced, real-client-IP trust must be explicitly reviewed before relying on network-level distinctions. Current shared proxy addresses would otherwise share a bucket. No header trust is silently enabled by this increment.

## Verification

- All 76 tests pass on disposable local PostgreSQL 17, including concurrent contact creation, stale-edit rejection, six concurrent failed logins, audit rollback, permission/CSRF checks, contact history and database constraints.
- Local Chromium: actual staff sign-in, create customer, correct email, add comment, inspect history and normalized-phone comment search passed. List/detail/edit/history/Dashboard rendered at 1440px and 390px without horizontal overflow or browser errors. Artificial data only.
- Schema migrations are additive. Original logo/photos, approved source PDF and standalone waiver HTML are unchanged. No provider credentials, card details or real customer records are committed.
