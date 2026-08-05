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

## 2. Database provider

Recommended provider discussed: Neon Postgres.

Still open:

- Final database hosting provider.
- Production database plan.
- Backup/retention settings.
- Preview/staging database strategy.
- Database access policy.

## 3. Hosting provider

Recommended provider discussed: Vercel.

Still open:

- Final hosting provider.
- Production domain.
- DNS setup.
- Environment variable management.
- Preview deployment strategy.

## 4. Email provider

Recommended provider discussed: Resend.

Still open:

- Final email provider.
- Sender domain.
- DNS records.
- Production API key.
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

Still open:

- Final legal waiver text.
- Waiver version.
- Parent/guardian signature language.
- Whether adult participants need separate language.
- Whether waiver covers one visit or multiple visits.
- Whether paper/in-person waiver records require file upload.

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

- Whether the system should store only the admin confirmation that the waiver was signed.
- Whether the system should support upload of a scanned/photo waiver copy.
- Whether in-person waiver signing will be paper-based or device-based.

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
