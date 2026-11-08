# Weekly schedule and booking horizon

Owner **Scheduling → Weekly schedule** now manages weekly templates and materializes dated sessions. This extends the dated calendar; it does not enable checkout, notifications or payments.

## Templates

Migrations initialize the four approved Sunday–Friday templates: 11:30–12:45, 13:00–14:15, 14:30–15:45 and 16:00–17:15, New York local time. This creates templates only, not sessions or bookings. Existing dated sessions are not adopted or rewritten. Owners can add/edit templates, choose weekdays, visibility, accompanied/supervised/both, limits and an internal label. Overlapping active templates on the same weekday are rejected. Templates may be disabled but are not deleted.

Saving a template alone does not change dated sessions. Select templates and an inclusive date range, from today through two calendar years ahead, then use **Generate / apply dated sessions**. Only future starts are generated; past/started sessions remain untouched. Generation is explicit, not an unattended background job. Operators must generate enough dates to cover their booking horizon.

By default, generation fills missing dates and preserves all existing sessions. With **Also update untouched, unbooked generated sessions** selected, it also applies the current template to eligible sessions originally generated from that template. Disabling a template or removing weekdays closes its eligible obsolete sessions in the selected range; reactivation can reopen those generated sessions. No booking is cancelled.

Always preserved:

- Any session with booking history, even a released test booking.
- Manual per-date overrides. Saving through the dated editor ends automatic template management; its original source remains traceable.
- Independent/legacy seed sessions, including programs and overlapping one-time sessions. They are not silently adopted.
- Already-started sessions and date-wide closures. Reopening a generated session does not reopen a closed date.

Results list created/updated sessions and preserved conflicts for review. Already matching, unchanged generated sessions need no update. To change a preserved session, review it in the dated calendar and handle affected bookings individually. No notification or confirmed-booking repricing is implied.

Each generated session retains its template ID, template revision and source date. Calendar and template mutations share the existing PostgreSQL exclusive advisory lock; reservations use its shared lock. Concurrent generation cannot duplicate dated sessions. Generation and audits commit together. A validation error rolls back the batch. Ambiguous/nonexistent New York DST times fail explicitly; use another time or split the date range. Private labels remain off public pages. Saturday stays hidden under normal public-calendar rules, including explicitly public Saturday templates.

The old development-only `seed_staging` command remains idempotent, uses the same calendar lock and skips overlapping owner sessions. It is not the operational recurring generator or a reset procedure.

## Horizon

Owner **Booking horizon** accepts whole numbers 1–10. **Revert to default: 1 day** requires the explicit confirmation checkbox. Saving checks the previously displayed value, audits before/after and updates only the horizon field, preserving independent staging-security configuration. Existing bookings, quotes and dated sessions are unchanged.

The public availability logic continues to use New York calendar-day openings. Sunday opens by Friday midnight, or earlier when the selected general horizon allows it. Horizon changes do not materialize dates and do not bypass visibility, closures, capacity, supervised cutoff or Saturday hiding.

## Remaining work

Unattended generation/expiry jobs, returning a manual override to automatic management, hosted operational validation, affected-booking notifications, final program lifecycle, membership benefit integration, payments and public checkout remain unfinished. These changes deploy nothing, resize no Droplet and activate no paid service or provider operation.
