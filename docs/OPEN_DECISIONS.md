# MonkeyDo Open Decisions

Documentation-only checkpoint created on 2026-08-05. This file lists items that are not yet finalized. Unresolved items must not be treated as decided during implementation.

## 1. Payment processor

Recommended provider discussed: Stripe.

Still open:

- Final approval of payment processor.
- Stripe account creation/verification.
- Final Stripe pricing/fees confirmation from the active account.
- Stripe webhook configuration.
- Final card-saving and delayed-charge consent wording.
- Final phone consent script for owner-entered phone bookings.
- Final handling for charges requiring additional authentication.

No payment workflow should be claimed production-ready until the provider account, credentials, webhook secrets, approved consent wording, and test-mode validation are complete.

## 2. Database operations

Decision confirmed: PostgreSQL will initially run on the same DigitalOcean VPS as the application to reduce initial cost. DigitalOcean Managed PostgreSQL remains a possible future upgrade.

Still open:

- Backup/retention settings.
- Off-VPS encrypted backup destination.
- Restore-test schedule and responsible operator.
- Preview/staging database strategy.
- Database access policy.

## 3. Hosting provider

Decision confirmed: use a DigitalOcean VPS/Droplet for website and backend hosting.

Confirmed:

- The DigitalOcean account supports Droplets, Managed PostgreSQL, backups/snapshots, and Spaces.
- The account currently has free credit; paid billing will be activated when needed.
- New York is the preferred region.
- The production domain is being purchased.
- The external domain provider will manage DNS and point it to DigitalOcean.

Still open:

- DigitalOcean account access or scoped API token.
- Final production domain name.
- Exact DNS records and timing for the domain-provider change.
- Droplet size.
- Backup/snapshot preference.
- Environment variable management.
- Preview/staging deployment strategy.
- Temporary test-access method before the production domain is connected (public IP or configured temporary hostname).

## 4. Email provider

Decision confirmed: use Resend for transactional email. The owner has created the Resend account.

Security prerequisite:

- Completed: the owner revoked the API credential disclosed during planning and created a replacement.
- Transfer the replacement through a secure secret-management channel; do not place it in chat, source control, documentation, logs, screenshots, or client-side code.
- Store the replacement only as a server-side environment variable or deployment secret.

Still open:

- Sender domain.
- DNS records.
- Secure installation of the already-created replacement production API credential.
- Confirmation email wording approval.
- Reminder email wording approval.
- Delivery/retry policy.

## 5. Text/SMS provider

Recommended provider discussed: Twilio.

Still open:

- Final SMS provider.
- Twilio account setup.
- SMS-capable number or messaging service.
- A2P 10DLC registration if required.
- SMS opt-in wording.
- SMS opt-out wording.
- Confirmation text wording.
- Reminder text wording.
- Whether SMS is enabled at launch.

No SMS workflow should be claimed production-ready until account setup, compliance approval, credentials, and final message wording are complete.

## 6. Final cancellation and no-show policy

Still open:

- Final cancellation policy wording.
- Cancellation deadline/window.
- Cancellation fee.
- No-show fee.
- Refund policy.
- Exceptions.
- Whether cancellation/no-show fees are taxable.
- Final customer consent wording.
- Activation date.

Cancellation-fee and no-show-fee charging must remain disabled until final wording, amounts, rules, and consent language are supplied and approved.

## 7. Final waiver wording

The original PDF is present in the current checkout at `docs/waivers/source/MD Waiver (1).pdf`. Its readable text and SHA-256 checksum have been verified, and it remains a draft/reference until legal approval. The confirmed validity period is one full year from the signing timestamp.

Still open:

- Final legal approval of the waiver and electronic-signature workflow by qualified New Jersey counsel.
- Counsel confirmation of the approved production waiver version and final user-facing version label.
- Counsel confirmation of the approved adult-participant and parent/legal-guardian language.
- Counsel confirmation of the approved seven-years-after-expiration retention period, particularly for records concerning minors.

Do not launch live booking with placeholder waiver wording.

## 8. Zelle business information and payment deadline

Still open:

- Business Zelle email, phone number, or Zelle Tag.
- When Zelle payment is due.
- Exact Zelle instruction wording.
- Whether Zelle bookings expire if not paid by a deadline.
- Operational process for duplicate payment review and refund handling.

Do not invent Zelle details.

## 9. Waiver storage for in-person signatures

The owner wants to check a box on the booking screen after the waiver is signed in person.

Still open:

- Whether a scanned/photo paper waiver upload should be added after initial launch. Initial launch records only the audited completion checkbox and does not record minor names from paper waivers.

## 10. Production legal/policy review

Still open:

- Legal approval for waiver.
- Legal approval for cancellation/no-show policy.
- Legal approval for card-saving and later-charge consent.
- Legal approval for phone consent script.
- Legal approval for SMS opt-in/opt-out text.

## 11. Domain and branding assets

Still open:

- Production domain name.
- Final high-resolution brand assets for implementation.
- Whether “Every little monkey needs a jungle” may be used as a main homepage headline.
- Whether “designed by moms and professional therapists” may be used on the website.
- Whether “Go Bananas Here” may be used as a playful graphic accent.

## 12. Refund workflow

Still open:

- Whether refunds should be issued directly through the admin dashboard.
- Whether refunds should be recorded manually at first.
- Who may approve refunds.
- Refund notification wording.

## 13. Card removal policy

Still open:

- Whether backup card removal after cash/check/Zelle payment should be manual or automatic.
- Whether owner can remove card before payment is received under any exception.
- Exact card removal wording and audit reason requirements.

## 14. Staff/admin roles

Still open:

- Whether there will only be one owner account.
- Whether additional staff accounts are needed.
- Whether role levels are needed, such as owner, admin, staff, or read-only.
- Whether multi-factor authentication is required at launch.
