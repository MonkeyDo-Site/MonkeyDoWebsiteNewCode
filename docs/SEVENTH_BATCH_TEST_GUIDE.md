# Seventh batch: post-deployment testing guide

For PR #33, after the deployment command reports success at staging.monkeydoplay.com. This guide includes the final screenshot-review changes. Use new test bookings, fictional participants and Banquest sandbox cards. For email checks, use an inbox you control. The site remains sandbox-only; ordinary admission is collected after staff review at arrival.

## 1. One-page arrival

Open an upcoming integrated booking and select Start arrival. Children, Adults, Babies and Grip socks appear in one desktop row and wrap on a phone. Active customer waivers and Sign waiver now appear on the same page as the cream Visit payment details box and actual-payment selection.

Change counts and socks. The itemized price, original/adjusted comparison, Zelle already received and remaining payment/refund should follow the changes. Previewing must not record arrival or collect money. The final button describes the selected action and amount; only clicking it confirms arrival and the payment action. Cash/check receipt dates default to the actual recording day without an extra date input.

## 2. Paper waivers entered during arrival

Check Paper waivers signed. The signing date, signing adult, Parent/Legal guardian and covered-minor fields expand below it. Record one adult per entry using the actual paper signing date. Parent entries require minors' first names, one per line; Legal guardian entries require first and last names. Adult-only visits use the same form, with relationship/minor names blank when applicable.

Save paper-waiver record. The new entry appears in Active customer waivers, without changing attendee counts or actual-payment choice. Until paper details are saved or the checkbox is cleared, final arrival is disabled. Invalid names/dates produce an inline error and do not save a waiver or confirm arrival. A repeated save must not duplicate the record.

Select Yes for coverage only after checking everyone in this booking. Final arrival saves this coverage confirmation, staff actor and time. Waiver history for this booking expands saved waiver records; the staff coverage confirmation is saved separately and is not displayed inside that dropdown.

## 3. Paper-waiver reuse and original evidence

Check customer history, staff waiver search and another booking for the same customer. A valid named paper waiver is reusable for one year under the same coverage rules as electronic evidence. It must be valid for the appointment date. Staff distinguish Signed paper from Signed electronically; public summaries do not distinguish the medium. Names in displayed summaries are capitalized, while original signed evidence remains unchanged. Earlier unnamed paper marks are retained but are not converted into invented named signatures.

## 4. Record advance Zelle

On an upcoming booking's Payment card, choose Record Zelle received. Enter the verified bank amount, actual bank receipt date and sender, then confirm the money was received. This must not mark the booking arrived, charge its card or treat the receipt as a finalized visit invoice. Record only transfers actually received; there is no automatic bank verification.

The upcoming booking shows the receipt and its date/sender. Recording the same submitted request twice must not count it twice. A separate additional bank transfer can be recorded as a separate receipt. Before arrival, empty generic money-received/unpaid panels should not create confusing zero totals.

## 5. Partial Zelle plus cash or card

Suggested example using the current sandbox pricing: book 3 children, 2 adults and 1 pair of socks with cash expected. The original estimate is $55.29. Record $10.00 Zelle before arrival. At arrival reduce children to 2. The revised total is $42.30, including the existing $3 partial cancellation fee.

Choose cash for the remainder: the final action should record only $32.30 cash alongside the already-recorded $10.00 Zelle. After arrival the Payment card should show Payment status: Paid and Total received: $42.30, followed by the separate cash and Zelle entries. It should not show a standalone Zelle-only headline or a $0 unpaid balance.

Repeat on another booking using the card on file for the remainder. Review the applicable card fee/tax on that card-funded portion. Do not collect the original full visit amount again. A pending or declined card amount is not included in Total received. Choosing Apply recorded Zelle when too little Zelle has been recorded should require another verified transfer or another permitted remainder method.

## 6. Zelle overpayment and manual refund

Record $55.29 Zelle for the original example, then reduce to 2 children at arrival. Expect $42.30 adjusted total and $12.99 Refund due through Zelle. Confirm arrival using recorded Zelle. The system calculates the refund; it does not send it.

The owner Dashboard should retain a refund notice linked to the booking. After returning $12.99 manually through Zelle, use Record completed refund on the booking and confirm the actual return. The notice should disappear. Total received then says after refunds and excludes the actual refunded amount. Opening the refund screen or calculating the amount alone must not mark it completed.

## 7. Prepaid cancellation and no-show

Use separate upcoming Zelle-prepaid bookings. Cancel one with the applicable fee and another with no fee. Record a no-show only after the session starts. Each action should reconcile the actual prepayment against the selected fee and identify the remaining manual refund. A no-fee cancellation returns the full unapplied prepayment.

Each cancellation/no-show asks Send customer email? with explicit Yes/No and no preselected answer. Choose Yes to test the notice and No to verify no customer notice is sent. Emails must accurately distinguish amounts received, pending charges and refunds still due; a calculated refund must not be described as sent. Owner pricing and complimentary rules remain as previously agreed.

## 8. Original amount and price adjustment

Check the arrival preview, Edit booking before saving and completed booking details. Changed prices show Original booking total, grouped added/removed admissions or socks, separate cancellation fee, tax/card-fee adjustment where applicable, and one Adjusted total. Original means the first saved booking quote, even after multiple edits.

For the example: $55.29 minus $15.00 admission, plus $3.00 cancellation fee, minus $0.99 tax equals $42.30. Both additions and removals remain visible when they offset each other. Unchanged prices need no extra comparison. Existing price history remains intact. These displays do not themselves create fees or payments.

## 9. Owner special price and complimentary bookings

Use Edit pricing to owner pricing or complimentary booking on an upcoming booking. A special price covers admissions only; socks remain separate. Changing attendee counts prompts the owner to retain or adjust that agreed price, without an automatic cancellation fee. Ordinary bookings must not show an empty special-price notice. Staff cannot use owner-only pricing controls.

## 10. Completed booking details

After arrival, confirm Saved price breakdown and the accepted actual/adjusted total. Amounts align right. Payment and Waivers cards are side by side on desktop and stack on phones. Total received combines successful funds once, including advance Zelle; failed/pending card operations do not count as received. Unreturned excess remains received until its actual refund is recorded. Unpaid balance appears only when money is still owed. Original payment operations and corrections remain in history.

On Edit booking, Cancel returns to booking details without saving edits; it does not cancel the reservation. Actual cancellation remains a separate explicit booking action.

## 11. Owner supervised-play exception

Edit an Open-Play-only booking as owner and choose Supervised Play with valid supervised attendee counts. The second exception checkbox must not appear on the ordinary edit screen or merely because the first checkbox is selected.

Submit the reviewed change without an exception. Expect: This session is marked as open play only. Do you want to change this booking only to supervised play? Only then should the owner exception checkbox appear, unchecked. Explicitly approve it and save. The booking changes; the session's public play mode and other bookings do not. A previously approved exception stays with its booking/session.

Also check the approved exception for zero supervised allocation or after the supervised cutoff but before session end. Session closure/end and unrelated child/combined-capacity restrictions still apply. Non-owner staff cannot approve the exception.

## 12. Child, total and supervised capacity

On staff edits, exceed a configured limit. Owners see a short reminder using actual capacity and the count already booked, excluding the booking currently being edited. Example: The child capacity for this session is 35, of which 30 slots are already booked. Check the owner override checkbox to proceed. The general capacity override remains explicit and owner-only. Staff who lack that control are directed to the owner. The warning spans the edit form width.

At arrival, unexpected attendees that exceed capacity show an arrival warning and the existing arrival-only override. No override is selected automatically. Approval applies to this arrival rather than changing the configured session limits.

On the public form, separately exceed child capacity, combined child/adult capacity and supervised capacity. The estimate should show the relevant configured limit, already-booked count and recovery guidance. Customers receive no override checkbox.

## 13. Public Continue after a capacity warning

Click Continue while over capacity. The error screen shows the session date/time directly beneath Your play session and above the warnings. It offers Adjust the amounts in my booking and Choose another session.

Adjust returns to the same session with the latest attempted play type, attendee counts, socks and payment choice preserved, including when those differ from an earlier accepted estimate. Continuing with excessive counts still fails; correcting them requires a fresh capacity/price check. Choose another session opens session selection. Neither recovery action books a place or collects money.

## 14. Change timing and compact edit forms

Use Change timing and pick another date/session. The list/capacity information should update without leaving the booking. Saving must not demand attendee/payment fields that are absent from the timing form. Check the new session/time on booking details. Owner closures/reopen options retain their existing explicit behavior.

In Edit booking, attendee inputs remain compact. Counts/payment changes update the price preview before Save changes. A changed amount requires its payment-method review. Saving an edit does not collect money.

## 15. Public waiver and payment wording

On session selection, all five booking steps are present. Waiver choices use Every participating minor needs a signed waiver, Your current signed waiver info, bullet summaries and capitalized display names. On the signing form, the one-minor-per-line instruction sits above the names box. The redundant saved-waiver reassurance is removed. Earlier valid evidence remains reusable.

Zelle sender fields appear only when Zelle is selected. The card page uses the revised credit-card visit-payment wording, the shorter future-use replacement sentence and tighter spacing between hosted fields and the optional save-card checkbox. Invalid card/setup responses must be prominent in rose near the confirmation controls; uncertain provider responses must not trigger silent retries.

The month-to-year cursor advancement is still pending Banquest's answer. This release does not claim to implement it. Verify actual provider-field appearance and sandbox card outcomes after deployment; local browser captures use synthetic provider integrations.

## 16. Payment follow-up and settlement refresh

Use a definitively declined unpaid sandbox card attempt to test the existing owner Retry card action. It requires explicit review and confirmation and collects only the remaining amount. Pending/unknown payments must be reconciled before another attempt. No automatic retry is added by this batch.

Refresh provider settlement status asks Banquest for updated information about an existing transaction. It does not charge the card again. Keep the original transaction and event history when reviewing its response.

## Deployment and feedback

The supplied single PowerShell block uses the browser-downloaded pinned ZIP, refreshes its matching helper and deploys to the existing Functional staging target with -ApplyReviewedBooking. Additive migrations 0048-0051 create the new paper/Zelle records and booking controls. The helper verifies the allowed migration files/plan, creates a private database checkpoint and applies restricted runtime grants. A checkpoint is not an offsite backup; code rollback does not undo schema changes.

No new credentials, live-payment activation, backup activation, homepage redesign or active membership features are included. Existing sandbox integration configuration and earlier business records remain. No server deployment is performed by the agent. Deployment health checks verify startup; the scenarios above still need your review afterward.

For feedback, give the booking ID, page/action, expected result and actual result. A screenshot is useful. For uncertain card outcomes, review the existing operation before trying again; do not enter real card details or share credentials in feedback.
