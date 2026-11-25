# Eighth batch: post-deployment testing guide

For PR #34 after the deployment command reports success at staging.monkeydoplay.com. This covers the final approved screenshot comments and inline retry wording. Use fictional customer details, Banquest sandbox cards and an email inbox you control. Ordinary admission is collected after staff arrival review; saving/selecting a card does not collect it. These checks supplement the automated tests already run before release.

## 1. Public pages and navigation

Review Home, About, Membership, Parties and Contact on a desktop and phone. The public name is MonkeyDo and navigation says Membership. Check the About-only Open Play membership sentence, corrected membership benefits, rose Save More, and party goody-bag/souvenir wording. The footer says Open Sunday through Friday - by reservation only. On a phone, the four membership photos form two rows of two. About text/photos retain full strength while scrolling. The Contact address sits lower beneath its divider. Membership checkout remains unavailable; no active membership stage is introduced.

## 2. Session selection and progress

Open Book Now. Choose your slot is rose. Desktop session cards have more space around time, description and button. Phone cards keep the compact box size with the description slightly lower. Available sessions do not repeat the redundant Open status, but open-play-only, supervised availability and unavailable states remain clear. On a phone, progress reads 1–3 down the left column and 4–5 down the right, with each leaf aligned to the first line.

Time ranges should read 2:30–3:45 PM or 9:00–10:15 AM. A session crossing noon retains both: 11:30 AM–12:45 PM. The selected date/time appears highlighted directly below Your play session and above the staging notice.

## 3. Customer details

Start a brand-new customer booking. Required Last Name and Email address markers follow the colon: Last Name: *. Empty required values prevent continuation. Public phone summaries use 732-555-0147 formatting without changing the saved number. Existing name/email verification, conflict handling and owner alerts remain in place; either-or lookup fields must not misleadingly require both values.

## 4. Group counts and socks

Open Play requires at least one adult. Switching to Supervised Play locks adults/babies to zero; returning to Open Play restores its adult requirement. Baby-only and adult-only visits remain available under the existing admission rules. Mouse-wheel scrolling over a number input should scroll the page without changing its value. Explicit typing/spinner/keyboard changes still work. Sock guidance includes $1.99 per pair; quantities use child/children, adult/adults, baby/babies and pair/pairs appropriately.

## 5. Waivers and validation

Check both a new customer and a returning customer with an active waiver. Public signing hides the internal waiver version; signed records still retain it. Selecting additional signing disables and grays Continue to payment until the signing requirement is resolved. Trigger a missing relationship or another required-field error. The error should be brought into view and receive focus without the former rectangular outline around the message. Input/button keyboard focus indicators still work. Existing waiver evidence and the shared-parent held-place workflow are preserved.

## 6. One-button card confirmation

Proceed to Payment Details with a new card. There is one Confirm booking button. Accept the cancellation policy and staging acknowledgment; the latter is staging-only. Saving/selecting the card and confirming the booking happen through that one explicit action, with processing dots and an unconfirmed status while work is underway. Do not repeatedly click while processing. A successful result shows the saved booking and queues its confirmation email. No ordinary admission payment or verification hold should be created by card setup.

Repeat with an existing reusable card. The selected saved card is visible. When entering a replacement card, the replacement sentence appears only if there is already a reusable card. Missing/invalid secure fields should produce a visible error and leave the booking unconfirmed. Card setup is not an admission authorization; it does not establish that a later admission charge will succeed.

## 7. Interrupted connection and inline retry

This is an exceptional connection-recovery state, not a normal step or a statement that a previously saved card disappeared. If a setup/selection response is interrupted, the public message reads: Your booking is not confirmed. We couldn't confirm your card selection for this booking, please try again. The final phrase is a link inside the message, replacing the separate public Check card setup control.

For a previously saved card, the link reloads the recorded choice. For a newly entered card, it checks the already-started setup. Neither action resubmits the card, charges it or silently confirms a booking. After successful recovery, the selected card is shown and the customer must explicitly click Confirm booking. If the result remains uncertain, the customer must not keep submitting another card. Staff setup retains its separate Check card setup control. These interruption cases were exercised locally with synthetic adapters; deliberately interrupting a payment charge is not needed for this review.

## 8. Cash, check and Zelle backup cards

Choose each non-card payment method and review the backup-card wording and Switch payment method spacing. Saving the backup card does not collect admission. Zelle setup includes the sender details and explains that instructions follow in the confirmation email. Confirm a Zelle booking: its confirmation page shows a cream instruction box without the warning-style border. The first sentence is Please send payment by Zelle at any time to monkeydoplay@gmail.com.

## 9. Confirmation email

Check delivery to your controlled inbox and the booking's message history. The subject uses a hyphen before the session weekday/month/day and start/end times, with no year or booking reference. Example: Your MonkeyDo adventure is booked! - Thursday, November 26, 2:30–3:45 PM. No booking reference appears in the body. There is no separate preheader repeating that appointment. The body still includes its date, year and time range, correct quantity wording, address and applicable payment/waiver instructions. Zelle instructions use the revised combined sentence. Previously sent/frozen messages are not rewritten. Same-session emails may still be grouped by the recipient's mail client.

## 10. Older browser flows

Start a fresh booking after deployment. It must follow the current waiver/card completion flow, without the old pending-test-reservation confirmation screens. An unfinished older flow should return to current required steps while preserving its entered details. Historical test bookings remain historical records. A staging configuration without booking completion enabled should pause new booking rather than silently accept a legacy reservation.

## 11. Hosted card layout and regression spot-check

Check Banquest's actual secure fields on desktop and phone: the card-number field leaves room for expiry/security fields and Security code stays on one line. Local gallery captures use a simulated provider frame; actual iframe rendering needs this deployed check. Month-to-year cursor advancement remains pending Banquest's guidance.

Spot-check an existing booking, arrival, payment history and waiver history. Admission collection remains an explicit staff arrival action; the existing payment retry and refund controls retain their safeguards. No financial calculation, signed evidence, historical consent or earlier frozen email is rewritten by this release.

## Deployment boundary

The eighth batch introduces no schema migration. The single deployment block uses the existing Functional staging target and routine migration guard; it does not enable production payments, backups or memberships. Existing credentials and integration flags remain configured as before. Keep the successful deployment output, then record any issues with the gallery screen number, route and steps that produced them.
