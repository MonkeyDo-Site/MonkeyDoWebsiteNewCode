# MonkeyDo current website requirements

Consolidated November 5, 2026 from history prompts A–AG and later owner answers. This document replaces the older planning checkpoint for current requirements. Specialized rules live in the linked companion documents. All behavior below is an implementation target unless explicitly identified as existing evidence.

## 1. Scope, status, and approvals

Build a welcoming, polished, mobile-friendly, accessible website for MonkeyDo, a children's indoor playspace in Lakewood, New Jersey. Initial scope: public content, ordinary bookings, Subscription and Unlimited memberships, supervised play, clubs, parties, physical gift-card sales/tender handling, socks, electronic waivers, customer records, owner/staff administration, and email workflows.

SMS, participant merging, day-camp/group invoicing, and possible automatic payment retries after operational review are post-launch enhancements. Scanning/uploading paper waivers is not required initially.

The owner subsequently authorized staging website/database development and explicitly approved Django with PostgreSQL; see [development status](DEVELOPMENT.md). The original documentation checkpoint was not an implementation. Production deployment, Cloudflare DNS connection, live payments (including approved cancellation charging), and opening customer booking each need separate written approval. Cancellation activation is not a separate fifth production approval. Present current recurring costs before purchasing or provisioning infrastructure.

## 2. Public identity and visual direction

- Public phone: **848-238-5147**; public email: **monkeydoplay@gmail.com**.
- Public location: Budleman Way, Lakewood, New Jersey. Do not publish the exact street address on public pages.
- Private confirmation location: **56 Budleman Way, Lakewood, NJ 08701**; basement entrance; parking in the driveway or cul-de-sac.
- Future canonical site: **https://monkeydoplay.com**; `www.monkeydoplay.com` redirects there. Cloudflare DNS/proxy, DigitalOcean application hosting. Internal protected temporary access is not the public launch plan.
- Normal hours wording: **Open Sunday through Friday by reservation, with four daily time slots.**
- Preserve the original MonkeyDo logo exactly; do not recreate, redraw, generate, or alter it. Original logo/ad and real facility photography guide the design. See [asset handling](brand-assets/README.md).
- Warm, playful, calm, polished, boutique, parent-trustworthy, soft jungle/adventure character; sage, coral/salmon, taupe/beige, cream/warm white and natural wood; readable dark text. Rounded typography, pill controls, organic photo frames, soft cards, restrained leaf/banana/star/monkey accents. Avoid generic bright-primary-color presentation.

### Approved public copy

Main headline: **Every little monkey needs a jungle.**

Supporting phrase: **Designed by mothers and professionals who get kids.** This replaces the old mothers/therapists claim in advertisement text. **Go Bananas Here** is a graphic accent.

Age line: **Designed for little monkeys ages 1–10.** Eleven-year-olds are still admitted at the child rate; marketing age wording does not change pricing categories.

Homepage introduction:

> Where sensory stimulation, imaginative play, swinging, climbing, sliding and endless enjoyment combine to give children an enriching and engaging experience they will want to return to time and again.

About introduction:

> Have you been looking for a place where your children can spread their wings and engage in a combination of stimulating, energizing and relaxing play spaces, in a warm and welcoming setting? Monkey Do is that place. Designed by mothers and professionals who get kids.

| About area | Approved description |
|---|---|
| Imaginative Play | Creative stations and playful props invite children to invent stories, explore ideas, and bring imaginary adventures to life. |
| Game Room | Lights, action, and sound come together for fun, collaborative team play. |
| Climbing Area | Energetic fun with slides, a ball pit, foam pit, climbing wall, and monkey bars. |
| Toddler Zone | A welcoming space designed for little ones, with swings, a toddler-friendly ball pit, and tabletop toys. |

Use owner-supplied photos for these four areas; do not substitute a new area inventory based on a later assistant suggestion. Short image alternative text is accessibility metadata, separate from approved visible copy, to be drafted with actual photo selection. No separate program-specific imagery is required.

## 3. Public pages and navigation

- **Home:** approved headline/introduction, facility visuals, public location/hours/contact, prominent Book Now.
- **About:** introduction, four approved photo areas, ordinary and supervised-play options. No separate Play page. The isolated phrase “reserved play” in AG is not authorization for a new product.
- **Memberships, Clubs & Parties:** one combined page; membership purchase entry, approved package descriptions, party inclusions/pricing, seasonal club information, gift-card notice.
- **Book Now:** show schedule and availability before requesting personal information; pricing/group message, customer lookup/details, attendee counts, payment/consent, waiver, review, confirmation.
- **Contact Us:** public phone/email/location/hours, gift-card notice, no public exact street address. General secondary contact actions say Contact Us; group instructions retain call/text wording.
- Secure booking-linked waiver page for phone/admin booking, shared parent links and signing at arrival.

Owner controls public Clubs visibility and individual program visibility without developer deployment or deleting backend history. Do not display exact semester dates or “Spaces are limited” publicly. Club confirmation emails do include actual dates. Keep gift-card notice on the combined page and Contact initially; no separate gift-card page.

Public club wording is in [PROGRAMS.md](PROGRAMS.md). Final navigation arrangement and image crops are staging acceptance choices, not new requirements blockers.

## 4. Schedule and availability

| Default public session | End |
|---|---|
| 11:30 AM | 12:45 PM |
| 1:00 PM | 2:15 PM |
| 2:30 PM | 3:45 PM |
| 4:00 PM | 5:15 PM |

- Operate Sunday–Friday using **America/New_York** for calendar openings, appointments, membership usage, deadlines, and DST-aware comparisons.
- Default public horizon: one calendar day. A date opens at midnight on the previous calendar day. Owner may set any whole number 1–10; provide **Revert to default: 1 day** with confirmation. Changes do not change/cancel existing bookings.
- Sunday opens no later than Friday 12:00 AM (midnight after Thursday night). If the general horizon opens it earlier, use the earlier date.
- Ordinary same-day bookings remain available after start until the session ends. Supervised bookings close at start; see [PROGRAMS.md](PROGRAMS.md).
- Hide Saturday entirely in the normal public calendar, rather than marking it closed. Support admin-only Saturday/seasonal Saturday-night bookings.
- Derive availability from real bookings, capacities, closures, visibility, and owner overrides. No automatic holiday rules: owner manually blocks dates up to two years ahead, entering a private reason. Customers see generic unavailability, not the reason.
- Show all relevant session times. Unavailable sessions are gray/nonclickable. Ordinary full sessions say **Fully booked**; party sessions say **A party is booked for this slot.**
- When the date is fully booked: **We're all booked for the date you want. We would love to see you another time.**
- Owner can change recurring slots, per-date times/capacity, closures, visibility, and add one-time sessions outside normal hours. One-time sessions have an internal label. Ask owner to designate public/backend-only; accompanied/supervised/both; overall child/combined limits and supervised limit when applicable. Do not silently expose a backend-only program.

## 5. Capacity, groups, and timing changes

- Babies under one do not count. Children 1–11 and adults 12+ count.
- Normal defaults: **35 children maximum and 50 children plus adults combined**, both enforced. Do not treat the older 30-child reference as a separate current booking cutoff.
- Owner may configure session-specific limits and explicitly override capacity. Owner override does not require an extra confirmation/reason field; automatically audit it.
- Staff may change attendee quantities before arrival on customer request and during arrival. Arrival-specific capacity override permits unexpected extra attendees; advance moves into a full session require owner override.
- Staff may change timing to an available slot on the same or another date. Release old capacity and reserve new capacity atomically. Preserve old/new timing, actor/time and rescheduled history; only current slot consumes capacity.
- Discounted group bookings are owner-entered/custom-priced, including $0. No online discount, online discount-request form or payment pop-up. Customers may book 10+ children online at normal pricing if capacity permits.
- Ask whether an owner-created group is exclusive. Exclusive groups block the whole session regardless of entered headcount, permit owner-entered attendee quantities without a system maximum, and use owner price. Nonexclusive groups count toward normal limits.
- Display exactly: **For group bookings of 10 or more and discounted group rates, please call or text us at 848-238-5147.**
- Failed capacity acceptance must not save a confirmed booking or charge a payment. Protect capacity and membership-benefit reservations against concurrent requests.

## 6. Ordinary pricing and booking inputs

Ordinary rates before tax/card fees: children 1–11 **$15**; babies under one normally free; one adult free; each additional adult **$5**. At least one adult 12+ is required for ordinary play. Supervised drop-off is the approved exception.

| Ordinary attendee mix | Admission calculation |
|---|---|
| At least one child | $15 per child + $5 × max(adults − 1, 0); babies free |
| Babies, no children | One baby supplies required $15 admission; additional babies free; first adult free, additional adults $5 |
| Adults only | First adult supplies required $15 admission; each additional adult $5 |

Member free/discounted admissions and adult benefits override ordinary pricing as specified in [MEMBERSHIPS.md](MEMBERSHIPS.md). An owner-comped $0 booking is different from a member's free visit, which still has applicable cancellation obligations.

Collect Last Name, phone, email, date/session, baby/child/adult quantities, calculated total (never re-enter total manually), referral source, payment method and appropriate consent/waiver. Supervised and club field exceptions are in [PROGRAMS.md](PROGRAMS.md). Email is mandatory; SMS is a later optional additional text confirmation, not a replacement email preference.

Validate in browser and server: required fields/consent, nonnegative integer counts, nonzero attendance, adult rule where applicable, card setup unless owner-comped, availability/end time, capacity and permissions. Online waiver must be covered before booking completes; admin/phone bookings may confirm pending.

Show an itemized calculation before confirmation. Save immutable price/tax/fee/policy snapshots; an authorized edit creates a new revision with before/after audit, not silent rewriting of the original. Future owner pricing/settings do not alter accepted existing bookings or cohort prices.

## 7. Customers and public identification

- Profiles have **Last Name** only, not a separate first/full-name field. If a greeting is used: **Dear Family [LastName]**. Waiver signer full legal name and named club participants are separate entities.
- Assign backend-only sequential six-digit customer IDs starting **000001**, never reused. One customer may have many bookings and membership cohorts.
- Customer type is customer-level **Family** or **Day Camp** only. Public customers default Family, no type question. A camp name uses Last Name; director/contact details may be searchable comments. Owner can change customer type with history preserved. No Both category or booking-level organization layer.
- Current phone is unique; retain one Previous phone. Retain Current email and one Previous email. Normalize phone storage/display/search consistently. Owner resolves reassigned previous numbers before reuse; do not create duplicate customer accounts for the same match.

### Public flow

1. Ask whether the customer has visited before. Search current and previous phone fields. New-customer entry also silently searches after phone entry.
2. If no profile matches, continue new booking without announcing an internal search. Support trying a prior phone when a returning lookup fails.
3. On a current-number match, including a supposedly new customer, say: **Looks like you've been to Monkey Do in the past. We found a customer profile with this number. For verification, please enter your last name.** On success: **That name matches our records. Please go ahead with your booking.** Associate only after verification. On failure: **The last name you entered doesn't match the name on record for this number. We would love to get your booking done for you as soon as possible. Please call or text 848-238-5147 and we'll help you with it.** Stop online booking rather than associating an unverified match.
4. On a previous-number match, show full current phone: **Looks like you've been to Monkey Do in the past. We found a customer record with your number, along with an updated number of [current phone]. Please confirm if this is your phone number.** Yes is sufficient for this branch; do not add an unapproved second last-name check. No: **We would love to get your booking finalized as soon as possible. Please call/text 848-238-5147 for assistance with this booking.** Owner explicitly chose this full-number disclosure.
5. Link internally to the same account and use current contact information without unnecessary repeated entry. Do not expose prior booking history, minor names or other private history in the lookup.
6. All customers see booking success and the destination email with an Update email address option. No emailed verification code was requested for that change.

### Administrative corrections and comments

Booking contact data is read-only with **Edit customer**, avoiding accidental profile changes while editing a booking. Owner/staff may correct phone/email. Phone change asks **do you want to move the old number to the previous number field**. Yes moves it; No replaces current and leaves existing Previous phone unchanged. Displaced older phone preservation in comments is manual, not automatic.

Email change moves current to Previous email; if Previous email is occupied, archive its displaced older value in an automatically dated staff-visible comment. Validate new address, update same customer, audit, resend only affected booking confirmation. No verification-code step. Repeated bounce of corrected address alerts again.

Customer and booking comments: searchable, newest-first, author/date/time/edit history; staff-visible. No dedicated mandatory special-price reason field. Preserve actor/action/amount changes automatically. Never put raw cards, passwords or secrets in comments.

## 8. Waivers and signature evidence

Owner-approved wording and electronic interaction are confirmed; **counsel review is not an owner-required gate**. Report insurance-broker approval accurately without claiming counsel review. The preserved prototype still says draft and does not save signatures; updating its code/UI is deferred to separately authorized development. See [source provenance](waivers/README.md).

- Use complete accessible HTML text, printable/downloadable unsigned PDF, unselected acknowledgments, electronic-record/signature consent, typed full legal name, relationship and names of covered minors, and an explicit signing action. Never infer signature from booking submission or precheck consent.
- Use MONKEYDO LLC consistently. Customer must not re-enter booking confirmation number; link customer/booking/version automatically.
- Each signature preserves exact approved text/version, signer/contact/relationship, covered minors, consent, signature method, signed/valid-until timestamps, booking links, tamper-evident hash and appropriate IP/user-agent audit. A successful frontend interaction alone is not saved evidence.
- One-year validity from signing for matching participants/version. Feb29 expires same local time Feb28 in following non-leap year, New York time.
- A new version requires signing at the **next booking**, even if old signature has not expired. Approved example label **MD-WAIVER-2026-01**. Historical “immediately” wording approved the version direction, not current deployment authorization.
- Ordinary bookings do not collect minor names. For unexpired current-version coverage, ask whether new minors not on the prior waiver attend; obtain signatures for them. Expired message: **Please sign a waiver again. Waivers are valid for one year.**
- Signed files only in a dedicated **private Cloudflare R2 bucket**, never Git/public directories/DO/Spaces/PG. DigitalOcean retains metadata, links/object reference and hash, no duplicate signed file. Random object identifiers, server-side credentials, authorization on every retrieval, short-lived access; owner/staff see waiver status, signing date, expiration date, version, history and signed-file view from customer/booking record without manually searching Cloudflare.
- **Delete signed files two years from signing**, not seven years after expiry. Keep minimal historical fact, signer/covered participants, signing/deletion dates and deletion audit. Historical encrypted backup metadata may expire naturally. This is not permission to include duplicate signed files in PG backups. After disaster recovery, reapply retention/deletion state. No paper-destruction alert.

### Shared links and arrival

Phone/admin bookings can confirm with waiver pending; no verbal waiver. Single/Multiple waiver instruction choice determines email content. Multiple uses unsigned PDF attachment plus one shared electronic link, not a separate download-button flow. Multiple parents independently enter their own signer/contact/minor data; every signature links original booking. Public link shows only appointment date, not customer/payment/other waivers. Link remains usable after each signer and expires **11:59 PM New York time the calendar day after the appointment**; rescheduling updates expiry. Expired message: **this link has expired, since you've already had your appointment.**

Online customers may request link/PDF to forward to other parents. Each completion emails the booking customer's current email with signer and minor names; dashboard updates, no separate staff email. Exact wording in [EMAIL_TEMPLATES.md](EMAIL_TEMPLATES.md).

At arrival one **Sign waiver now** button stays available. Distinguish no prior waiver, expired/superseded waiver, and additional uncovered minors; an old expired record does not keep an alert active when current coverage exists. Prefer electronic signing offered verbally. Paper fallback is an audited **Paper waivers signed** booking checkbox only after all required paper forms are actually signed; no initial upload/minor-name entry or repeated timestamp entry. Club paper coverage is per named participant.

Before completing ordinary arrival, require Yes to **Was a waiver signed for everyone in this booking?** No returns to waiver handling and preserves entered attendance/payment selections. A checkbox must not fabricate an electronic signature. Every participating minor requires coverage.

## 9. Admin experience and permissions

**Today** is login landing; **Dashboard** is separate. Start staging with left-side navigation and review arrangement after owner testing before launch. Provide calendar/list/detail, customers, waivers, payment issues, programs/memberships, owner settings/staff and audit; mobile navigation adapts. Exact sidebar order is a presentation choice.

- Global search includes last name/ID, current/previous phone/email, comments, bookings and electronic waiver signer/minor names. Normalize phone punctuation inside comments too; label where a result matched.
- Customer page is responsive at-a-glance cards, not tabs: customer info, comments, waivers and one expandable Bookings card. Messages/audit may be buttons.
- Show first booking today plus **View N more booking(s) today**; always **Other bookings: N upcoming · N previous**, even with no booking today. View all/Create booking available. Do not repeat waiver information redundantly in summary card when Waivers card covers it; detail still includes it.
- Condensed today rows: **Open booking**, **Start arrival**. Future rows: **Open booking**, **Change timing**.
- Booking status actions: Start arrival / Mark as no show / Cancel booking. Editing actions grouped separately: Edit customer / Edit attendees / Change timing / Change credit card / Add booking comment / owner-only special price.
- Start arrival opens workflow, never instantly marks/charges. Final descriptive controls in [PAYMENTS.md](PAYMENTS.md).
- Pre-arrival display: **Upcoming — waiver complete** or **Upcoming — waiver required**; then Arrived/Cancelled/No show. Underlying ordinary attendance is null/Arrived/No show/Cancelled, no Left/Completed/Not arrived statuses. Comped is payment status, not appointment status. Arrival actor/time belong in audit, not direct `arrivedAt`/`arrivedByUserId` booking fields.
- Payment and message attention states separate from attendance: expected method, due/received/partial/paid/comped, charge pending/failed/authentication required/outcome unknown, correction/refund/duplicate review; latest email status/time and history.
- One owner plus multiple staff; owner creates usernames/passwords, grants individual permissions and resets/disables accounts. No mandatory staff first-login password change, and no viewing existing passwords.

| Capability | Default staff | Owner |
|---|---|---|
| Arrival, actual quantities, ordinary cancellation/no-show with/without fee, paper mark, signed-waiver view/search, rosters | Yes | Yes |
| Contact/comment corrections, secure card replacement, available timing changes | Yes | Yes |
| Unexpected attendee arrival capacity override | Yes | Yes |
| Advance full-session override, configured capacities/slots, standard prices/special price | No | Yes |
| Normal membership sale/renew/add, visit conversion, payment-method change, history, contacted-customer manual retry | Yes | Yes |
| Complimentary/early exception/refund, cohort consolidation, nonpurchase benefit adjustments, membership rules | No | Yes |
| Club enrollment assistance, participant edits, attendance correction, waiver/payment follow-up, authorized explicit charge after contact | Yes | Yes |
| Club/program setup, enrollment price override/refund; party creation/pricing | No | Yes |
| Gift-card sale/redemption, socks | Yes | Yes |
| Broad customer/booking/payment/participant/DOB/waiver/audit exports | Only explicit added permission | Yes |
| Staff management, backup operations/restore, export-history visibility | No | Yes |

Staff see calculated fee changes but cannot enter special prices. Enforce every permission server-side, not merely hidden buttons.

## 10. Export, print, retention, and security

- Export customers, all bookings/by booking-date range, one customer's payment history, all payments/by date range; membership and program exports in companion docs. CSV is the documented export format.
- Customer standard fields: Last Name/current phone/current email. Optional ID, previous phone/email, next booking, waiver status and comments. Booking comments optional/default excluded. Never export tokens, raw cards, passwords or secrets.
- Staff print daily/session schedules with Last Name, phone, attendance/appointment/payment information, without customer/booking comments or redundant waiver column. Club rosters have different participant/age/waiver fields. Owner sees export history; no extra owner password prompt for exports while logged in.
- Business records, customer/contact history, participants/DOB, bookings, memberships, payment metadata, messages and audit do not auto-expire. Signed-file retention is the exception. Owner handles corrections; no public deletion-request flow. Owner may delete an erroneous record only when no payment/legal/audit association or active membership/future booking consequence exists. Archive staff identities, never erase action attribution.
- Owner rejects extra privacy notices/clicks in the booking experience; do not present an assistant-proposed notice as approved or claim a legal exemption from this UX choice.
- Minimum password length **10**; store secure hashes, never display passwords. Emailed reset links; owner email MFA every **30 days**, no staff MFA or authenticator-app requirement. Owner-designated secondary email and offline single-use recovery codes; never commit recovery details/codes.
- After **five failed logins**, progressive delays, account/network rate limits, repeated-attempt owner alert, no permanent automatic lockout. No staff bypass of owner recovery.
- **12-hour inactivity logout**, active use stays signed in; password reset, permission removal or disablement immediately invalidates relevant sessions/access. Usernames unique and never reused.
- HTTPS, input validation, CSRF/session/access protection, rate limiting, signed webhooks, concurrency/idempotency controls, redacted logs and append-only sensitive-action audit. Do not treat tokenization as issuer approval.
- Operational logs **90 days**, security logs **one year**, business audit indefinite. Never log card/CVV/password/secret/signed-document contents. Store secrets only in protected server settings.

## 11. Technical direction and acceptance

Server-rendered mobile-first public/admin application in one maintainable codebase; server authoritative for prices, availability, benefits, waiver/payment state and permissions. Persistent PostgreSQL on DigitalOcean initially, not production JSON. Atomic capacity and membership-benefit reservations; durable jobs for due installments, approved notices, webhook handling/reconciliation, retention and backups. No automatic payment retries or appointment-reminder jobs.

Conceptual entities: customers/contact history/comments; admin identities/permissions/sessions; recurring schedules/occurrences/overrides; pricing/tax/settings versions; bookings/price revisions/capacity reservations; provider methods/consents/payment operations/events/tenders/customer credit; membership cohorts/cycles/place allocations/benefit ledger/renewals; program participants/semesters/enrollments/occurrences/attendance; waiver versions/signatures/coverage/object metadata; message templates/deliveries; audit. These are design responsibilities, not selected ORM/schema implementation. Framework/auth/ORM/job tooling remain implementation choices to propose after development authorization.

WCAG **2.2 AA** target. Test current Chrome/Edge/Firefox/Safari, iPhone/Android sizes, tablets/laptops/desktops; keyboard, labels/screen readers, contrast, focus, resizing and errors. Owner password-protected staging acceptance covers full booking/payment/waiver/customer/membership/program/email/admin/security/backup/mobile workflows. Validate actual functional requests and nonzero meaningful tests, not only formatting or a running process. Full acceptance cases and phased build order: [RECONSTRUCTION.md](RECONSTRUCTION.md).

## Staff portal discovery (owner clarification, November 9, 2026)

The staff/owner entry address is `/staff/` on the same website domain. Customer
pages must not link to staff login, administrative pages, or staff actions,
including when a staff member views a customer page. Staff bookmark the address.
Staff login, account recovery, administrative responses and redirects carry
`X-Robots-Tag: noindex, nofollow`; staff HTML also carries a robots noindex tag.
Any future public sitemap must include only explicitly approved public pages,
never staff/admin/account routes. There is currently no sitemap endpoint.
Do not rely on robots.txt disallow rules to hide login pages: crawlers need to
fetch the noindex instruction. The existing staging-wide noindex policy remains.

This is search-result exclusion, not a private network or a secret URL. Anyone
who knows the address can reach the login screen; active authorized staff
credentials, existing permissions and owner verification control entry. No VPN or
Cloudflare Access gate is selected by this clarification. The frozen hosted V1
snapshot remains unchanged; apply this behavior to the functional application
when it is deployed. Customer testing should eventually enter at the homepage;
this does not replace the current frozen design-review index during review.
