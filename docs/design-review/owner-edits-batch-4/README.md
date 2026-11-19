# Fourth batch — customer booking page only

These are screenshots of the actual local implementation with fictional data.
Only the redesigned customer booking page is shown, per the owner's request.
Other staff/matching changes are included in the draft PR for testing after the
approved deployment. Hosted staging has not changed.

| Booking-page state | Desktop | Phone |
| --- | --- | --- |
| Open Play — four quantity fields left, estimate/payment right | [Desktop JPG](01-booking-open-play-desktop.jpg) | [Phone JPG](01-booking-open-play-phone.jpg) |
| Supervised Play — adults/babies zero and locked | [Desktop JPG](02-booking-supervised-play-desktop.jpg) | [Phone JPG](02-booking-supervised-play-phone.jpg) |
| Open-only session — Supervised choice visible but unavailable | [Desktop JPG](03-booking-open-only-session-desktop.jpg) | [Phone JPG](03-booking-open-only-session-phone.jpg) |
| Supervised-only session — Open choice visible but unavailable | [Desktop JPG](04-booking-supervised-only-session-desktop.jpg) | [Phone JPG](04-booking-supervised-only-session-phone.jpg) |

Open an image, then use GitHub's **Download raw file** button to save it.
The draft PR can receive your comments and updated screenshots without creating
another PR. It remains a draft until the booking-page review is approved.

The estimate excludes processing fees and tax; final Payment Details retains
both when applicable. No card is collected and no real payment is enabled.
Only public forms auto-lock supervised adult/baby counts; staff keep validation.
Homepage/About imagery and layout are unchanged.

[Implementation/branch rules](../../OWNER_EDITS_BATCH_4.md) ·
[Browser and image evidence](verification.json)


Latest image-review revision: the narrower green panel aligns left with a clear
120px desktop gap before the outside cards. Family/contact links precede Your Group
and Choose play type. Start again is removed from Session Details only. Four inputs stack left with explicit quantity labels and separate
age guidance; the estimate is upper right, payment/Continue bottom right. All
eight JPGs reflect this revision. The 41 affected public-booking tests and browser
checks passed; the PR remains a draft for image approval.
