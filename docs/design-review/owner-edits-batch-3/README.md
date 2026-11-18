# Third batch — desktop and phone review images

**For owner review before PR and deployment.** These are screenshots of the
working local implementation with fictional test data. The staging website has
not changed. Earlier galleries remain unchanged.

Click **Desktop JPG** or **Phone JPG** to open an image in GitHub. Use the image
page's **Download raw file** button to save it. Full-page images can be tall;
02 and 03 are convenient homepage section close-ups.

Suggested first review: **02–03** (homepage), **15** (schedule timing coverage),
**18–21** (custom sessions/reopening), and **27–29** (booking estimate/completion).
Use the screen number when sending comments; screenshots with instructions also
remain welcome.

| Screen | What to review | Desktop | Phone |
| --- | --- | --- | --- |
| 01 | Homepage — complete compact layout | [Desktop JPG](01-homepage-desktop.jpg) | [Phone JPG](01-homepage-phone.jpg) |
| 02 | Homepage — compact 2×2 About areas | [Desktop JPG](02-homepage-about-desktop.jpg) | [Phone JPG](02-homepage-about-phone.jpg) |
| 03 | Homepage — smaller play cards | [Desktop JPG](03-homepage-play-desktop.jpg) | [Phone JPG](03-homepage-play-phone.jpg) |
| 04 | Bookings — default year and compact Clear dates | [Desktop JPG](04-bookings-default-year-desktop.jpg) | [Phone JPG](04-bookings-default-year-phone.jpg) |
| 05 | Bookings — no date restriction and Brawn search | [Desktop JPG](05-bookings-all-history-typo-desktop.jpg) | [Phone JPG](05-bookings-all-history-typo-phone.jpg) |
| 06 | Today — session dropdown | [Desktop JPG](06-today-session-filter-desktop.jpg) | [Phone JPG](06-today-session-filter-phone.jpg) |
| 07 | Customers — bnot/bnos miriam matching | [Desktop JPG](07-customers-word-typo-desktop.jpg) | [Phone JPG](07-customers-word-typo-phone.jpg) |
| 08 | Customers — School filter | [Desktop JPG](08-customers-school-filter-desktop.jpg) | [Phone JPG](08-customers-school-filter-phone.jpg) |
| 09 | Create customer — School type | [Desktop JPG](09-school-customer-form-desktop.jpg) | [Phone JPG](09-school-customer-form-phone.jpg) |
| 10 | Membership form — typo-aware customer picker | [Desktop JPG](10-membership-customer-typo-picker-desktop.jpg) | [Phone JPG](10-membership-customer-typo-picker-phone.jpg) |
| 11 | Add booking — date/session picker and owner closure | [Desktop JPG](11-add-booking-date-and-session-desktop.jpg) | [Phone JPG](11-add-booking-date-and-session-phone.jpg) |
| 12 | Edit booking — date/session picker and estimate | [Desktop JPG](12-edit-booking-date-and-estimate-desktop.jpg) | [Phone JPG](12-edit-booking-date-and-estimate-phone.jpg) |
| 13 | Date settings — backend-only date | [Desktop JPG](13-backend-only-date-desktop.jpg) | [Phone JPG](13-backend-only-date-phone.jpg) |
| 14 | Weekly schedule — coverage summary | [Desktop JPG](14-weekly-coverage-summary-desktop.jpg) | [Phone JPG](14-weekly-coverage-summary-phone.jpg) |
| 15 | Weekly schedule — generated timing ranges | [Desktop JPG](15-generated-timing-ranges-desktop.jpg) | [Phone JPG](15-generated-timing-ranges-phone.jpg) |
| 16 | Add weekly default — checked means closed | [Desktop JPG](16-weekly-default-closed-control-desktop.jpg) | [Phone JPG](16-weekly-default-closed-control-phone.jpg) |
| 17 | Bulk weekly editing — consistent closure controls | [Desktop JPG](17-edit-weekly-schedule-controls-desktop.jpg) | [Phone JPG](17-edit-weekly-schedule-controls-phone.jpg) |
| 18 | Custom session — preview affected slots | [Desktop JPG](18-custom-session-review-desktop.jpg) | [Phone JPG](18-custom-session-review-phone.jpg) |
| 19 | Custom session — linked blocking bookings | [Desktop JPG](19-custom-session-booking-conflicts-desktop.jpg) | [Phone JPG](19-custom-session-booking-conflicts-phone.jpg) |
| 20 | Custom session — explicit reopening controls | [Desktop JPG](20-custom-session-reopen-controls-desktop.jpg) | [Phone JPG](20-custom-session-reopen-controls-phone.jpg) |
| 21 | Cancel booking — reopening choice | [Desktop JPG](21-cancellation-reopen-choice-desktop.jpg) | [Phone JPG](21-cancellation-reopen-choice-phone.jpg) |
| 22 | Public booking — Canadian/ten-digit phone wording | [Desktop JPG](22-phone-validation-wording-desktop.jpg) | [Phone JPG](22-phone-validation-wording-phone.jpg) |
| 23 | Public booking — new-customer continuation and back link | [Desktop JPG](23-new-customer-continuation-desktop.jpg) | [Phone JPG](23-new-customer-continuation-phone.jpg) |
| 24 | Public booking — details ready, not saved early | [Desktop JPG](24-new-customer-details-ready-desktop.jpg) | [Phone JPG](24-new-customer-details-ready-phone.jpg) |
| 25 | Public booking — email recovery | [Desktop JPG](25-email-recovery-desktop.jpg) | [Phone JPG](25-email-recovery-phone.jpg) |
| 26 | Public booking — matching family confirmation | [Desktop JPG](26-email-family-confirmation-desktop.jpg) | [Phone JPG](26-email-family-confirmation-phone.jpg) |
| 27 | Public booking — live pretax estimate and play information | [Desktop JPG](27-live-estimate-and-play-info-desktop.jpg) | [Phone JPG](27-live-estimate-and-play-info-phone.jpg) |
| 28 | Public booking — final tax-inclusive details | [Desktop JPG](28-final-payment-details-tax-desktop.jpg) | [Phone JPG](28-final-payment-details-tax-phone.jpg) |
| 29 | Public booking — rose completion sentence | [Desktop JPG](29-completion-rose-message-desktop.jpg) | [Phone JPG](29-completion-rose-message-phone.jpg) |

## Evidence and limits

58 JPGs at 1440px and 390px. The browser walkthrough checks automatic filters,
dated session choices, typo-aware pickers, custom previews/conflicts, email/name
recovery, live estimate changes and final pending-test completion. It records no
JavaScript errors or document overflow. Additional 320px and staff-permission
checks passed. [Verification record](verification.json).

The About areas are two across/two down on desktop, as clarified. Images are
loaded before capture and use the approved existing assets. Phone layouts stack
content and let wide staff tables scroll horizontally. Current tax remains on
final Payment Details, not the new live estimate.

No real bookings, payments, card setup, signed waivers, active memberships,
provider delivery, hosting changes or deployments were performed. Confirmed
customer visits remain unfinished. [Implementation and migration notes](../../OWNER_EDITS_BATCH_3.md).
