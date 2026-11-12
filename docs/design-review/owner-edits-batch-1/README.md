# First batch of backend edits — screenshot review

These JPGs use fictional local customers, bookings and dates. No changes have been deployed. Open an image and click **Download raw file** to save it.

| Screen | Desktop | Phone |
| --- | --- | --- |
| Daily sessions table | [JPG](01-owner-scheduling-desktop.jpg) | [JPG](01-owner-scheduling-phone.jpg) |
| Edit session — fixed date, editable times | [JPG](02-edit-session-desktop.jpg) | [JPG](02-edit-session-phone.jpg) |
| Date settings and inline checkboxes | [JPG](03-date-settings-desktop.jpg) | [JPG](03-date-settings-phone.jpg) |
| Weekly defaults and session generation | [JPG](04-weekly-schedule-desktop.jpg) | [JPG](04-weekly-schedule-phone.jpg) |
| Edit weekly default | [JPG](05-edit-weekly-default-desktop.jpg) | [JPG](05-edit-weekly-default-phone.jpg) |
| Booking horizon | [JPG](06-booking-horizon-desktop.jpg) | [JPG](06-booking-horizon-phone.jpg) |
| Delete confirmation and booking warning | [JPG](07-delete-weekly-default-desktop.jpg) | [JPG](07-delete-weekly-default-phone.jpg) |
| Bookings table | [JPG](08-bookings-desktop.jpg) | [JPG](08-bookings-phone.jpg) |
| Customer spelling suggestions | [JPG](09-customers-spelling-search-desktop.jpg) | [JPG](09-customers-spelling-search-phone.jpg) |
| Booking spelling suggestions | [JPG](10-bookings-spelling-search-desktop.jpg) | [JPG](10-bookings-spelling-search-phone.jpg) |
| Public booking — close surname confirmation | [JPG](11-customer-name-confirmation-desktop.jpg) | [JPG](11-customer-name-confirmation-phone.jpg) |
| Public booking — after confirmation | [JPG](12-customer-booking-after-confirmation-desktop.jpg) | [JPG](12-customer-booking-after-confirmation-phone.jpg) |

Table closeups: [Daily sessions](01-owner-scheduling-detail.jpg) · [Bookings](08-bookings-detail.jpg)

The weekly screenshot includes an inactive evening default to show that it stays available for owner editing but is absent from generation choices. The deletion screenshot warns about its one existing fictional booking. The public confirmation screenshot deliberately does not disclose the stored surname or email; those appear only after confirmation.

Tables scroll within their own regions on small screens. The Owner scheduling parent link stays visible while scrolling. Waiver and membership columns are intentionally deferred.

The [implementation and deployment notes](../../OWNER_EDITS_BATCH_1.md) describe behavior, history preservation and migration 0022. One additive database migration is needed before the existing Functional deployment command. No PR or deployment has been performed; these screenshots are for review first.

Validation: all **308 PostgreSQL-backed tests passed**. Ruff lint/format checks and desktop/phone browser checks passed.

Subsequent owner-approved change: Bookings now has a linked Booking ID column instead of the Open booking column shown in these earlier screenshots. The owner chose to review that final change on staging.
