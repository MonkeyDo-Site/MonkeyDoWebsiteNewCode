# MonkeyDo Decision Log

Documentation-only checkpoint created on 2026-08-05. This file records business-rule decisions confirmed by the owner. Open or unresolved items are not marked as decided here.

## 2026-08-05 — Public location and private address

Decision: The public website may say MonkeyDo is located on Budleman Way in Lakewood, New Jersey, but it must not publish the exact street address.

The exact address is confirmation-only:

- 56 Budleman Way
- Lakewood, NJ 08701
- Basement entrance

Confirmation messages should also include the parking note:

- Please park in the driveway or cul-de-sac.

## 2026-08-05 — Public phone and email

Decision: The public phone number is 848-238-5147.

Decision: The public email address is monkeydoplay@gmail.com.

## 2026-08-05 — Public business-hours text

Decision: The public website should use this business-hours wording:

> Open Sunday through Friday by reservation, with four daily time slots.

## 2026-08-05 — Branding direction

Decision: The supplied MonkeyDo logo and advertisement are the visual direction for the website.

Decision: Preserve the original MonkeyDo logo and do not recreate or alter it.

Decision: The brand direction should use the logo/ad personality: soft jungle adventure, sage green, coral/salmon, taupe/beige, cream backgrounds, rounded playful typography, organic shapes, and pill-style buttons.

## 2026-08-05 — Required group-booking message

Decision: The booking page should display this exact group-booking message:

> For group bookings of 10 or more and discounted group rates, please call or text us at 848-238-5147.

## 2026-08-05 — Online group booking behavior

Decision: Customers may book 10 or more children online at the normal public price.

Decision: Discounted group rates cannot be applied online.

Decision: The site should not show a group-rate pop-up during payment.

Decision: The site should not provide an online group-discount request form.

## 2026-08-05 — Admin group pricing

Decision: For owner-created group bookings, the owner should be able to enter any price she determines.

Decision: Admin custom pricing should allow $0 bookings.

## 2026-08-05 — Adult required for every booking

Decision: Every booking must include at least one adult ages 12+.

Decision: A booking cannot have children with no adult.

Decision: A booking cannot have babies with no adult.

## 2026-08-05 — Public pricing wording

Decision: The booking page should use this pricing wording:

> Children ages 1–11 are $15 each. Babies under 1 are free. One free adult per family, and each additional adult is $5. Every booking requires at least one $15 paid admission, which will be applied to a baby or adult if there is no child in the booking.

## 2026-08-05 — Child booking pricing

Decision: If a booking includes one or more children ages 1–11, each child is $15, babies are free, one adult is free, and each additional adult is $5.

## 2026-08-05 — Baby/no-child booking pricing

Decision: If a booking includes babies but no children ages 1–11, one baby is treated as the required $15 paid admission for display and confirmation purposes.

Decision: Additional babies are free.

Decision: One adult is free.

Decision: The second adult and each additional adult after that are $5 each.

## 2026-08-05 — Adult-only booking pricing

Decision: If a booking includes no children and no babies, one adult is treated as the required $15 paid admission.

Decision: Each additional adult is $5.

## 2026-08-05 — Baby plus adult confirmation display

Decision: If a booking has one baby and one adult, the confirmation should show the $15 price going toward the baby, not toward the adult.

## 2026-08-05 — Booking window opens previous day

Decision: A booking date becomes available to customers starting at 12:00 AM America/New_York on the previous calendar day.

Example: For an August 4 booking date, customers can begin booking on August 3 at 12:00 AM America/New_York.

## 2026-08-05 — Same-day bookings

Decision: Same-day bookings are allowed.

## 2026-08-05 — Booking after slot start

Decision: Customers may book a slot after it has started, as long as the slot has not ended.

Decision: A slot closes after its end time.

## 2026-08-05 — Saturday visibility

Decision: Saturday should be hidden entirely from the customer-facing booking calendar.

Decision: Saturday should not be shown as closed to customers.

Decision: The backend should support owner/admin-created Saturday bookings for future seasonal Saturday night bookings.

## 2026-08-05 — Admin-created $0 bookings

Decision: Owner-created $0 bookings do not require a saved credit card.

Decision: Waiver is still required for $0 bookings.

## 2026-08-05 — Phone booking waiver status

Decision: For owner-created phone bookings, the customer should receive a secure waiver link to sign personally.

Decision: The phone booking should be confirmed even if the waiver has not been signed yet.

Decision: The waiver status may remain pending on a confirmed phone booking.

## 2026-08-05 — Waiver cannot be verbal

Decision: A waiver cannot be completed verbally.

Decision: The owner should not be able to mark a waiver as completed based only on verbal consent.

## 2026-08-05 — In-person waiver signing

Decision: A customer who made a phone appointment may sign the waiver during the appointment.

Decision: The owner should be able to open the customer booking screen and check that the person arrived and the waiver was signed.

Decision: The owner should not have to re-enter customer information when marking an in-person waiver as signed.

## 2026-08-05 — Phone booking confirmation waiver wording

Decision: Phone booking confirmation messages should include the waiver link and say signing before arrival is preferred, but signing on arrival is allowed.

Approved wording:

> We prefer that you complete your waiver before your visit using this secure link: [Waiver Link]. If you don’t get to it before your appointment, you’ll be able to sign it when you arrive.

## 2026-08-05 — Reminder waiver wording

Decision: If a customer has not signed the waiver yet, reminder emails/texts should include a reminder to sign the waiver and include the waiver link.

Decision: If the waiver is already signed, reminders should not include the waiver reminder.

## 2026-08-05 — Credit-card charge timing

Decision: Credit-card bookings are not charged at booking time.

Decision: Credit-card bookings are charged after the appointment starts operationally, when the admin marks the customer as arrived.

Decision: The charge is triggered by the admin's arrival action, not merely by time passing.

## 2026-08-05 — Arrival payment choices for non-credit-card bookings

Decision: After a customer is marked as arrived, if the booking is not already a credit-card booking, the owner should see payment options: cash, check, Zelle, or credit card.

Decision: If the owner selects cash, check, or verified Zelle, the payment is recorded accordingly.

Decision: If the owner selects credit card, the saved backup card should be charged.

## 2026-08-05 — Backup card removal

Decision: If the customer pays by cash, check, or Zelle, the payment can be noted and the saved credit card information can be removed.

## 2026-08-05 — Attendance statuses

Decision: Attendance status values should be limited to Arrived, No show, and Cancelled.

Decision: Additional values such as Not arrived, Left, or Completed are not needed.

## 2026-08-05 — Arrival audit fields

Decision: Do not store `arrivedAt` directly on the booking record.

Decision: Do not store `arrivedByUserId` directly on the booking record.

Decision: Arrival timestamps and the admin user who performed the action should be captured in the audit log instead.
