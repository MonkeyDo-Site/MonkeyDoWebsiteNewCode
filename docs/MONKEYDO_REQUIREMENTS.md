# MonkeyDo Website Requirements

Documentation-only checkpoint created on 2026-08-05. This file consolidates confirmed requirements and planning notes for the future MonkeyDo website build. It does not implement application code, payment integrations, database code, or deployment configuration.

## 1. Project goal

Build a production-ready website for MonkeyDo, a children's indoor playspace located in Lakewood, New Jersey. The site should be welcoming, playful, polished, mobile-friendly, accessible, and appropriate for families.

The website must include:

- A homepage introducing MonkeyDo.
- Warm, engaging wording about the children's playspace.
- A prominent “Book Now” button leading to the booking page.
- Top navigation with Home, Book Now, and Contact Us.
- A customer-facing booking system.
- A secure administrative dashboard for the owner.
- A contact page or section.
- Public location wording that says MonkeyDo is on Budleman Way in Lakewood, New Jersey, without publishing the exact street address.

The website must use a persistent production database. A temporary JSON file must not be used as the production database.

## 2. Branding and design direction

The supplied MonkeyDo logo and advertisement are the visual source of truth. The logo must be preserved exactly and must not be recreated, generated, redrawn, or altered.

### Brand personality

MonkeyDo should feel:

- Warm.
- Playful.
- Polished.
- Calm rather than chaotic.
- Boutique and parent-trustworthy.
- Soft jungle/adventure themed.
- Sensory-rich and movement-oriented.
- Child-friendly without feeling generic.

### Observations from the logo

The logo uses:

- Large playful block lettering.
- A monkey face integrated into the wordmark.
- Muted sage green for “MONKEY.”
- Warm salmon/coral pink for “DO.”
- Soft beige/taupe for the monkey face and tagline.
- Wide tracking for “ADVENTUROUS PLAY.”
- Rounded, friendly, irregular letterforms.

### Observations from the advertisement

The advertisement uses:

- Organic blob-shaped photo framing.
- Thick sage borders.
- White and warm negative space.
- Jungle mural imagery.
- Natural wood tones.
- Palm leaves, animals, and soft greens.
- Pill-shaped feature labels.
- Playful text such as “GO BANANAS HERE.”
- A calm, muted color system rather than bright primary colors.

### Recommended visual system

Use a palette inspired by the supplied materials:

- Sage green as the primary color.
- Coral/salmon pink as the main warm accent.
- Taupe/beige for supporting accents.
- Cream or warm white backgrounds.
- Natural tan/wood tones as subtle supporting accents.
- Deep warm green/charcoal for readable body text.

The design should use:

- Rounded typography.
- Pill-shaped buttons.
- Organic image frames.
- Soft cards.
- Gentle jungle, leaf, banana, star, and monkey-inspired accents.
- Mobile-first responsive layouts.
- Accessible color contrast and keyboard-friendly controls.

Recommended customer-facing pricing wording:

> Children ages 1–11 are $15 each. Babies under 1 are free. One free adult per family, and each additional adult is $5. Every booking requires at least one $15 paid admission, which will be applied to a baby or adult if there is no child in the booking.

Required group-booking message:

> For group bookings of 10 or more and discounted group rates, please call or text us at 848-238-5147.

## 3. Public contact and location requirements

Public phone number:

- 848-238-5147

Public email:

- monkeydoplay@gmail.com

Public location wording:

- The public website may say MonkeyDo is located on Budleman Way in Lakewood, New Jersey.
- The exact street address must not be published on the public website.

Confirmation-only address:

- 56 Budleman Way
- Lakewood, NJ 08701
- Basement entrance

Confirmation-only parking note:

- Please park in the driveway or cul-de-sac.

Recommended confirmation location wording:

> MonkeyDo is located at 56 Budleman Way, Lakewood, NJ 08701. Please use the basement entrance. Please park in the driveway or cul-de-sac.

Public business-hours text:

> Open Sunday through Friday by reservation, with four daily time slots.

## 4. Schedule and availability

MonkeyDo currently operates Sunday through Friday with four booking slots per day:

- 11:30 AM–12:45 PM
- 1:00 PM–2:15 PM
- 2:30 PM–3:45 PM
- 4:00 PM–5:15 PM

All booking logic must use the America/New_York time zone.

Customers must be able to view available dates and time slots before beginning a booking.

Availability must be calculated from:

- Existing bookings.
- Slot capacity.
- Date closures.
- Blocked holidays or unavailable dates.
- Admin slot changes.

Availability must not be a static schedule.

### Customer booking window

- A date becomes bookable starting at 12:00 AM America/New_York on the previous calendar day.
- Same-day bookings are allowed.
- A customer may book a slot after it has started as long as it has not ended.
- A slot closes after its end time.

Example: for an August 4 booking date, customers may start booking on August 3 at 12:00 AM America/New_York.

### Saturday rules

- Saturday must be hidden entirely from the customer-facing booking calendar.
- Saturday should not appear as closed to customers.
- The backend/admin system must support owner-created Saturday bookings for future seasonal Saturday night use.
- Saturday bookings are admin-only unless the owner later changes the customer-facing schedule.

## 5. Admin schedule controls

The administrator must be able to:

- Open or close specific dates.
- Block holidays or unavailable dates.
- Add, remove, or edit time slots.
- Adjust capacity.
- Adjust pricing.
- View remaining capacity for each slot.
- Create admin-only slots, including Saturday slots.
- View, search, edit, and manage bookings.

The schedule model should support slot visibility values such as public, admin-only, and hidden.

## 6. Individual and group bookings

Only individual/non-discounted bookings can be completed online.

Discounted group bookings cannot be completed online. Customers may still book 10 or more children online at the normal public price if they choose to do so.

The booking page must display this exact message:

> For group bookings of 10 or more and discounted group rates, please call or text us at 848-238-5147.

The system must not:

- Apply a group discount online.
- Provide an online group-discount request form.
- Show a group-discount pop-up during payment.
- Prevent 10+ child bookings at normal price solely because they are 10+.

For admin/owner-created group bookings, the owner must be able to enter any custom price she determines, including $0.

## 7. Attendee categories and validation

The individual booking form must collect separate quantities for:

- Babies under 1.
- Children ages 1–11.
- Adults ages 12+.

The system must automatically calculate and display the total number of attendees. Customers must not manually enter the same total again.

Every booking must include at least one adult ages 12+.

The backend must reject bookings where:

- Adults count is less than 1.
- Any attendee quantity is negative.
- Total attendees is zero.
- Required customer fields are missing or invalid.
- Required waiver or consent is missing, except where an admin-created phone booking is confirmed with waiver pending.
- Required card setup is missing, except for admin-created $0 bookings.
- Capacity limits are exceeded.
- The selected slot is unavailable or has ended.

## 8. Capacity rules

Babies under 1 do not count toward either capacity limit.

Only children ages 1–11 and adults ages 12+ count toward occupancy.

Capacity must be enforced atomically on the backend so two customers cannot reserve the same remaining space simultaneously.

Rules:

- Standard child capacity: 30 children ages 1–11.
- Absolute child limit: 35 children ages 1–11.
- Absolute combined occupancy: 50 children and adults.
- A booking may take the child count above 30 only if the resulting child count remains 35 or fewer.
- A booking is accepted only if the resulting combined number of children and adults remains 50 or fewer.
- Both absolute limits must be satisfied.
- Babies do not reduce remaining capacity.

Examples:

- If 28 children are booked, a booking for 3 more children is allowed.
- If 34 children are booked, a booking for 2 more children is not allowed.
- If 34 children are booked, a booking for 1 child and several adults is allowed only if the resulting combined child-and-adult total remains 50 or fewer.
- If 35 adults and 15 children are booked, the slot is at its total occupancy limit.
- Babies do not count toward either limit.

If a booking cannot be accommodated, the system must display a friendly explanation and must not save the booking or process a payment.

## 9. Pricing rules

Pricing must be calculated automatically.

Standard public pricing:

- Children ages 1–11: $15 each.
- Babies under 1: free, except when a baby receives the required $15 paid admission because there is no child in the booking.
- One free adult per family.
- Each additional adult is $5.
- Every booking requires at least one $15 paid admission.

### Bookings with one or more children ages 1–11

If the booking includes at least one child:

- Each child is $15.
- Babies are free.
- One adult is free.
- Each additional adult is $5.

Formula:

- Child charge = children × $15.
- Adult charge = max(adults − 1, 0) × $5.
- Baby charge = $0.

### Bookings with babies but no children ages 1–11

If the booking includes babies but no children:

- One baby is treated as the required $15 paid admission for display and confirmation purposes.
- Additional babies are free.
- One adult is free.
- Each additional adult is $5.

Formula:

- Baby admission charge = $15.
- Additional baby charge = $0.
- Adult charge = max(adults − 1, 0) × $5.

### Adult-only bookings

If the booking includes no children and no babies:

- One adult is treated as the required $15 paid admission.
- Each additional adult is $5.

Formula:

- Adult admission charge = $15.
- Additional adult charge = max(adults − 1, 0) × $5.

### Price snapshots

The system must show an itemized price breakdown before confirmation and save the final price calculation with the booking so future price changes do not alter existing bookings.

The administrator must be able to change future pricing without editing code.

For admin-created group bookings or special bookings, the owner may override pricing and enter any custom amount, including $0.

## 10. Customer booking fields

The booking form must collect:

- Full name.
- Phone number.
- Email address.
- Selected date.
- Selected time slot.
- Number of babies under 1.
- Number of children ages 1–11.
- Number of adults ages 12+.
- Automatically calculated total attendees.
- “How did you hear about us?”
- Preferred confirmation method: email, text, or both if supported.
- Payment method.
- Required waiver acceptance for online bookings.
- Electronic signature for online bookings.

All required information must be validated on both the frontend and backend.

## 11. Card-on-file requirements

Every paid customer booking must have a valid credit card securely saved on file, regardless of selected payment method.

Exception:

- Admin-created $0 bookings do not require a saved card.

The MonkeyDo database must never store:

- Full card numbers.
- CVV/security codes.
- Raw card data.

Use a payment provider's secure hosted or tokenized collection system.

The customer must clearly consent to:

- Saving the payment method securely with the payment provider.
- Charging it later according to the selected payment method.
- Charging an unpaid balance after the appointment.
- Charging an approved cancellation or no-show fee once the final policy is activated.

Store:

- Consent source.
- Accepted terms version.
- Date and time.
- Relevant audit details.

Phone/admin bookings may record verbal card consent given over the phone, but the owner must use an approved phone-consent script. The owner may enter the customer card through a secure provider-controlled card entry component. Card data must not pass through the MonkeyDo server.

## 12. Payment workflows

### Cash

At booking:

- Save a backup card unless this is an admin-created $0 booking.
- Do not charge the card when the booking is made.
- Payment status should indicate cash is expected.

At arrival/payment:

- Owner can mark customer arrived.
- Owner can mark cash received.
- Once cash is received, the saved backup card may be removed.
- If cash is not received, owner may choose credit card and charge the saved backup card, with confirmation and audit logging.

### Check

At booking:

- Save a backup card unless this is an admin-created $0 booking.
- Do not charge the card when the booking is made.
- Payment status should indicate check is expected.

At arrival/payment:

- Owner can mark customer arrived.
- Owner can mark check received.
- Once check is received, the saved backup card may be removed.
- If check is not received, owner may choose credit card and charge the saved backup card, with confirmation and audit logging.

### Zelle

At booking:

- Save a backup card unless this is an admin-created $0 booking.
- Do not collect the Zelle payment through the website.
- Do not charge the backup card when the booking is made.
- Display configurable Zelle payment instructions once supplied.
- Display the exact amount due.
- Generate a unique booking confirmation number.
- Tell the customer to include the confirmation number in the Zelle memo.

At arrival/payment:

- Owner can mark customer arrived.
- Owner can mark Zelle received only after verifying it in the business bank account.
- A customer screenshot must not be treated as final proof of payment.
- Once verified Zelle payment is marked received, the saved backup card may be removed.
- If Zelle was not received, owner may choose credit card and charge the saved backup card, with confirmation and audit logging.
- If duplicate payment occurs, the system should flag it for review and refund handling.

Still configurable and not yet supplied:

- Business Zelle email, phone number, or Zelle Tag.
- When Zelle payment is due.
- Exact Zelle instruction wording.

### Credit card

At booking:

- Securely collect and save the card.
- Do not charge the card when the booking is made.
- Clearly show the amount that will be charged later.
- Obtain explicit consent for later charge.

At arrival:

- When the admin marks the customer as arrived, the saved card should be charged automatically if the selected payment method is credit card.
- This is triggered by the admin's arrival action, not merely by the appointment time passing.
- The admin action should clearly communicate that marking the customer as arrived will charge the saved card.
- The system must prevent duplicate charges.
- Failed charges and charges requiring additional authentication must be handled clearly.

### Non-credit-card bookings that pay by card at arrival

For bookings originally marked cash, check, or Zelle:

- After the customer is marked arrived, the owner should see payment options: cash, check, Zelle, or credit card.
- If the owner selects credit card, the saved backup card should be charged.
- The system must record the payment method selected at arrival and audit the action.

### Admin-created free bookings

The owner may create bookings with a $0 final amount.

For $0 bookings:

- No saved card is required.
- No payment attempt should be created.
- Payment status should be comped.
- Waiver is still required.
- The reason for the $0 booking should be recorded and audit logged.

## 13. Payment statuses

Support clear payment statuses including:

- Card required.
- Card saved.
- Payment pending.
- Cash expected.
- Cash received.
- Check expected.
- Check received.
- Zelle expected.
- Zelle received.
- Credit-card charge pending.
- Paid.
- Comped.
- Failed.
- Refund pending.
- Refunded.
- Partially refunded.
- Duplicate-payment review required.

The admin dashboard should clearly display:

- Payment method.
- Amount due.
- Amount received.
- Payment status.
- Payment history.

## 14. Attendance statuses

Attendance status should use only:

- Arrived.
- No show.
- Cancelled.

Before attendance is marked, the stored value may be blank/null. Do not add unnecessary statuses such as not arrived, left, or completed.

Do not store `arrivedAt` or `arrivedByUserId` directly on the booking. Arrival history, timestamps, and the admin actor should be recorded in the audit log instead.

## 15. Cancellation and no-show policy

The final cancellation policy, cancellation deadline, cancellation fee, and no-show fee have not yet been determined.

The system should be built so these can be configured later without rebuilding the website.

For now:

- Use clearly marked placeholder cancellation-policy content in development only.
- Keep cancellation-fee and no-show-fee charging disabled.
- Do not invent a fee, deadline, refund amount, or exception.
- Store a version number for every policy.
- Require customers to accept the active policy before booking once final wording is provided.
- Save which policy version the customer accepted.
- Allow the administrator to configure the final cancellation window and fee later.
- Do not enable live cancellation-fee charging until final wording, amounts, and rules are supplied and approved.
- Do not launch live booking until cancellation terms shown to customers match the actual charging workflow.

Once activated, cancellation or no-show charges must require proper customer consent and must be logged.

## 16. Waiver requirements

Customers must review and electronically sign a waiver before completing an online booking.

Record:

- Waiver version.
- Customer's typed legal name.
- Agreement checkbox.
- Date and time accepted.
- Booking confirmation number.
- Relevant audit information.

Do not create final legal waiver wording. Use clearly marked placeholder content in development until approved waiver text is provided.

Do not launch live booking with placeholder waiver wording.

### Phone/admin bookings

For owner-created phone bookings:

- Booking may be confirmed even if the waiver is pending.
- Confirmation email/text should include the waiver link.
- The waiver cannot be completed verbally.
- Customer may sign waiver online before the appointment.
- Customer may sign waiver when arriving for the appointment.
- Owner can open the booking screen and check that the waiver was signed without re-entering customer information.

Recommended confirmation/reminder waiver wording:

> We prefer that you complete your waiver before your visit using this secure link: [Waiver Link]. If you don’t get to it before your appointment, you’ll be able to sign it when you arrive.

## 17. Confirmations and reminders

After a booking is successfully created:

- Generate a unique confirmation number.
- Send an immediate confirmation using the customer's selected method when providers are configured.
- Include booking date and time.
- Include attendee quantities.
- Include itemized price.
- Include amount due.
- Include selected payment method.
- Include payment instructions.
- Include location and arrival instructions.
- Include contact information.
- Include cancellation information.
- Include waiver link for phone/admin bookings with pending waiver.

For phone/admin bookings, confirmation messages should include the waiver link and explain that signing before the visit is preferred, but signing on arrival is available.

Reminder emails/texts should include the waiver reminder and link only if the waiver has not yet been signed.

The administrator must be able to configure reminder timing.

The system must:

- Track delivery status.
- Provide a safe retry process for failed messages.
- Prevent duplicate reminders.

## 18. Admin dashboard requirements

Create a secure admin login and dashboard where the owner can:

- View bookings in calendar and list formats.
- Search by customer name, phone, email, date, or confirmation number.
- View attendee counts and remaining capacity.
- View payment, waiver, and confirmation status.
- Add, edit, cancel, or reschedule bookings.
- Create phone/admin bookings.
- Create admin-only Saturday bookings.
- Enter custom owner-determined prices for group bookings.
- Enter $0 comped bookings.
- Record verbal card consent for phone bookings using an approved script.
- Enter cards through a secure provider-controlled card entry field.
- Record cash, check, and verified Zelle payments.
- Mark customers as arrived.
- Mark no-show or cancelled.
- For credit-card bookings, trigger card charge when customer is marked arrived.
- For cash/check/Zelle bookings, select actual payment at arrival: cash, check, Zelle, or credit card.
- Remove saved backup card after cash/check/Zelle payment is verified and recorded.
- Initiate approved backup-card charges.
- Record and issue refunds if supported.
- Review possible duplicate payments.
- Open, close, add, remove, or edit time slots.
- Block dates.
- Change capacity and pricing for future bookings.
- Configure reminder timing.
- Export bookings to CSV.
- Manage contact information and active policies.
- View a secure audit log of important administrative and payment actions.

The dashboard must not be publicly exposed. It must use secure authentication and authorization.

## 19. Security requirements

The system must:

- Be responsive and accessible.
- Protect customer information.
- Validate and sanitize all inputs.
- Add rate limiting to sensitive operations.
- Prevent overbooking through database transactions or equivalent atomic controls.
- Prevent duplicate bookings.
- Prevent duplicate charges.
- Use idempotency controls for payment actions.
- Verify payment-provider webhooks securely.
- Verify messaging-provider webhooks securely.
- Keep credentials in environment variables.
- Never log sensitive card information.
- Never store full card numbers, CVV, or raw card data.
- Use provider-hosted or tokenized card collection for both customer and admin-entered cards.
- Maintain audit logs for sensitive actions.

## 20. Testing requirements

Automated tests must cover:

- Pricing.
- Capacity.
- Availability.
- Individual bookings.
- Group-booking restrictions.
- Admin custom group pricing.
- Admin $0 bookings.
- Payment status transitions.
- Backup-card charging safeguards.
- Arrival-triggered credit-card charge workflow.
- Cash/check/Zelle payment-at-arrival workflow.
- Backup-card removal after verified payment.
- Zelle reconciliation.
- Waiver requirements.
- Phone booking waiver links.
- Reminder waiver-link logic.
- Cancellation-policy activation.
- Duplicate booking prevention.
- Duplicate charge prevention.

## 21. Documentation requirements for future implementation

Future implementation should include clear documentation for:

- Local setup.
- Environment variables.
- Admin usage.
- Booking operations.
- Payment workflows.
- Waiver operations.
- Deployment.
- Provider account setup.
- Production launch checklist.
