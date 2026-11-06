# Customer email requirements and wording

Consolidated November 5, 2026. This preserves owner-edited wording and the surrounding drafts for documentation-PR review. It is not executable email code and does not send messages. Bracketed fields/conditions are template instructions, never literal customer text. Escape user input, pluralize counts/verbs and render only applicable sections.

## 1. Delivery rules

- **Resend** selected; account exists. Previously exposed credential was revoked/replaced, never reproduced. Sender **bookings@monkeydoplay.com**, replies/owner alerts **monkeydoplay@gmail.com**; sender-domain/DNS/secrets must be securely configured during authorized integration. No Gmail From assumption.
- Every successful booking gets email. No confirmation number or six-digit customer ID in customer emails. If a greeting is needed, **Dear Family [LastName]**, not invented first name. Saved signer/participant full names belong only where applicable.
- SMS deferred post-launch; eventual optional **would you also like to get a text confirmation?**, never replaces required email.
- No appointment reminders, waiver-reminder messages, reminder texts, or appointment-reminder timing controls. Specific membership renewal notices and waiver-completion notifications below are approved exceptions.
- Track recipient, booking/enrollment/cohort, template/version, provider reference, attempt times/status/resend count; Sent is not proof delivered/read. Distinguish Failed/Bounced/unknown. On failed/bounced email, Dashboard+booking alert/history and owner email with safe reason/details; if Resend itself fails, Dashboard persists without relying on owner email succeeding.
- Staff contacts customer, updates email and explicitly resends only affected booking confirmation. Repeat failure/bounce alerts again. Do not blindly resend on unknown delivery outcome; reconcile duplicate risk. Do not send one old confirmation for every historical booking on contact correction.
- At success all public customers see: **You're all set! A confirmation email was sent to [email address]. If you would like to change the email address for the account, please click here.** Actual unsuccessful sending must be reported accurately rather than claiming success.
- Message-history labels: **Booking Confirmation**, **Booking Confirmation with Waiver Link**, **Waiver Completed Notification**, future **Text Confirmation**. Resends are attempts of same type, not separate online/admin/resend message kinds. Membership/program notices retain their actual purpose/linkage.
- When membership and booking purchased together, send **one combined purchase/booking confirmation**, not redundant standalone confirmations. Separate actual charge times remain accurate.
- No successful monthly-installment receipt emails, no separate later membership-refund email, no automatic customer failed-installment email. Optional owner-triggered follow-up exists. Complimentary membership requires explicit Send confirmation Yes/No before closing screen.

## 2. Ordinary booking confirmation

**Subject:** Your Monkey Do adventure is booked!

> **You're all set for your Monkey Do adventure!**
>
> We look forward to seeing you [weekday / date / at time AM/PM].
>
> [Number] adults · [Number] children · [Number] babies
>
> Your total is [amount]. You selected to pay via [method].
>
> [Itemized pricing, one processing-fee row when applicable, one sales-tax row, amount paid/due; sock quantity/unit price/total and “Pick up upon arrival” when selected.]
>
> [Applicable payment instructions.]
>
> [Conditional waiver section.]
>
> Swing your way over to: 56 Budleman Way, Lakewood, NJ 08701
>
> Please use the basement entrance. Parking is in the driveway or cul-de-sac.
>
> [Applicable cancellation footer.]
>
> Get ready to go bananas,
>
> The Monkey Do team

Use adult/child/baby for one and adults/children/babies for other counts. Ordinary paid confirmation may show amount due, not falsely received. Zelle paragraph:

> You selected Zelle as your form of payment. Please Zelle payment to monkeydoplay@gmail.com.

Gift-card choice includes **Gift card must be presented upon arrival** and any second-method balance. Card-funded visit payment is processed after arrival; don't reuse this statement for immediately charged membership/club purchase.

### Cancellation footer conditions

- Ordinary online paid booking, small print: **In the event that you must cancel, please call or text us at 848-238-5147. Cancellation fees will apply.** Do not repeat full policy or calculate that booking's potential fee in email.
- Owner/admin-created paid ordinary booking also includes full supplied policy, small print: **If the booking is cancelled, or the customer doesn't arrive, the customer's credit card will be charged $3 per each $15 admission.** Product membership/supervised terms apply the later $3-per-child rule; see [PAYMENTS.md](PAYMENTS.md).
- Owner-comped $0: **In the event that you must cancel, please call or text us at 848-238-5147.** Omit fee claim and full paid policy.
- Party uses its $50 policy, not ordinary footer calculation. Clubs use their enrollment terms, not ordinary $3 fee.

## 3. Waiver sections

Admin field **Waiver instruction type**: Single Waiver / Multiple waivers. Add appropriate content only when required/chosen; electronic coverage suppresses unnecessary pending-waiver instructions. No automated waiver reminder.

Single:

> We prefer that you complete your waiver before your visit using this secure link: [Waiver Link]. If you don't get to it before your appointment, you'll be able to sign it when you arrive.

Admin multiple (unsigned PDF attachment plus shared signing link, no separate Download waiver button):

> Please see the PDF waiver file attached. Please ensure a parent of each minor who will be coming signs the waiver. Please bring along the signed waivers as they are required. Alternatively, you can send the link below to each parent to sign electronically.
>
> [Sign waiver]

Online option text:

> I am bringing along additional minors and would like to receive the waiver link in my confirmation email so that I can send it to a parent of the minors I will be bringing.

When selected, attach unsigned PDF and include:

> Please see below the waiver link that you requested to send to parents of other minors included in your booking. Alternatively, we've attached a PDF waiver file that you can print, have them sign and bring along when you come.
>
> [Sign waiver]

Shared-link privacy/expiration is in [main requirements](MONKEYDO_REQUIREMENTS.md). Each completion notifies booking customer's **current email**, identifying parent/signing adult and covered minor names; status updates Dashboard without separate staff email. Notification content must distinguish signed participants and booking; do not attach somebody else's completed signed waiver to this email. This is a completion notice, not a reminder.

## 4. New membership confirmations

### A. Subscription

**Subject:** Your Monkey Do Subscription Membership is ready!

> **You're all set for more Monkey Do adventures!**
>
> Your Subscription Membership begins on [weekday, start date] and continues through [end date]. Your membership can always be renewed.*
>
> [Number] Subscription Membership[s]
>
> Enjoy two free play sessions per membership each month, then just $5.99 for each additional play session that month. Your membership also includes two free adults for every visit, 25% off supervised play, and 15% off parties.
>
> [Payment paragraph]
>
> Ready for your next adventure?
>
> [Book a visit]
>
> * After the initial 3 months, membership can be renewed each month, consecutively, without a new 3 month minimum.
>
> Get ready to go bananas,
>
> The Monkey Do team

### B. Unlimited

**Subject:** Your Monkey Do Unlimited Membership is ready!

> **You're all set for more Monkey Do adventures!**
>
> Your Unlimited Membership begins on [weekday, start date] and continues through [end date]. Your membership can always be renewed.*
>
> [Number] Unlimited Membership[s]
>
> Enjoy one free visit per membership each day, with two free adults, plus 15% off parties.
>
> Unlimited Membership benefits exclude supervised play and Chol Hamoed. You may book those visits at full price.
>
> [Payment paragraph]
>
> Ready for your next adventure?
>
> [Book a visit]
>
> * After the initial 3 months, membership can be renewed each month, consecutively, without a new 3 month minimum.
>
> Get ready to go bananas,
>
> The Monkey Do team

### Payment paragraphs

Monthly:

> Your first payment of [amount actually paid] was received. Your next scheduled payment is [amount] on [date].

Prepaid:

> Your payment of [amount actually paid] was received for a [number]-month membership.

When credit used:

> A customer credit of [amount] was applied to this purchase.

Use actual collected amounts including applicable fees/tax, not just base price. No “received” when payment is unresolved. Do not imply prepaid next installment or another first charge after renewal.

## 5. Combined membership and booking confirmation

Owner requested order: introduction (conditional waiver-link overview), **Your visit**, **Your Membership**, benefit usage, payment details, conditional **Waiver**, arrival location, renewal footnote, cancellation/footer. No **Ready for your next adventure / Book a visit** action in this combined email; a visit is already booked.

The following complete **illustrative** example has **five children total**, two adults, two new monthly Subscription places, three ordinary additional child admissions, card payment and **6.6% staging tax**. Production uses approved actual rate, not hardcoded example values. Membership37.06 collected now, visit49.41 at arrival. The three-child variant is50.98pretax/53.53total, not80.98; see [PAYMENTS.md](PAYMENTS.md).

**Subject:** Your Monkey Do membership and visit are ready!

> **You're all set for more Monkey Do adventures!**
>
> Read on for info on your visit, your membership, and the waiver link.
>
> **Your visit**
>
> We look forward to seeing you [weekday, appointment date] at [time AM/PM].
>
> 2 adults · 5 children · 0 babies
>
> **Your Membership**
>
> You've also purchased 2 Subscription Memberships.
>
> Your Subscription Membership begins on [weekday, start date] and continues through [end date]. Your membership can always be renewed.*
>
> Enjoy two free play sessions per membership each month, then just $5.99 for each additional play session that month. Your membership also includes two free adults for every visit, 25% off supervised play, and 15% off parties.
>
> Today's booking uses one free visit from each of your two Subscription Memberships.
>
> **Here's your payment details for the membership and visit:**
>
> Two Subscription Memberships—first month: $35.98 <br>
> Two child admissions using membership benefits: $0.00 <br>
> Three additional child admissions: $45.00 <br>
> Two adults: $0.00 <br>
> Credit-card processing fee: $2.43 <br>
> Sales tax: $3.06 <br>
> **Total: $86.47**
>
> Your first membership payment of $37.06 was received. Your next scheduled membership payment is $37.06 on [date].
>
> You selected to pay via credit card. Your visit payment of $49.41 will be processed after you arrive.
>
> **Waiver**
>
> Please see below the waiver link that you requested to send to parents of other minors included in your booking. Alternatively, we've attached a PDF waiver file that you can print, have them sign and bring along when you come.
>
> [Sign waiver]
>
> Swing your way over to: <br>
> 56 Budleman Way, Lakewood, NJ 08701 <br>
> Please use the basement entrance. Parking is in the driveway or cul-de-sac.
>
> * After the initial 3 months, membership can be renewed each month, consecutively, without a new 3 month minimum.
>
> In the event that you must cancel, please call or text us at 848-238-5147. Cancellation fees will apply.
>
> Get ready to go bananas,
>
> The Monkey Do team

Only include the overview sentence, Waiver heading/content/link and PDF when applicable. Replace package block for Unlimited with complete Unlimited benefits/exclusions. If both types bought, list both packages/cohorts and actual payment dates. Do not omit exclusions merely because email also confirms a visit.

Already-paid in-person conversion uses a transaction-accurate variant showing original payment, replaced admission/tax reversal, credit applied, new amount collected or credit remaining. Never claim a new full payment or phantom credit for unpaid admission. An online combined confirmation is not permission to immediately charge its future visit balance.

## 6. Membership notices

### D. Five days before expiration

**Subject:** More Monkey Do adventures? Your membership ends soon

> **Ready for more Monkey Do adventures?**
>
> Your [number and membership type] [expires/expire] on [date].
>
> We'd love to keep the fun going!
>
> [Renew membership]
>
> Renew within 7 days from when your membership ends with no three-month minimum. Renewal after 7 days requires a new three month minimum.
>
> Get ready to go bananas,
>
> The Monkey Do team

Use expires for one, expire for several. Owner removed the lapse-benefit sentence **from this email only**, not the underlying rule. Cohort-specific dates and 30-day secure renewal-link lifetime must not imply a 30-day grace period.

### E. One day before grace period ends

**Subject:** Your Monkey Do membership renewal window ends tomorrow

> **There's still time for more Monkey Do adventures!**
>
> Your membership renewal grace period ends tomorrow, [date].
>
> Renew by then to renew without a new three-month minimum. Your renewed membership will begin as soon as you renew.
>
> [Renew membership]
>
> We'd love to see you again,
>
> The Monkey Do team

### F. Renewal, including type conversion

**Subject:** Your Monkey Do membership is renewed!

> **You're all set for more Monkey Do adventures!**
>
> Your renewed membership is ready:
>
> [Number and membership type] <br>
> Begins: [date] <br>
> Ends: [date]
>
> [If applicable: Your membership is changing from Subscription to Unlimited / Unlimited to Subscription.]
>
> You can always renew your membership.
>
> [Applicable payment paragraph]
>
> [Book a visit]
>
> Get ready to go bananas,
>
> The Monkey Do team

### G. Additional memberships

**Subject:** More Monkey Do adventures are ready!

> **You're all set for more Monkey Do adventures!**
>
> You've added [number and membership type].
>
> These memberships begin on [date] and continue through [date]. Your membership can always be renewed.*
>
> [Applicable payment paragraph]
>
> Your existing memberships keep their own dates and benefits.
>
> * After the initial 3 months, membership can be renewed each month, consecutively, without a new 3 month minimum.
>
> [Book a visit]
>
> Get ready to go bananas,
>
> The Monkey Do team

### H. Complimentary membership

Send only when owner selects Yes (explicit Yes/No choice required).

**Subject:** A little more Monkey Do fun, on us!

> **You're all set for more Monkey Do adventures!**
>
> We've added [number and membership type] for your family, with our compliments.
>
> Begins: [date] <br>
> Ends: [date]
>
> [Book a visit]
>
> We look forward to seeing you,
>
> The Monkey Do team

### I. Membership cancellation

**Subject:** Your Monkey Do membership cancellation

> Your [number and membership type] will end on [effective date].
>
> [If applicable: You may continue using your remaining membership benefits through that date.]
>
> [If applicable: A refund of [amount] has been processed.]
>
> Thank you for making Monkey Do part of your family's adventures. We welcome you at any time!
>
> The Monkey Do team

One email for cancellation/refund processed together; no statement that processing fee is nonrefundable, no separate later refund email. Financial nonrefund rule itself remains.

### J. Optional owner-triggered failed-installment follow-up

**Subject:** A quick update about your Monkey Do membership

> We couldn't process your scheduled membership payment for [date].
>
> Please update your payment method using the secure link below, or call/text us at 848-238-5147 for assistance.
>
> [Update payment method]
>
> Membership benefits are temporarily unavailable until the payment is resolved.
>
> We look forward to seeing you,
>
> The Monkey Do team

No automatic customer failure message/retry. Link must be securely scoped; actual update/authentication flow depends on verified Banquest configuration.

## 7. Club confirmation drafts retained for review

One family email lists enrolled siblings and applicable occurrence dates, with conditional missing-waiver content. Do not send separate receipts for deferred payment or backup charge already discussed by phone.

### Sunday Club

**Subject:** You're all set for Sunday Club at Monkey Do!

> **You're all set for your Monkey Do adventure!**
>
> We look forward to welcoming [participant names] to [club name].
>
> Get ready for everything you love about Monkey Do, plus baking, crafts, art, and more!
>
> **Your club dates:** <br>
> [Eight scheduled dates and their times]
>
> Your total is [amount]. <br>
> You selected to pay via [method].
>
> [Applicable payment instructions]
>
> [Conditional waiver instructions/link]
>
> Swing your way over to: <br>
> 56 Budleman Way, Lakewood, NJ 08701 <br>
> Please use the basement entrance. Parking is in the driveway or cul-de-sac.
>
> Get ready to go bananas,
>
> The Monkey Do team

### Weekday Club

**Subject:** You're all set for Weekday Club at Monkey Do!

> **You're all set for your Monkey Do adventure!**
>
> We look forward to welcoming [participant names] to [club name].
>
> Enjoy ongoing weekly supervised play in sessions reserved for club members, with friends you'll get to know!
>
> **Your steady day:** [Owner-designated weekday] <br>
> **Your club dates:** [Scheduled dates and their times]
>
> Your total is [amount]. <br>
> You selected to pay via [method].
>
> [Applicable payment instructions]
>
> [Conditional waiver instructions/link]
>
> Swing your way over to: <br>
> 56 Budleman Way, Lakewood, NJ 08701 <br>
> Please use the basement entrance. Parking is in the driveway or cul-de-sac.
>
> Get ready to go bananas,
>
> The Monkey Do team

Payment instructions: card successfully charged **Your payment has been received.** Cash/check **Payment is due at your first club session.** Zelle **Please send payment to monkeydoplay@gmail.com before your first club session.** Apply family sibling/custom price itemization and receipt truthfulness. Private confirmation dates do not violate public semester-date restriction. Enrollment terms prohibit ordinary cancellations/makeups/proration except owner exceptions; no new policy amounts are invented here.

## 8. Party confirmation

**Subject:** Your Monkey Do party is booked!

> **You're all set for your Monkey Do party!**
>
> We look forward to celebrating with you on [weekday, date], from [start time] to [end time].
>
> Your private 75-minute party is booked for:
>
> [Number] children · [Number] adults · [Number] babies
>
> Your party includes grip socks and take-home goody bags for all children.
>
> Party price: [amount] <br>
> Additional guests: [itemization, if applicable] <br>
> Membership discount: [if applicable] <br>
> Sales tax: [amount] <br>
> Credit-card processing fee: [if applicable to card-funded portion] <br>
> **Your total: [amount]**
>
> You selected to pay via [method]. <br>
> [Applicable payment instructions and any amount already paid/due]
>
> [Multiple-waiver instructions, attached unsigned PDF, and shared signing link]
>
> Swing your way over to: <br>
> 56 Budleman Way, Lakewood, NJ 08701 <br>
> Please use the basement entrance. Parking is in the driveway or cul-de-sac.
>
> **Party cancellation policy:** A $50 cancellation fee applies if the party is cancelled or you do not arrive. Your card will be charged the cancellation fee.
>
> Get ready to go bananas,
>
> The Monkey Do team

Compute discount before tax/processing fee. Show one combined tax total (base-item and fee tax), one fee row, actual party inclusions/guest quantities and owner override. Fee row is conditional on card portion; changes at arrival create a revised financial record, not a false claim that booking charged it already. Owner can waive cancellation fee operationally.
