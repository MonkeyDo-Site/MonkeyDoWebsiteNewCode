# Ninth/tenth review — checks after deployment

This guide describes PR #35 as built. Automated PostgreSQL tests and GitHub deployment-wrapper checks passed before release. These are the owner's manual acceptance checks on staging after the deployment command reports success. Use fictional customers and Banquest sandbox cards. Ordinary admission is collected at reviewed arrival, not during online reservation.

The owner approved merging and deploying while deferring the cloud-environment settings issue. Actual Banquest field rendering was not verified from the cloud workspace; check it first below. Local gallery fields and provider outcomes were simulated. Month-to-year automatic focus still depends on Banquest guidance. Active memberships and cash-change functionality remain deferred.

## 1. Deployment and existing records

The single PowerShell block installs the matching deployment helper and deploys Functional staging with -ApplyReviewedBooking. From the reported deployed 0051 baseline, the only new schema step is reviewed migration 0052, which adds an optional booking association to existing comments. The helper checks the pinned migration files/plan, saves a private local database checkpoint and applies the approved upgrade. Unknown migration plans stop deployment. This checkpoint is not an offsite backup; code rollback does not reverse schema changes.

Open existing customer and booking records. Earlier general customer comments, payments, waivers, frozen emails and accepted pricing must still be available. No integration credentials or activation flags are changed by this handoff.

## 2. Actual Banquest fields — first visual check

Start a fictional online booking and select Enter a new card. Check card-number width, month/year positioning and CVV alignment on desktop and phone. This release restores the earlier provider container layout and sizes the number input within its container. Confirm that labels/errors are visible without clipping. Report a screenshot if the actual hosted layout is still wrong; the gallery cannot establish this result.

Use only provider-approved sandbox card details for payment tests. Card saving does not establish that a later charge will be approved. A Banquest-hosted validation error is distinct from an issuer/processor decline.

## 3. Public payment and booking confirmation

The customer page has one rose Confirm booking action, a separate cancellation acknowledgment and optional future-use card checkbox. Backup-card pages have no separate payment-policy agreement checkbox or long booking-only-card disclaimer. Switch payment method has space above the backup-card explanation. Selecting a saved card hides new-card controls.

For credit card, the quote says Total that will be charged at arrival. For cash/check/Zelle, it says Total due at arrival. Clicking Confirm booking shows processing and saves/selects the secure card before confirming the reservation. Failure/uncertainty must not claim a confirmed booking or silently repeat a token exchange. The saved-card recovery wording uses an inline please try again link.

After successful confirmation, check the appointment, counts, socks, email and payment choice. No ordinary admission payment should have been collected online. Where a shared waiver link was requested, the reminder starts Please remember to send the link in your confirmation email to the other parents. The places remain held and outstanding waiver coverage remains recorded.

## 4. Customer lookup after an unsuccessful email search

Choose Yes, enter an unknown phone, and use the email recovery link. Search for an unknown email, then retry with an existing current email associated with another phone. The existing email must now be recognized. Verify the last name; an already entered matching name is reused.

Before a name match, the page must not disclose the stored phone. A matching name leads to an explicit Is this you? confirmation showing the saved name, actual email and formatted phone. Continue with this customer profile uses that profile and its saved phone for this booking. Start again retains the selected session. Customer records are not merged or edited by this choice.

## 5. Conflicting profiles and duplicate new-customer email

Use the phone of profile A and email of profile B. If the name matches B, the flow may verify and explicitly confirm B instead of requiring a restart. If the name matches both profiles, the clear two-option screen appears: Use the profile with phone… and Use the profile with email…. The phone option requires the email saved with that phone. The verified email option shows its saved phone and Continue with this email address. An unverified name must not unlock that stored phone or select the profile. Existing conflict notices remain on the owner's Dashboard.

On Your details, submit an email already used by another customer. Expect the shorter Looks like you’ve booked with this email before… guidance, the newly entered formatted phone and a go back link. It must not offer to remove another profile's email or create a duplicate customer. The link retains the session.

## 6. Adult-count messages and public prices

In Open Play, attempt to lower adults below one. The field explains: An adult must accompany a baby or child to an open play session. Supervised public counts retain their children-only controls.

As owner, edit an Open Play booking containing adults and select Supervised Play. Immediately expect Cannot have adults in a supervised play visit beside Adults. Correct the count to zero and verify that the estimate updates. Counts are retained for correction; an invalid preview clears the old breakdown rather than showing stale prices. Saving changes does not collect payment.

On pricing settings, percentages display cleanly, such as 6.60 and 3.00. Unchanged values with redundant trailing zeroes are accepted; genuine excess precision receives a focused error. There is no independent minimum-admission input. Save a fictional new child price: baby-only/adult-only admission must match it, and current public price text must update. Existing accepted bookings retain their original policy and amounts.

## 7. Waiver signing and coverage

Every new electronic or named paper waiver requires minor names. Parent uses first names; Legal guardian requires first and last names for every minor. Blank minor-name exceptions are not retained. Earlier signed evidence is not rewritten.

Public headings say Sign Waiver and Every participating minor needs a signed waiver. After signing, Yes appears above No for the coverage question. Public shared links still use their limited signing/completion flow. Staff signing from arrival returns to protected arrival with its unsaved entries preserved.

## 8. Arrival pricing before waiver confirmation

Open Start arrival. Change children, adults and grip socks before answering the waiver question. The price and payment plan must update. The final action remains unavailable until required coverage/payment decisions are complete. Missing coverage confirmation says The waiver confirmation field is required rather than a generic missing-fields error.

Active waiver summaries and any shared-link request are visible. Paper waivers signed expands the named paper-entry controls on arrival; recording one does not itself mark the customer arrived or collect money.

## 9. Staff coverage attestation and count discrepancy

Increase visiting children/babies above the distinct names recorded in current connected waivers, then choose Yes. Expect: There are more children in the visit than the children listed in the signed waivers connected to this booking. Do you want to go ahead?

The final action must remain blocked until staff explicitly acknowledges the discrepancy. Yes plus that acknowledgment is authoritative after staff checks the actual waivers. The actor, time, attendee/name counts and acknowledgment remain in checkout/audit history. Changing counts must require the relevant acknowledgment again.

## 10. One-action card change and preserved arrival entries

Enter distinctive arrival counts, socks and payment choices. Choose Change card for this booking. Expect one Save and use this card action, no duplicate Save card button and no extra Use this reviewed card checkbox. New staff-entered cards require a separate Yes/No choice about future use. Staff cancellation text contains only the approved first three sentences.

Save/use the reviewed card and return to arrival. Check that counts, socks, payment rows, waiver answers and selected card are retained. Repeat through Sign waiver now. Returning from signing must retain entries and show the new names. Neither side trip records arrival or repeats an uncertain card request. Arrival drafts expire after two hours or when the booking changes elsewhere; an expired/stale draft asks for a fresh review.

## 11. Full non-card split and card remainder

Select Split payment. Enter method/amount rows and use Add payment method. For a $15.99 non-card total, $10 gift card plus Use remaining balance on a cash row fills $5.99. At another price, use its actual displayed remainder. Verify physical gift cards and received Zelle as required.

When non-card funds cover the visit, there must be no card charge or card processing fee. With a partial non-card amount, the preview explicitly shows the remaining card charge; the fee applies only to the card-funded portion. Excess applied amounts show a clear error and block confirmation. Cash-change functionality is not included.

Switch the overall payment choice away from Split payment. Abandoned unsaved rows/amounts clear and the price updates. Previously recorded Zelle receipts and completed payments remain intact. Nothing records funds until final confirmation.

## 12. Final arrival and declined-card follow-up

Confirm a reviewed arrival using the rose final action. Expect processing dots while the real provider outcome is pending, followed by an accurate approved, declined, review-needed or still-pending message on the same page. Pending/failed funds must not count as received. Check payment status reads the existing operation and never sends another charge.

For a definitively declined unpaid card attempt, View booking must show both owner Retry card and Review remaining payment when permitted. Retry requires explicit review/confirmation and collects only the unpaid amount. Review remaining payment allows another supported tender. Change card for this booking can replace the source before a later reviewed card attempt. Pending/unknown operations must be resolved before another payment; no automatic retry occurs.

## 13. Booking details, comments and Dashboard

On desktop, Visit details, Payment and Waivers occupy the left column. Saved price breakdown, Comments and Messages occupy the right, in that order. On phones they stack without horizontal overflow. Payment shows the total actually received, then its tender history. Backup booking card ending in… appears immediately above Change card for this booking when the expected payment is non-card.

Add/search/edit a booking comment. Check staff author/date/time and retained edit history. Booking comments stay scoped to the booking, while earlier general customer comments stay general. Staff without the relevant permissions must not see or edit restricted comments/history.

Dashboard notices use compact rows with individually expandable details and Mark reviewed beside each. Reviewing a notice changes its review state, not the customer records or payments.

## 14. Adjustments, cancellations and Zelle

Change a standard booking's counts/socks before or during arrival. The price adjustment explains the original total, added/removed admissions or socks, processing-fee/tax changes and the adjusted total. Sales-tax adjustment appears above the cancellation-fee adjustment. The fee row states no sales tax. The arithmetic still reconciles exactly.

Cancel or mark no show with and without the applicable fee. There is no gift-card fee option; attempts to use gift cards for these fees are rejected, including later follow-up collection. Ordinary arrival still permits verified physical gift cards. Existing Zelle prepayments are applied against the chosen fee and any excess becomes a manual refund due, with the existing Dashboard reminder until completion is recorded. The owner still chooses whether to send the customer email. Calculating a refund does not send it.

## 15. Record feedback

For an issue, record booking ID, page/action, expected versus actual result and a screenshot. Include desktop/phone and whether it concerns the real Banquest frame. Do not include private keys, full card details or CVV. Continue using the existing staging site; report new comments as follow-up work after deployment.
