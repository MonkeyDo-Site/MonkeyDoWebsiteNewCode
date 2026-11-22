# Sixth batch: staging testing guide

Use this after deployment of PR #32. This batch changes the existing sandbox booking flow; it does not turn on live payments or active memberships. Homepage design is unchanged. Use provider sandbox cards and fictional participants, with an email inbox you control for confirmation testing.

## 1. Booking progress

On a wide screen, all five steps fit across one row: Choose Session, Customer Details, Session Details, Waiver Details, Payment Details. On phones the steps wrap without horizontal page scrolling.

## 2. New customer and all-expired waivers

On Waiver coverage, expect “Please select option 1 or both options:”. Signing now is required; requesting the shared parent link is optional. Selecting only the link must not bypass signing. A returning customer whose waivers have all expired sees the expiry explanation and follows the same rule. A waiver must still be valid for the appointment date, not just today's date.

## 3. Existing current and mixed waiver history

Check that each applicable current waiver shows signer, covered minor names and expiry date. An older unexpired waiver remains usable despite the shortened age acknowledgment in this release. Expired evidence remains in history. For mixed history, the explanation distinguishes expired and unexpired coverage.

Choose existing coverage to continue without signing again. Choose to sign for additional minors and check that Continue to payment is disabled until signing is completed. Participants not covered by existing waivers need a new signature or the requested shared-parent link. Selecting complete coverage must not bypass the participant-count check.

## 4. Signing and completion

Both the customer's form and the shared parent's form omit email and phone inputs. The full legal waiver, typed full legal name, parent/legal guardian choices, minor-name field and three explicit acknowledgments remain. No Self choices or self-only help sentence appear. The age acknowledgment reads “I confirm that I am at least 18 years old.”

Adult-only visits use the same screens and form. Leave the minor-name and relationship fields blank when signing for an attending adult; no separate Self option is needed. Selecting Parent or Legal guardian requires the covered minors' names.

After signing within booking, expect a thank-you screen showing the newly signed adult/minors and an explicit Yes/No coverage choice. Continue to payment leads to Payment Details, without redisplaying the full signing form. No requests the parent link and retains the approved Waiver pending / held-place behavior.

After signing through the emailed shared link, expect only the thank-you and appointment information within the normal site shell. No other family's contact, card, signature or legal form is exposed. The completion notification still goes to the booking customer's current email; it does not need the signing parent's email or phone.

## 5. Payment Details: each intended method

Try Credit card, Cash, Check and Zelle. Check that each page has a compact cream itemized breakdown, with amounts aligned on the right and “Total due at arrival”. Tax and applicable card fees remain in these final payment details; the earlier Session Details estimate still excludes them.

Credit card shows only its intended arrival-payment explanation. Cash/Check/Zelle explain the backup card. No public payment-policy checkbox or booking-only-card disclaimer is shown: explicitly choosing Save card securely records acceptance of the displayed payment terms. The separate cancellation acknowledgment and optional future-use choice remain. Zelle says its instructions will arrive by email. Check the owner's supplied public cancellation sentence and separate membership sentence. Existing fee calculations, minimum-admission fees and owner-comped exceptions have not changed.

Use Switch payment method on Payment Details. Previously signed waivers must remain saved. The quote updates for the new method; explicitly save/accept the applicable card policies again. A card already saved within this booking can be selected again without entering another card. Booking-only cards are not silently changed into future-use cards.

## 6. Save card, then confirm

Save card securely and Confirm booking appear beside each other with an arrow on wide screens; they stack on phones. Confirm booking starts lighter and disabled. There is only one Save card securely button. After successful setup, Confirm booking turns rose, pulses gently three times, receives focus and comes into view if needed. Expect “Your card is saved. Click Confirm booking to finish your reservation.” Reduced-motion settings suppress the pulse. The button remains rose after the animation ends. There is no automatic final booking submission.

The initial credit-card message is “Card will be charged at arrival. Save your card first, then confirm your booking.” The backup-card message begins “Saving a backup card does not charge it.” Switch payment method is positioned slightly higher, with more space before the backup-card explanation. The sandbox acknowledgment appears only in staging/development/test; the production form omits it.

Changing the selected card or its policy choices disables confirmation until it is saved again. Incomplete provider card entry should give actionable instructions and allow correction. An uncertain server/provider response instead asks you to check the existing setup; it must not silently exchange a second card token.

Card saving does not run an issuer charge or verification hold and does not guarantee a later charge will be approved. This is still tested separately at staff arrival. Check the actual Banquest-hosted fields on both desktop and phone after deployment; local screenshots use a simulated provider frame and cannot prove live iframe rendering or merchant card-brand acceptance.

## 7. Saved booking and confirmation email

The saved-booking page says no admissions payment was collected online and payment will be processed upon arrival. Its itemized payment box uses the cream layout. Updating the email explains that it changes the customer profile and sends this booking's confirmation to the updated address.

Confirmations have the MonkeyDo logo and background, a bold rose adventure heading, bold appointment and total/payment-method information, and one final total after the breakdown. Cash/Check are due upon arrival; Credit card is charged upon arrival. Zelle includes the supplied destination and backup-card explanation. Sock purchases appear once in the breakdown; when none were purchased, expect “Please remember to bring along your grip socks.”

A later resend after an actual payment or correction must retain truthful received/remaining amounts, rather than promise another full arrival charge. Staging emails retain their test subject/banner. Earlier frozen messages are preserved.

## 8. Owner Retry card

Use an existing booking with a verified Declined card attempt and unpaid balance, such as #22 if it is still unpaid. Do not create another booking to collect the original visit's balance.

On the booking Payment panel, and on its declined payment detail, the owner sees Retry card. Opening it sends no charge. Review the remaining amount and card's last four digits. If necessary, use Change booking card before retrying. Explicitly confirm the reviewed amount once. The new request remains pending until the provider confirms its result; the original decline remains in history.

There is no automatic retry. Received cash or other successful split tenders must not be collected again. Pending/unknown/authentication-required transactions are not retryable until reconciled. Fully paid or corrected invoices must not offer an unreviewed retry. Staff do not receive this owner-only shortcut; existing permitted remaining-payment tools remain.

## 9. Browser Back and Forward

Move backward and forward through customer details, attendee counts, waiver choices and payment review. Earlier entered values should remain. Editing earlier answers invalidates later cached checkpoints and requires the appropriate review again. A stale tab must not submit another flow's form.

Previously signed evidence remains saved; changing a payment method does not require another signature. Browser Back/Forward alone must not sign a waiver, collect money, save another booking or send another confirmation. After final confirmation, revisiting old booking forms resolves to the saved receipt. Explicit Start again starts a separate booking for the selected session.

## Deployment boundary

This is a normal code-only Functional deployment, with no database migration switch and no credential changes. It preserves active sandbox integrations and the existing disabled-backup setting. Existing bookings, evidence, payments and histories remain. Merge only after the final PR checks pass and the payment-page design is approved; use the exact reviewed ZIP and single PowerShell block supplied with the handoff.
