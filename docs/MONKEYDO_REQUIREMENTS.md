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

- The default customer booking horizon is one calendar day: a date becomes bookable at 12:00 AM America/New_York on the previous calendar day.
- The owner must be able to change the customer booking horizon in the admin dashboard to any whole number from 1 through 10 calendar days.
- A horizon of `N` days means that a booking date becomes available at 12:00 AM America/New_York exactly `N` calendar days before the appointment date.
- Changing the setting affects customer-facing availability and must not modify or cancel existing bookings.
- Sunday appointments must become bookable no later than Friday at 12:00 AM America/New_York—the midnight immediately following Thursday night. If the configured general horizon opens that Sunday earlier, the earlier opening remains in effect.
- Same-day bookings are allowed.
- A customer may book a slot after it has started as long as it has not ended.
- A slot closes after its end time.

Example: for an August 4 booking date, customers may start booking on August 3 at 12:00 AM America/New_York.

Sunday example: a Sunday appointment must be available by Friday at 12:00 AM America/New_York. This is Thursday night at midnight and the beginning of Friday.

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
- Configure the customer booking horizon from 1 through 10 calendar days without editing code.
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

Recommended implementation, pending owner approval and legal review:

- Use a first-party, mobile-friendly waiver page integrated with the booking system rather than an image-only waiver or an admin checkbox as the electronic signature.
- Render the complete active waiver as accessible HTML and provide a downloadable/printable copy.
- Require the signer to affirmatively consent to electronic records and signatures, scroll through or otherwise be presented with the complete waiver, check an unselected agreement box, type their legal name, identify their relationship to the participating minor(s), enter the minor name(s), and select a clear `Sign waiver` action.
- Do not use a prechecked agreement box or infer acceptance from booking submission alone.
- Create an immutable signed-waiver record tied to the booking and active waiver version.
- A completed waiver remains valid for one full year from its signing timestamp for the signer and participating minor(s) identified on that waiver, subject to final legal approval and any re-signing rule triggered by a later waiver revision.
- Store both `signed_at` and the calculated `valid_until` timestamp. The customer must sign again when no matching, unexpired waiver covers the relevant participants.
- Preserve an exact snapshot or generated PDF of the text signed, plus a tamper-evident hash, rather than relying only on whichever waiver text is currently active.
- Send or make available a copy of the signed waiver to the signer.
- Provide the same signing page through the confirmation/reminder link and on a customer-facing device at arrival.
- Reserve the owner's `waiver signed` checkbox for recording a genuinely completed paper waiver; it must not substitute for the customer's signature.

Record:

- Waiver version.
- Customer's typed legal name.
- Signer's email address and phone number associated with the booking.
- Signer's relationship to the participating minor(s).
- Names of participating minors covered by the waiver.
- Agreement checkbox.
- Electronic-record/signature consent.
- Date and time accepted.
- Booking confirmation number.
- Signature method.
- Valid-until timestamp.
- Relevant audit information, including IP address, user agent, creation timestamp, and the immutable waiver snapshot/hash, subject to the final privacy and retention policy.

The booking confirmation number is linked to the waiver internally. Because electronic signing is part of the booking flow, the customer must not be asked to enter the confirmation number again.

### Returning-customer waiver check

- Begin booking by asking `Are you a new customer?`
- If yes, proceed to the normal booking fields.
- If no, ask for the customer's name and phone number. Phone numbers must be normalized and displayed in one uniform format, and each customer profile must have a unique phone number.
- If no profile matches, ask `Did you do the previous booking with a different phone number?` If yes, search the supplied previous number.
- If neither lookup matches, treat the person as a new customer.
- If a profile matches, associate the new booking with that customer profile internally. Show only that the customer was identified; do not disclose prior bookings, email addresses, minor names, or other historical profile data in the public flow.
- One customer profile may contain multiple bookings.
- If the applicable waiver was signed more than one year ago, show `Please sign a waiver again. Waivers are valid for one year.`
- Booking does not collect minor names, so the system must not infer which minors are attending from booking data. When an unexpired waiver for the active version exists, ask `Will minors not listed on the previous waiver be coming to MonkeyDo now?` If yes, require an electronic waiver for those additional minors.
- Activating a new waiver version requires a new signature even when the prior version was signed less than one year ago.
- A February 29 waiver expires at the same local time on February 28 of the following non-leap year in America/New_York.

The authenticated owner/admin may search electronically signed waivers by minor name and see whether the minor has a signed waiver, its signer, version, signing time, and expiration. Paper waivers are represented only by an audited completion checkbox at initial launch; their minor names are not entered into the system, so they do not support minor-level search.

Do not create final legal waiver wording. Use clearly marked placeholder content in development until approved waiver text is provided.

Do not launch live booking with placeholder waiver wording.

The owner supplied a waiver image during planning. Treat it as a draft/reference, not automatically as legally approved production wording. Obtain the original text or source document for accessible implementation and have qualified New Jersey counsel approve the final text, signer fields, electronic-consent language, minor/guardian workflow, and retention period before activation.

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

Resend is the selected transactional email provider, and the owner has created the Resend account. The owner confirmed that the API credential disclosed during planning was revoked and replaced. Only the replacement credential may be used, and it must be supplied through a secure secret-management channel and stored in an environment variable or deployment secret—not in source code, documentation, logs, chat, or client-side code.

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

For waiver-reminder purposes, an expired waiver or a waiver that does not cover the relevant signer/minor participants must be treated as requiring a new signature. An unexpired matching waiver should suppress the reminder unless a final policy requires re-signing after a waiver-version change.

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

## 21. DigitalOcean VPS hosting direction

The owner wants the website and backend hosted on a VPS using DigitalOcean.

Future implementation should plan for:

- A DigitalOcean Droplet/VPS for the website, backend, and admin dashboard.
- A persistent PostgreSQL database running initially on the same VPS to reduce cost, with automated encrypted off-VPS backups and tested restoration procedures.
- An application architecture that permits a later move to DigitalOcean Managed PostgreSQL without rebuilding the application.
- Deployment in a New York DigitalOcean region, subject to availability.
- Secure server provisioning with SSH keys, firewall rules, HTTPS, backups, monitoring, and environment-variable based secrets.
- No credentials, API keys, database passwords, or provider secrets committed to the repository.

The owner has confirmed that the DigitalOcean account supports the required services and currently has free credit; paid billing will be activated when needed. The production domain is being purchased, and its external domain provider will manage DNS and point it to DigitalOcean.

Actual VPS setup still requires scoped DigitalOcean access, the final domain/DNS records, an SSH public key, Droplet size, backup/retention choices, monitoring contact details, and production environment variables. Until the production domain is connected, testing may use the Droplet public IP or a configured temporary hostname.

## 22. Documentation requirements for future implementation

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

## 23. Recommended technical architecture

This is the approved planning direction, not application or deployment code:

- A server-rendered, mobile-first web application with public booking pages and a protected owner dashboard in one maintainable codebase.
- A backend service that is the sole authority for availability, pricing, waiver state, booking creation, attendance, and payment-state transitions.
- Persistent PostgreSQL running initially on the DigitalOcean VPS.
- Database transactions and row-level locking or an equivalent atomic mechanism for capacity enforcement.
- A background-job mechanism for confirmations, reminders, retries, webhook processing, and operational reconciliation; jobs must be durable and idempotent.
- Provider-hosted/tokenized card collection; no raw card data passes through or is stored by MonkeyDo.
- Resend for transactional email once the sender domain, DNS, replacement server-side credential, templates, and retry rules are configured.
- An SMS provider only after selection, account/compliance setup, credentials, and wording approval.
- HTTPS reverse proxy, application process supervision, monitoring, encrypted off-VPS database backups, and restore testing on DigitalOcean.
- Environment-specific configuration and secrets supplied outside source control.

The exact application framework, authentication library/provider, ORM/database migration tooling, background-job implementation, and SMS provider remain implementation selections. They must satisfy this requirements document and the unresolved constraints in `OPEN_DECISIONS.md`.

## 24. Page and screen inventory

### Public/customer pages

- **Home:** introduction, brand story, visual overview, public Budleman Way/Lakewood location wording, hours, contact details, and prominent Book Now action.
- **Book Now / availability:** dynamic date and slot availability shown before personal booking information is requested; exact group-rate message; pricing explanation.
- **Booking details:** customer contact information, attendee quantities, referral source, confirmation preference, and payment-method choice.
- **Card and consent:** provider-controlled card setup plus explicit card-on-file and later-charge consent.
- **Review and sign:** itemized pricing, attendee totals, payment instructions, active cancellation terms, and required electronic waiver for customer-created online bookings.
- **Booking confirmation:** confirmation number, appointment and attendee details, price, amount due, payment method/instructions, private full address and arrival details, contact details, cancellation information, and waiver status/link when applicable.
- **Secure waiver link:** booking-linked signing page for pending phone/admin bookings and arrival signing.
- **Contact:** public phone, email, Budleman Way/Lakewood wording, reservation-only hours, and no public exact street address.

### Owner/admin pages

- **Admin login:** protected authentication entry point.
- **Dashboard:** operational summary, upcoming bookings, payment/waiver/message exceptions, and capacity alerts.
- **Calendar:** slot/date occupancy and remaining capacity.
- **Booking list:** searchable/filterable bookings and CSV export.
- **Booking detail:** customer and attendee data, status, waiver, messages, payment history, arrival actions, edits/rescheduling, and audit history without re-entering customer data.
- **Create booking:** phone/group/admin-only Saturday booking, custom price including $0, consent recording, and provider-controlled card setup when required.
- **Schedule and availability settings:** recurring slots, date overrides, closures, capacity, public/admin-only visibility, and 1–10 day booking horizon.
- **Pricing settings:** future effective pricing without changing historical booking snapshots.
- **Payment operations:** expected/received payment recording, explicit backup-card charge confirmation, card charge after arrival, failures, refunds if enabled, and duplicate-payment review.
- **Messaging settings:** reminder timing, templates/status, safe retry, and delivery history.
- **Policy and waiver settings:** versioned cancellation terms, fee activation gates, waiver versions, validity/status, and business/contact settings.
- **Admin users/security:** users and roles if enabled, credential/MFA controls, and session management.
- **Audit log:** immutable searchable record of sensitive administrative, waiver, booking, and payment actions.

## 25. Conceptual database structure

The eventual schema may use different names, but it must preserve these entities and relationships:

- **admin_users / roles / sessions:** owner or staff identities, authorization, and secure sessions.
- **customers:** normalized contact information and payment-provider customer reference; never raw card details.
- **schedule_templates:** recurring day-of-week slot definitions and visibility.
- **slot_occurrences:** date-specific slot, start/end times, capacities, price configuration reference, status, and overrides.
- **date_overrides:** open/closed/blocked dates, holiday reason, and admin-only availability.
- **pricing_versions:** effective-dated child/adult/minimum-admission configuration for future bookings.
- **bookings:** confirmation number, customer, slot occurrence, booking/attendance statuses, source, confirmation preference, attendee quantities, totals, selected payment method, immutable price snapshot, amount due/received, and timestamps.
- **booking_participants:** signer/minor names or other participant identity data required for waiver coverage, subject to approved data-minimization rules.
- **booking_price_items:** immutable itemized labels, quantities, unit prices, and line totals.
- **payment_methods:** provider token/reference, limited safe display metadata, consent reference, status, and removal timestamp; never PAN, expiration date, or CVV.
- **payment_consents / policy_acceptances:** consent type, exact terms/policy version, accepted timestamp, signer, booking, and audit metadata.
- **payment_transactions:** charge/refund/provider references, amount, status, idempotency key, reason, initiating admin, and timestamps.
- **payment_events:** append-only provider and manual status history used for reconciliation and duplicate-payment review.
- **waiver_versions:** approved immutable text/source snapshot, version, effective state, and validity configuration.
- **signed_waivers:** signer, covered participants, booking, waiver version, signed/valid-until timestamps, signature method, immutable snapshot/hash, and audit metadata.
- **message_templates / reminder_settings:** versioned confirmation/reminder content and timing.
- **message_deliveries:** channel, recipient, booking, template/version, provider reference, idempotency key, delivery status, attempts, and timestamps.
- **audit_log:** append-only actor, action, target, before/after-safe metadata, reason, timestamp, and request context without secrets or card data.
- **application_settings:** versioned business contact, booking-horizon, Zelle instructions, and other configurable operational settings.

Capacity acceptance and booking insertion must occur in one database transaction. Payment actions and message deliveries require unique idempotency keys/constraints. Historical price, policy, consent, waiver, and message records must not be silently rewritten when future settings change.

## 26. External services and accounts

- **Hosting:** DigitalOcean account with Droplet, billing, backups/snapshots, monitoring, SSH access, and eventual production DNS records.
- **Database:** PostgreSQL on the initial VPS plus a separate encrypted backup destination; DigitalOcean Managed PostgreSQL remains a migration option.
- **Payments/saved cards:** provider still awaiting final approval; Stripe is the current recommendation. The account must support tokenized cards, SetupIntent-style authentication, later off-session charges, refunds, idempotency, and signed webhooks.
- **Email:** Resend is selected and the account exists. The disclosed credential was revoked; the replacement must be installed securely. Sender-domain verification, DNS, templates, and delivery handling remain.
- **Text messaging:** provider still awaiting final selection; Twilio is the current recommendation. Account/number, registration/compliance, opt-in/out language, templates, and credentials are required.
- **Authentication:** no separate hosted authentication account is required if secure server-side authentication is implemented in the application; final implementation and MFA/role requirements remain open. If a hosted provider is selected later, its account and production configuration will be required.
- **Waiver documents:** the approved source waiver and immutable signed snapshots require secure storage and retention; exact local encrypted storage versus DigitalOcean Spaces remains open.
- **Domain/DNS:** the owner is purchasing the domain; the external registrar/DNS provider will point approved records to DigitalOcean.

No provider-dependent feature is production-ready until the applicable account is verified, production credentials are installed securely, required policies/wording are approved, webhooks are verified, and end-to-end production-readiness tests pass.

## 27. Phased implementation and launch gates

1. **Requirements approval:** owner confirms this consolidated checkpoint and resolves implementation-blocking questions.
2. **Foundation:** select framework/tooling; establish database migrations, validation, timezone handling, authentication, authorization, audit primitives, and test infrastructure.
3. **Public experience:** implement accessible responsive branding, Home, Contact, availability, and pricing/group messaging using original assets.
4. **Booking core:** implement schedule configuration, transactional capacity enforcement, pricing snapshots, booking creation, admin-created bookings, and automated rule tests.
5. **Admin operations:** calendar/list/detail screens, search/export, attendance, rescheduling/cancellation, settings, and audit log.
6. **Waiver:** implement versioned signing and annual validity only after approved text/workflow are supplied; test online, phone-link, reminder, and arrival scenarios.
7. **Provider integrations:** integrate payment sandbox, Resend, and selected SMS provider with consent, authentication, idempotency, signed webhooks, retries, and reconciliation.
8. **Payment operations:** implement arrival-triggered card charges, alternate-payment recording, backup-card safeguards, failures, refunds if approved, and duplicate review.
9. **Infrastructure/staging:** provision hardened DigitalOcean staging, PostgreSQL backups/restore tests, HTTPS, monitoring, secrets, migrations, and smoke tests.
10. **Production readiness:** accessibility, security, concurrency, workflow, backup/restore, provider, and owner acceptance testing; approve final policies/templates and legal wording.
11. **Controlled launch:** configure production domain/DNS and credentials, run migrations/smoke tests, enable only approved workflows, monitor closely, and retain rollback procedures.

Live booking must remain disabled if the displayed waiver or cancellation terms are placeholders or do not match enabled charging behavior. Cancellation/no-show charging remains disabled until separately approved. No documentation statement alone constitutes production readiness.
