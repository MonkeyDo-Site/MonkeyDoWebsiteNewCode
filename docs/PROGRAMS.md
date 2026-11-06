# Supervised play, clubs, parties, gift cards, and socks

Current owner requirements, November 5, 2026. Shared [customers/waivers/admin](MONKEYDO_REQUIREMENTS.md), [membership benefits](MEMBERSHIPS.md), [payments/tax](PAYMENTS.md), and [email copy](EMAIL_TEMPLATES.md) apply unless this document states a product-specific exception. No implementation is included.

## 1. Supervised play

- Ages **3–11**, child-only/drop-off; no baby/adult quantities or ordinary adult requirement. Customer selects accompanied ordinary play or supervised; cannot mix in one booking.
- **$18.99** per child; **$14.24** (25% off, rounded per child) up to paid active Subscription-place count; extra children $18.99. Unlimited is full price. Example 3 Subscription places+4 supervised children: **$61.71** before fees/tax.
- Owner enables per session and sets **supervised-play capacity** within total child/combined customer capacity, not extra spaces. Employees excluded from website customer occupancy count. Do not rename this a staffing ratio or employee limit.
- At supervised capacity hide that option; accompanied booking can remain available if overall space exists. Normal horizon applies, but **no supervised booking after start**; accompanied booking until end.
- Applies to owner-designated normal or one-off sessions. One-off settings designate public/backend, modes, overall capacities and supervised subset.
- Ordinary waiver rules, no additional supervised consent. Do not add declined emergency/medical/pickup-code/child-DOB/name fields. Club named-participant data is a separate workflow.
- Cancellation/no-show **$3 per child** unless waived, including discounted supervised admissions. Subscriptions' ordinary free visits are not consumed by supervised discounts.
- Public information belongs on About, not a new Play page. Drop-off instructions should accurately describe this agreed service without inventing pickup/late fees or identity checks.

## 2. Clubs: common model

Public marketing only, **call/text to enroll**; no online club checkout. Owner manages enrollment in backend. Keep program/semester, generated occurrences, participant, enrollment, payment/waiver and occurrence attendance distinct from ordinary bookings, sharing secure payment components rather than pretending enrollment is a normal play booking.

| Rule | Sunday Club | Weekday Club |
|---|---|---|
| Default duration | 8 weekly sessions | 8 weeks |
| Default schedule | Sunday **11 AM–1 PM** | Tuesday or Thursday **5:30–6:30 PM** |
| Age | **3–8** | **3–8** |
| Price per child | **$279** | **$129** |
| Additional siblings | **10% discount each** | **10% discount each** |
| Member discount | None | None |
| Activity | Play, baking/art/crafts and other activities | Supervised play only; no creative-activity promise |

- Owner may enter custom price including $0. No automatic club capacity/waitlist enforcement; backend enrollment is owner-controlled.
- Semester labels such as Sunday Club Winter 5787; generate eight weekly dates, allow exclusions/roll forward, label Session1–8, change default/semester/individual times. Tuesday/Thursday groups generate independently.
- Club children do not automatically consume ordinary public-play capacity. Owner explicitly chooses **Allowed/Blocked** for overlapping public sessions. No location field or inferred occupancy warning.
- On time/date change show newly and no-longer overlapping sessions; require explicit allowed/blocked choices before save instead of silently reusing old ones. Preserve old/new audit and past/completed occurrences; alter current/future as chosen. No automatic schedule-change emails.
- Weekday group/day or particular occurrence may be changed by owner, including after enrollment/start. No normal customer switches/makeups/proration; owner can make exceptions and custom-price late joiners.
- Enrollment status: **Active / Cancelled / Completed**. Do not use Withdrawn. Owner may cancel after repeated no-shows; no automatic numeric absence cutoff is specified.

### Participants and waivers

- Reusable participant linked to one customer: first/last name, DOB, backend-only never-reused **P000001** ID, enrollments/history. No duplicate participant-level customer phone/email fields.
- Age as of semester enrollment; turning nine during term is allowed. Out-of-range enrollment warns rather than blocks. Refresh on next enrollment; DOB corrections recalculate enrollment-age information using relevant reference date.
- Staff correct name/DOB; audit prior values and attendance changes. Spelling correction preserves confirmed waiver association. Participant merge tool deferred post-launch.
- Match electronic waiver minors only within the customer context with normalized-name suggestions; unclear match needs owner/staff confirmation. No DOB added to waiver for matching; no cross-customer automatic association.
- Per-participant electronic coverage/current version/expiry and paper completion. Paper checkbox cannot fabricate file/signature. Obtain coverage before participant arrival; offer signing then. One family email includes sibling list and shared waiver link if any need signature; multiple guardians may use same link.
- Printed roster: participant name, family phone, enrollment age, waiver status. Show participant ID digitally and in exports; omit from the default printed roster unless selected. No free-text comments on normal rosters.
- Exports: all/by-club participants, missing waivers, enrollment history, payments and **attendance by occurrence** (one child/date row, status, actor/time). Apply export permissions.

### Attendance warning

Occurrence attendance: **Arrived / No show / blank**, staff may correct with audit. On leaving an individual relevant attendance page with blank state:

> Attendance is blank. Would you like to mark it as Arrived or No show?

On leaving a whole relevant roster with blanks:

> There are some participants whose attendance is blank. Would you like to mark them as arrived or no show?

Offer review/marking and **Leave attendance blank**. Do not force speculative attendance or overwrite marked participants; future sessions do not warn just because attendance has not occurred.

### Enrollment payment and follow-up

- Card charged at enrollment, not ordinary-play arrival. Cash/check due at first attended session; Zelle before first session; backup card required for alternative methods.
- First attendance handles unresolved payment with explicit confirmation before any backup-card charge. Staff may finish allowed attendance while deferring a payment issue with required follow-up date.
- First-session no-show: payment-required issue immediately, default follow-up **three days**, contact customer before explicit backup-card charge. Full semester still due, no ordinary $3 club no-show charge; do not wait indefinitely for attendance or automatically charge that day.
- Payment resolved once; do not collect again at each occurrence. Only owner changes enrollment price during follow-up. Staff help contact/resolve; no separate automatic receipt or after-phone-contact charge email.
- Owner exception refund any entered amount through provider, original processing fee not refunded, optional customer refund email; preserve original/refund audit/payment history. Club itself nontaxable. No normal cancellations/makeups; owner exceptions remain.

### Public wording

Owner visibility toggle hides Clubs/programs without deleting records. No exact semester dates or “Spaces are limited.” Generic intro removes “create,” which is Sunday-specific.

Sunday:

> A playful Sunday program filled with everything you love about Monkey Do plus activities such as baking, crafts, art, and more. Call or text us for current session details and registration.

Weekday:

> Enjoy ongoing weekly supervised play at Monkey Do in slots reserved only for club members. For children ages 3-8. Choose [Tuesdays] or [Thursdays] as your steady day. Play and explore each week with friends you get to know.

Fill weekday choices from owner program settings. Contact **848-238-5147**. No separate public registration forms.

## 3. Parties

- Rename former Special Events offering **Parties**. Generic public offering on combined page, no public individual-party records or online checkout. Customer calls/texts; owner creates/prices party.
- **$289**, **75-minute private session**, includes **10 children +10 adults**, goody bags and grip socks for all children, including paid additional children. Under-one babies excluded from child count.
- Additional child **$19.99**, additional adult **$5**. Included extra-child socks are in that price, not another sock line.
- One active Subscription or Unlimited place of booking customer qualifies whole party for **15% discount on package plus applicable guest charges**, before tax/processing fee. May combine with special owner price; owner may override discount. Separately sold socks do not get member discount.
- Any standard or owner-created custom session; owner-entered quantities with no fixed system maximum. Entire session unavailable publicly, gray **A party is booked for this slot.**
- No deposit; backup card required. Payment cash/check/Zelle/gift card/card or max-two-method split. Party payment follows final attendance review, with quantities initially booked and editable/repriced at arrival.
- No named-attendee entry or individual child attendance; quantities plus waiver-covered minors and final totals. Shared multi-parent link, signed waivers all associated party.
- **$50 cancellation/no-show fee**, owner may waive. Backend notice for owner to read aloud; confirmation includes **A $50 cancellation fee applies if the party is cancelled or you do not arrive. Your card will be charged the cancellation fee.** Do not apply $3-per-child ordinary policy instead.
- Public full package/inclusion/add-on pricing, not only “starts at.” Confirmation includes date/time, counts, totals/due/payment, socks/goody bags, shared waiver/PDF, private address/parking and cancellation policy.

## 4. Physical gift cards and split tender

Owner expressly rejected a digital gift-card balance ledger. Do **not** implement gift-card IDs/PINs, online balance validation/check page, digital activation/balance decrement, loss replacement or cancellation/balance-adjustment tools as if approved.

- Physical cards sold **in person** by owner/staff, from customer record. Enter quantity/face value line items (e.g.2×$50,3×$75). No face-value minimum/maximum, no expiration. Remaining value written on physical sticker, partial use across visits allowed.
- May pay ordinary/supervised admissions, memberships, clubs, parties, socks, cancellation/no-show fees; cannot buy another gift card.
- Card-paid $100 gift-card sale has $100 face value plus applicable card fee, not $103 face value. Sale nontaxable; underlying redeemed goods/services retain own tax classification.
- Gift-card sales CSV; no separate gift-card-redemption export requested. Keep transaction tender amounts without claiming to track physical remaining balances.
- Public Gift card choice immediately asks: **Does your gift card cover the full amount of this purchase? If not, choose another payment method for the remaining amount.** Permit one second method (card/cash/check/Zelle). Backup card required even if gift card expected to cover everything.
- Booking and confirmation: **Gift card must be presented upon arrival.** Staff verifies presented card/amount and manually updates sticker. Never assume online choice proves funds received.
- If second tender is card, charge only remaining approved amount. If alternative payment is missing/short, authorized backup-card flow covers unpaid remainder.
- Maximum two finalized methods per transaction. New gift-card sale alongside booking payment is a separate sale transaction, not a misleading split booking payment.
- Preserve received first tender if second fails: $75 due, $40 cash received, $35 card fails -> $40 received/$35 unpaid, resolve only remainder. Never retry full $75 or invent return of cash.
- Phone cancellation with physical gift card not presented/verified charges backup card under applicable fee policy.
- Proportional allocation of taxable/nontaxable value for card portion is approved; [PAYMENTS.md](PAYMENTS.md) explains fee/tax examples. Customer conversion credit is a separate application ledger, not physical-card balance tracking.

Public notice initially:

> MonkeyDo Gift Cards <br>
> Gift cards are available for purchase in person. Ask us during your visit or call/text for details.

Contact page: **Gift cards are available for in-person purchase.** Owner may revise placement after staging.

## 5. Grip socks

- Required for playing children; babies/adults do not need them. Reusable, customers may bring their own. **$1.99 per pair**, nontaxable.
- Checkout copy stays exactly:

> Grip socks are required for play at MonkeyDo. You can pay for them now or bring your own. Please select the amount you want to purchase.

- Default quantity **0**, typed and/or plus/minus controls, maximum **35 online** regardless of child count. In-person quantity unrestricted. Warn, do not block, when fewer pairs than children. No inventory, size or color fields.
- Booking-selected socks join booking total and its payment flow; “pay now” copy does not cause a separate immediate ordinary-booking charge. Pick up at arrival.
- Staff may add at door or reduce before charge (e.g.6 reserved,5 wanted -> recalculate5). Gift cards usable; if alternate payment absent, added socks may be part of approved backup-card charge.
- Itemize quantity/unit price/total and **Pick up upon arrival** in confirmation. No separate member discount on independently sold socks; party includes pairs for all child guests.
- Before first charge, calculate final total using stored provider payment source; do not automatically destroy/recollect card solely because quantity changed. Validate account-specific processor behavior. After successful completed charge, a later sale is a separate transaction, not mutation of settled history.
