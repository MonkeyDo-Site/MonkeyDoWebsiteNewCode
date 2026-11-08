# Owner scheduling controls

This checkpoint adds the owner calendar at `/staff/scheduling/`. Apply migrations normally; no extra staff permissions are required. These controls are owner-only even if a staff user has the underlying model permissions. Owner MFA remains required by the existing authentication middleware.

## Available workflow

Choose a New York date and review its sessions and reserved child/adult/supervised counts. Add a one-time ordinary session with an internal label, public/backend-only visibility, accompanied/supervised/both play type, times, and child/combined/supervised limits. Public Saturday sessions remain hidden under the approved normal public-calendar rule. Choosing public does not bypass the normal advance-booking horizon.

Edit future sessions to adjust visibility, closure and limits. New sessions cannot overlap existing sessions. Capacity cannot be reduced below existing reservations, including pending test reservations. Times and play type cannot change when booking history exists: move individual pending bookings through the existing booking tools instead. Customer notifications and confirmed-booking rescheduling/repricing remain future work. Weekly template editing/generation is now available separately; see [RECURRING_SCHEDULE_DEVELOPMENT.md](RECURRING_SCHEDULE_DEVELOPMENT.md). Earlier both/zero-supervised seed rows can be made explicitly accompanied-only without altering eligibility.

Date settings apply a date-wide closure and required private reason, or reopen a date. Closures apply to existing and subsequently created sessions on that date. Existing reservations and quotes remain unchanged. The owner calendar continues to show reserved counts; the owner must review affected bookings separately. No cancellation, fee waiver, refund or customer notification is implied. Individual session closures and date closures are independent: reopening the date does not reopen an individually closed session.

Chol Hamoed is a single date-level designation, never a slot-level setting. This stores the owner decision only; membership eligibility/price snapshots are not implemented by this checkpoint. Existing quotes are not silently repriced.

Owner edits are limited to today through two calendar years ahead, with future start times and same-day session bounds. Browser datetime inputs are interpreted in America/New_York. Django rejects ambiguous/nonexistent DST local times instead of silently choosing an offset. Existing party/exclusive session kinds are inspected on the calendar but cannot be converted through these ordinary-session controls.

## Integrity and privacy

Closure reasons and internal labels stay off the public schedule. All changes retain before/after values, actor, time and revision in the existing append-only audit log. Stale session/date submissions are rejected; there is no deletion endpoint.

PostgreSQL transaction advisory locks coordinate calendar changes with both reservation services. Reservations take a shared calendar lock before booking/session row locks; owner changes take the exclusive calendar lock first. This prevents competing sessions from overlapping and ensures a reservation waiting behind a closure checks the committed closure. Booking row/session locks and pricing history from the preceding increment remain in effect. SQLite does not establish concurrency guarantees.

## Limits and next work

Automatic affected-booking notifications, final program scheduling, membership benefit integration and public checkout remain unfinished. This checkpoint changes no DigitalOcean resources and does not deploy, send mail, charge payments or access Banquest/R2/Resend.

Weekly template generation and booking-horizon controls are documented in [RECURRING_SCHEDULE_DEVELOPMENT.md](RECURRING_SCHEDULE_DEVELOPMENT.md).
