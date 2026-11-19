# MonkeyDo staging acceptance scenarios

This is the living acceptance document requested by the owner. Use artificial families, email addresses you control and Banquest sandbox cards only. This document lists required coverage; listing a case does not mean its workflow is implemented or its test has passed.

## Current stage and inheritance

The owner reports PR #27 deployed. Customer/staff pending-test booking, improved
search/filter/layout, scheduling restrictions and editable membership drafts are
available for owner testing. This does not mean every scenario below passed:
full card/waiver/arrival/payment/booking-email cases remain blocked by their
unfinished integration, and active memberships follow that stage. Historical
local test counts and hosted deployment evidence are in BUILD_STATUS.md.

Apply [SHARED_WORKFLOW_STANDARDS.md](SHARED_WORKFLOW_STANDARDS.md) at each new
module, with the approved sequence in [NEXT_PHASE_REVIEW.md](NEXT_PHASE_REVIEW.md).
Both credit-card payment and alternate-payment-plus-backup-card paths are required.
Use new reservations for integrated-workflow testing; the proposed Old test
booking badge/filter preserves existing test records. No such relabelling has
been applied by this documentation update.

## Recording results

For each ID, record date/build, tester, setup/data, steps actually performed, expected result, actual result, Pass/Fail/Blocked and an issue or evidence reference. Re-test affected cases after corrections. Owner acceptance and automated developer checks are separate evidence.

Example result entry:

| ID | Build/date | Tester | Actual result | Status | Evidence/issue |
| --- | --- | --- | --- | --- | --- |
| BOOK-01 | To complete | To complete | Not yet performed | Not run | — |

Current status is in [BUILD_STATUS.md](BUILD_STATUS.md). The deployed suite covers the implemented pending-booking/customer/scheduling/draft workflows, including concurrency and permissions. It does not establish unfinished provider integration or blanket owner acceptance. Owner scenarios without a recorded result remain **Not run**. Cases needing unfinished features are **Blocked by implementation**, not failures attributed to the owner. The production tax rate and retained-fee-tax decision must remain explicitly pending where relevant.

## Public website and availability

| ID | Tester | Scenario/steps | Expected result |
| --- | --- | --- | --- |
| WEB-01 | Owner | Review all five public pages and navigation on desktop/mobile | Approved copy/logo/four About areas; no separate Play page; warm approved visual direction |
| WEB-02 | Owner | Inspect Home/About/Contact and public source | Exact street address/parking absent; public phone/email/location correct |
| WEB-03 | Owner | Hide Clubs/program, then show again | Public visibility changes without deleting backend history; no public semester dates or “Spaces are limited” |
| WEB-04 | Developer + owner | Keyboard-only navigation, screen-reader landmarks/errors, 200–400% zoom, contrast and reduced viewport | WCAG 2.2 AA checks; usable focus, labels and layout; meaningful image alt text |
| WEB-05 | Developer + owner | Chrome/Edge/Firefox/Safari; iPhone/Android/tablet/desktop | Complete workflows without overflow, clipped controls or inaccessible menus |
| AVAIL-01 | Developer | Exercise horizon 1 through 10 and revert-to-1 confirmation | New York calendar-day opening; existing bookings unchanged |
| AVAIL-02 | Developer | Check Sunday before/at Friday midnight and with longer horizon | Sunday opens no later than Friday 12 AM, or earlier under longer horizon |
| AVAIL-03 | Developer | Run spring/fall DST boundary and server UTC scenarios | Calendar openings/session times remain correct in America/New_York |
| AVAIL-04 | Owner + developer | Fill child limit, combined limit, party slot and entire date | 35 children/50 combined defaults; babies excluded; correct gray/nonclickable full/party/date wording |
| AVAIL-05 | Owner | Close dates, change time/capacity, create public/backend-only one-off session | Private reasons hidden; changes audited; Motzei Shabbos public/backend-only selection honored; explicit modes/capacities respected |
| AVAIL-06 | Developer | Book ordinary play after start/before end and supervised at/after start | Ordinary remains available until end; supervised closes at start; subset stays within overall capacity |

## Customer records, bookings and arrival

| ID | Tester | Scenario/steps | Expected result |
| --- | --- | --- | --- |
| CUST-01 | Owner | New family and Day Camp records | Last Name only; unique never-reused six-digit IDs; public default Family |
| CUST-02 | Developer + owner | Returning and supposedly new customer with current phone; correct/incorrect last name | Approved verification wording and email-only recovery reusing the entered phone after a name mismatch; two matching details before family disclosure; same record linked only after confirmation |
| CUST-03 | Owner | Previous-phone match, Yes/No, unmatched prior phone | Approved current-number disclosure/confirmation branch; no extra last-name gate in that branch |
| CUST-04 | Developer | Concurrent new customer submissions and normalized phone variants | Unique current-phone record; no duplicate accounts or unrelated history disclosure |
| CUST-05 | Owner | Correct phone/email with occupied previous fields | Approved old-value handling, audit and affected-booking confirmation resend only |
| CUST-06 | Owner | Search IDs, comments, normalized phones, email, waiver signer/minor names | Matched field labeled; searchable newest-first comments and histories |
| CUST-07 | Owner | View customer with multiple today/upcoming/previous bookings | Card layout; first today booking plus count; Other bookings counts always visible |
| BOOK-01 | Owner | Complete ordinary booking with approved payment/waiver flow | Availability precedes personal data; itemized authoritative quote and accurate confirmation |
| BOOK-02 | Developer | Invalid/missing counts, adult/consent/email/card setup, tampered price | Browser/server rejection; no confirmed booking or payment on failure |
| BOOK-03 | Developer | Submit concurrent requests for last child/combined space | Only permitted capacity accepted; no oversell, duplicate benefit use or orphan charge |
| BOOK-04 | Owner | Adult-only, babies-only, child-plus-adults and 10+ child group | Approved $15 minimum/$5 extra-adult rules; group message; no online group discount |
| BOOK-05 | Owner + developer | Move booking to another session; race/failure while moving | Old capacity released/new reserved atomically; old/new timing and actor preserved |
| BOOK-06 | Owner | Owner advance capacity override; staff attempt; staff unexpected arrival additions | Permission matrix enforced server-side; owner override automatically audited without extra reason prompt |
| BOOK-07 | Owner | Owner nonexclusive/exclusive group and custom $0 price | Explicit exclusivity; exclusive blocks session; quantities/pricing follow approved exception rules |
| BOOK-08 | Owner | Start arrival, edit attendees/socks, go back during waiver/payment review | No immediate arrival/charge; selections preserved; final reviewed values determine explicit action |
| BOOK-09 | Owner | Partial arrival, absent child, extra adult, cancel/no-show | Correct $3 applicable-child fee/waiver handling and benefit release; no extra-adult cancellation fee |
| BOOK-10 | Developer | Change future settings/prices after accepted booking | Immutable original quote/policy retained; authorized edits create revisions and audit |

## Waivers

| ID | Tester | Scenario/steps | Expected result |
| --- | --- | --- | --- |
| WAIVER-01 | Owner + developer | Read/sign approved version, omit consent/name, attempt double submission | Complete approved HTML/PDF; explicit unselected consent/signing action; durable signature evidence |
| WAIVER-02 | Developer | Inspect saved evidence and object retrieval | Private R2 file only; version/text/hash/contact/consent/time/coverage metadata; authorization on retrieval |
| WAIVER-03 | Owner | Existing current coverage, new minors, expired and superseded versions | Correct coverage questions; next-booking version renewal; no stale alert once covered |
| WAIVER-04 | Developer | One-year expiry including Feb 29 and New York local time | Approved anniversary/Feb 28 adjustment; no UTC date drift |
| WAIVER-05 | Owner + developer | Multiple parents share link; inspect each page | Only appointment date disclosed; separate signatures attach to same booking; no other family/payment/waiver data |
| WAIVER-06 | Developer | Reschedule then use link before/after next-day 11:59 PM NY expiry | Expiry follows appointment; approved expired-link text; previously used link remains available to other signers |
| WAIVER-07 | Owner | Phone booking pending, sign at arrival, paper fallback, answer No to universal coverage gate | No verbal waiver; paper checkbox does not fabricate electronic evidence; No returns to handling and preserves work |
| WAIVER-08 | Developer | Advance clock to two years and recover older metadata backup | Files removed with minimal historical/deletion audit retained; restoration reapplies retention; no signed-file copies in PG/DO |

## Memberships and conversion credit

| ID | Tester | Scenario/steps | Expected result |
| --- | --- | --- | --- |
| MEMBER-01 | Owner | Buy Subscription/Unlimited, multiple anonymous places, monthly/prepaid terms | Correct prices, three-month new minimum, owner-approved terms and independent cohorts |
| MEMBER-02 | Developer + owner | Subscription first two monthly visits then further visits; rollover boundary | Two free per place/month, then $5.99; no rollover; original accepted pricing preserved |
| MEMBER-03 | Developer + owner | Unlimited same-day repeat and next-day visits with multiple memberships | One free child per place/New York calendar day; no named-child requirement |
| MEMBER-04 | Developer | Mixed memberships, adult allocations/four-adult stacking, benefit reservations concurrent | Exact allocation examples in MEMBERSHIPS.md; no double use or silent repricing |
| MEMBER-05 | Owner | Supervised/Chol Hamoed visits with each membership type | Subscription 25% supervised discount/continued holiday benefit; Unlimited exclusions respected |
| MEMBER-06 | Developer | January 29 leap year, Jan 30/31 short months and return to anchor | Approved billing/benefit calendars, including Feb 29 and March 1 cases |
| MEMBER-07 | Owner + developer | Early renewal, grace Dec 6/10/12 after Dec 5 expiry, late Dec 13 | Actual renewal date, no lapse benefits; grace qualifies without new minimum; late renewal normally new minimum |
| MEMBER-08 | Owner | Renew fewer places, change type, renew multiple cohorts, owner early/midterm exception | Correct cohort selection/history/schedules; no silent consolidation or lost usage |
| MEMBER-09 | Developer + owner | Failed installment and owner-assisted resolution | Benefits temporarily inactive; owner/dashboard alert; no automatic retry/customer email/monthly receipt |
| MEMBER-10 | Owner | Complimentary membership, additional memberships, owner cancellation/refund | Correct permissions, independent dates, opt-in complimentary email and one cancellation message |
| CREDIT-01 | Owner + developer | Unpaid visit conversion: two children/two Subscriptions; three children; five children | Pretax $35.98/$50.98/$80.98 respectively; no credit for uncollected admission |
| CREDIT-02 | Owner + developer | Already-paid cash/card admission converted to membership | Reverse eligible admission/tax, retain original fee; new fee only on new card charge; correct real credit |
| CREDIT-03 | Owner + developer | Retained-fee tax on converted card admission | **Blocked pending accountant decision** on original fee tax; no silent default |
| CREDIT-04 | Owner | Spend credit on each allowed purchase; owner adjust/remove; prepaid membership expires with balance | Audited eligible use, no expiry, owner expiration alert; physical gift-card ledger remains separate |
| CREDIT-05 | Developer | Concurrent credit redemption and next-installment credit application | No double spend; unused credit applied to next installment before actual new charge |

## Payments, taxes and communications

| ID | Tester | Scenario/steps | Expected result |
| --- | --- | --- | --- |
| PAY-01 | Developer | Collect/tokenize card, wait beyond short-lived nonce; inspect browser/server/logs | Durable provider payment method; no holds or raw PAN/CVV in application; tokenization not presented as issuer approval |
| PAY-02 | Developer | Confirm actual sandbox processor and supplied amount responses | Fiserv/TSYS-specific documented outcomes; $45.67/$105/$101.31/$101.06/$109.02 handled accurately where applicable |
| PAY-03 | Developer | Double click, request replay, gateway timeout, repeated/out-of-order webhooks | One intended operation; signature verification/deduplication; unknown outcome reconciled before retry |
| PAY-04 | Developer + owner | Decline, invalid account, authentication-required and manual recovery | Correct persistent issue state, contacted-customer resolution; no automatic full-charge retry |
| PAY-05 | Owner + developer | Remove booking-only method after obligations resolved; explicitly saved method; old transaction | Removed method unavailable for new charges; brand/last4/reference/history retained; provider deletion semantics verified |
| PAY-06 | Developer | Run all fee/tax regression examples from PAYMENTS.md | Decimal/cents arithmetic, one fee and one combined tax row; 3% before tax; taxable-fee portion taxed; no gateway double surcharge |
| PAY-07 | Owner + developer | Cash/check/Zelle/gift card/customer credit/card and actual inclusive split amounts | Tax on underlying taxable goods; fee only on card-funded base; approved proportional allocation; cents reconcile |
| PAY-08 | Owner + developer | $75 due, $40 cash received, remaining $35 card fails | $40 stays received/$35 unpaid; no invented return or repeated $75 charge |
| PAY-09 | Developer + owner | Void/refund/correction and owner's amount override | Correct settled-versus-unsettled provider operation and audit; no undocumented automatic fee refund |
| PAY-10 | Developer | Production URL/key guard and staging reset | Sandbox only; no migration of sandbox transactions to live; no production customer data/credentials/buckets |
| TAX-01 | Owner + developer | Install final production UEZ rate; inspect old transactions | **Production-only pending input**; staging 6.6% never silently promoted; original transactions retain rate |
| EMAIL-01 | Owner | Review every approved membership/club/party/booking conditional template | Latest edits, correct plural/date/package/exclusions/payment wording; no prohibited messages |
| EMAIL-02 | Owner + developer | Combined booking/membership purchase with/without extra-minor waiver request | One combined email; paid-now/due-at-arrival distinction, conditional PDF/link sentence and no Book a visit CTA |
| EMAIL-03 | Developer + owner | Delivery failed/bounced/timeout, corrected email, Resend outage, retry | Persistent dashboard status including unknown; safe retry; affected booking resend only; no dependence on email to report its own failure |
| EMAIL-04 | Developer | Staging send to tester-entered address | TEST subject/banner/staging links; no appointment reminders or successful installment receipts |

## Clubs, parties, physical gift cards and socks

| ID | Tester | Scenario/steps | Expected result |
| --- | --- | --- | --- |
| CLUB-01 | Owner | Create Sunday/weekday term, eight occurrences, exclusions and time changes | Correct defaults/prices/sibling discount; independent weekday groups and roll-forward dates |
| CLUB-02 | Owner | Change occurrence time overlapping public slots | Explicit Allowed/Blocked decisions for new/no-longer overlaps before save; past history retained; no automatic schedule email |
| CLUB-03 | Owner | Reuse participant, enroll at age boundary, correct name/DOB | P-number, customer link, enrollment age/history and warning-not-block behavior; audit; no extra participant phone/email |
| CLUB-04 | Owner | Electronic/paper coverage and ambiguous normalized-name matching | Match within customer context only, explicit confirmation when ambiguous, per-child coverage, one family email |
| CLUB-05 | Owner | Leave individual/whole roster with blanks and inspect future roster | Exact relevant warning; Leave attendance blank allowed; marked rows preserved; future sessions do not warn |
| CLUB-06 | Owner | First attendance unpaid, first-session no-show, contact then backup charge | Required follow-up/default three days as applicable; no automatic $3 club fee or charge; no repeated collection each occurrence |
| CLUB-07 | Owner | Change/cancel/complete enrollment, exception price/refund | Approved permissions and statuses; full-term normal obligations, owner exceptions audited |
| PARTY-01 | Owner | Create private 75-minute party, additional guests, membership/custom price | $289 package/10 children+10 adults, $19.99/$5 extras, included socks/goody bags, 15% before tax/fee |
| PARTY-02 | Owner | Arrival final quantities, split payment, phone cancellation/no-show | Reviewed final payment, $50 fee/owner waiver, backup card for unpresented gift card; exact confirmation policy |
| GIFT-01 | Owner | In-person sale of multiple quantities/face values; card-funded sale | Correct face value, no expiry, taxable status and fee; separate sale when accompanying booking |
| GIFT-02 | Owner | Partial/full physical card tender and phone cancellation without card | Presented card manually verified/sticker updated; backup card required; no digital balance/PIN/activation/check page |
| SOCK-01 | Owner | Online quantity 0/35/36, more/fewer than children, in-person larger sale | Online maximum 35, in-person unrestricted, shortage warning not block; original wording and payment flow |
| SOCK-02 | Owner | Reduce/add socks at arrival or after completed charge | $1.99 nontaxable; final pre-charge total revised; later sale separate; party-included pairs not double-charged |

## Administration, security, infrastructure and handoff

| ID | Tester | Scenario/steps | Expected result |
| --- | --- | --- | --- |
| ADMIN-01 | Owner | Today versus Dashboard, responsive sidebar/cards, arrival and future actions | Approved presentation/workflows; actions describe effects; no charge from simply starting arrival |
| ADMIN-02 | Developer + owner | Exercise every owner/staff capability in MONKEYDO_REQUIREMENTS.md via UI and direct requests | Server denies forbidden overrides/refunds/exports/settings/backups; optional export permission honored |
| ADMIN-03 | Owner | Print schedules/rosters and export all documented record types | Required fields, correct defaults/filters and optional columns; no secrets, raw card data or unwanted comments |
| ADMIN-04 | Developer + owner | Correct sensitive records; attempt audit modification; inspect export history | Actor/time/before-after preserved; append-only audit; owner-only export-history visibility |
| SEC-01 | Developer + owner | Ten-character password, reset, owner 30-day email MFA and recovery | Required hashing/link/MFA/secondary-email/offline-code controls; no staff MFA or existing-password visibility |
| SEC-02 | Developer | Five failed logins, repeated attempts from account/network | Progressive delay/rate limits/owner alert, no permanent automatic lockout |
| SEC-03 | Developer | Twelve-hour idle, continued active use, reset/disable/remove permission | Idle expiration and immediate relevant session/access revocation; archived/nonreused usernames |
| SEC-04 | Developer | CSRF/XSS/object authorization, private cache headers, logs/retention, secret exposure checks | No unauthorized actions/data leakage; redacted data and approved retention; no tokens in CSV/logs/tutorial |
| OPS-01 | Developer + owner | Staging shared password change/90-day rotation; independent staff login | Both distinct protections work; test data/environment remain isolated |
| OPS-02 | Developer | Nightly encrypted backup, R2 upload failure, checksum/retention/deletion failures | Verified encrypted archives, seven nightly/twelve monthly, persistent alerts, no premature recovery-point deletion |
| OPS-03 | Developer + owner | Monthly isolated restore and post-recovery waiver retention | Real restore evidence; private key outside DO/R2; no production replacement or normal staging exposure |
| OPS-04 | Owner | Monthly reminder/Download now/two desktop copies, investigation preservation | Dated encrypted downloads; owner manually removes oldest; audited retention hold/release |
| OPS-05 | Developer + owner | Owner-only production restoration preview and approval procedure | Current DB preserved; isolated validation and explicit replacement authorization; staff denied |
| OPS-06 | Developer | Resend unavailable, app down, disk/TLS/service failure | Dashboard when app runs; independently selected monitoring detects whole-app outage; no unapproved subscription |
| HANDOFF-01 | Owner | Follow video tutorial on staging and repeat key daily workflows | Owner can operate without developer assistance; recording contains test data only and matches final UI |
| HANDOFF-02 | Owner + developer | Final acceptance review and production checklist | Open defects/decisions recorded; costs reviewed; separate written production/DNS/live-payment/open-booking approvals |

## Owner training video

Prepare the final walkthrough after the operational UI stabilizes: sign-in/Today, booking/customer search, arrival/payment/waiver handling, membership sales/renewals/conversion, clubs/attendance, parties/gift cards/socks, alerts/corrections, owner settings/exports/backups, and safe staging versus production use. Use artificial records; do not record credentials, test-card numbers or recovery codes. A script or screenshot document is not a completed video. Track the actual video artifact, duration and build version when recorded.

## Current increment: pending test reservations

Use artificial customers and future sessions only. Confirm creating an ordinary/supervised reservation stores the displayed quote and Setup pending status. Test card versus cash quotes, extra adults, babies-only minimum admission, socks, blocked/ended sessions and supervised cutoff. Change attendees and check prior quotes remain visible; change timing and verify capacity moves without repricing. Cancel a test booking and verify its space returns without recording a fee. Try a stale browser tab and repeated submission; neither may silently overwrite or duplicate. Staff cannot use owner pricing/capacity privileges. Owner future-price changes must not rewrite earlier quotes. Membership benefits, confirmed-booking cancellation, arrivals, split collection and provider operations cannot yet be accepted through these screens.

## Owner calendar acceptance

- Create a backend-only one-time session; verify it stays off the public schedule. Select public and check normal horizon/closure/capacity rules remain in force.
- Exercise accompanied-only, supervised-only and mixed sessions; unsupported play types must fail reservation server checks. Test invalid limits, overlap and ambiguous/nonexistent DST times.
- Close a date with a private reason; verify existing bookings/quotes persist and new test reservations and moves are blocked, including owner capacity overrides. Create another session on that closed date and confirm it remains blocked. Reopen the date; individually closed sessions must stay closed.
- Verify private labels/reasons never appear on the public schedule. Mark Chol Hamoed once for the whole date; membership pricing is deferred, not claimed active.
- Attempt stale simultaneous calendar edits, reduce capacity below reservations and change booked session timing. Each must reject safely. Staff cannot use these owner controls even with model permissions.
- Confirm every successful edit is audited and does not send a message or process a payment. Weekly template controls are covered in the following acceptance cases.

## Membership draft calendar acceptance

- Create Subscription and Unlimited drafts for anonymous places, including mixed separate cohorts and nonstandard whole-month durations. Reject a new term shorter than three months. Drafts must never activate benefits or record customer acceptance/payment.
- Check January 29 leap/non-leap cases, January 30/31 and October 31. Compare each planned charge date against the separate cycle start/end and restored original anchor. DST must not shift civil dates.
- Compare monthly/prepaid estimates, card/noncard fees and nontaxable membership treatment. Prepaid should have one whole-term payment estimate and no later installments.
- Change future product prices and fee policy; existing draft/cycle history must remain unchanged. Staff cannot change owner pricing. Repeat a submission and verify no duplicate draft/cycles/audit.
- Confirm customer-filtered draft history, permissions, pagination and desktop/mobile rendering. Actual benefit allocation, renewal sale, admission conversion, customer credit and Banquest collection cannot yet be accepted from these screens.

## Weekly templates and horizon acceptance

- Review the four initialized Sunday–Friday templates; create an evening/backend-only or Motzei Shabbos template. Saving a template must not expose or change dated sessions by itself.
- Generate a selected inclusive date range. Repeat it and verify no duplicate sessions. Update a template, apply with updates off/on, and inspect the results. Unbooked untouched generated sessions may change; manual, booked, program and independent sessions must be preserved.
- Disable a template or remove a weekday and apply updates: obsolete eligible sessions close without cancelling bookings. Reactivate and apply: only eligible generated sessions reopen; date-wide/manual closures stay effective.
- Try active template overlap, stale edits, invalid capacity/weekdays and ambiguous/nonexistent DST times. A failed generation must roll back its changes and audit.
- Change the horizon to 10, verify date openings and Sunday Friday-midnight behavior, then use the default-one-day reset with/without confirmation. Existing bookings and quotes must remain unchanged. Generation is separate from horizon changes.
- Confirm staff cannot access owner template/horizon actions even with model permissions; verify audit history, CSRF, concurrent generation and desktop/mobile screens.

## Customer self-booking checkpoint

Run the detailed scenarios in [CUSTOMER_BOOKING_DEVELOPMENT.md](CUSTOMER_BOOKING_DEVELOPMENT.md) against the isolated functional environment with fictional data. Local automated/browser checks have passed for pending reservation creation, revision, staff visibility/cancellation and receipt isolation. Real host HTTPS/proxy/permissions, Resend inbox delivery/recovery and real service rollback have not yet been run. This is not acceptance of payments, waiver completion or confirmed customer visits.

## Second owner-feedback batch acceptance (owner review pending)

- SCHED-B2-01: edit four weekly slots into a nonoverlapping final arrangement that overlaps intermediate original positions; save and generate together. Eligible dated identities persist; booked/manual sessions retain original timing; cascading conflicts are explained with links.
- SCHED-B2-02: invalid final overlaps, stale submissions and concurrent bookings do not partially update the schedule or expose temporary values. Check the generated-through date and a deliberately missing expected date.
- AVAIL-B2-01: close weekly default => hide linked public sessions; close individual public dated/one-time session => show Not Available; backend-only stays hidden; owner-designated public Motzei Shabbos sessions follow the normal availability rules.
- STAFF-B2-01: combine date range, recurring clock time, contact search, play/status filters and attendee sorting; clear restores today. Today ignores submitted date changes, includes empty sessions and shows capacity totals independent of search. Add booking preselects the session; ordinary staff cannot configure sessions.
- BOOK-B2-01: one form changes timing/play/counts, enforces supervised/capacity/cutoff rules, prompts for expected-payment-method review when the estimate changes, retains original pricing policy and audit differences. Cancel requires confirmation with/without JavaScript.
- CUST-B2-01: test +1 phones and customer/customir, Zorger/Zarger/Zharger/Zorge; no unrelated public surname disclosures. Returning unmatched phone permits alternative lookup before new contact entry.
- EMAIL-B2-01: current duplicate addresses are rejected case-insensitively, including concurrent requests and staff corrections. Multiple empty staff emails are allowed; public known-customer flow collects missing email. Historical-only reuse warns staff, permits public booking and creates an owner-only reviewable notice. A CSRF rejection stays HTTP 403 with recovery guidance.
- MEMBER-B2-01: both products and payment-plan types permit explicitly audited owner one/two-month exceptions; staff cannot forge the exception; normal public minimum stays three. Membership/payment customer cards accurately distinguish drafts/estimates from actual benefits/payments.
- UI-B2-01: desktop/mobile screenshots, keyboard customer picker, row filters, narrow-screen table scroll, inline checkbox labels, compact breadcrumb navigation and readable history. Owner screenshot approval precedes deployment.

## Second-batch follow-up acceptance (new image review pending)

- FILTER-B2R-01: on Today and Bookings, select several sessions and then none; none means all. Combine with contact search and submit using Enter. Check that table headings sit below filters, Add booking is beside the title and Apply/Clear sit below contact search. Bookings must not promise totals below the table.
- BOOK-B2R-01: change counts or expected payment method and see the itemized estimate before saving. The estimate request must not mutate the booking. An amount-changing Save opens the reminder; Review payment method focuses the existing selector, Save changes saves once, and stale/tampered proofs cannot skip review. Verify the no-JavaScript reminder too.
- MEMBER-B2R-01: follow an existing numeric membership ID from the table, edit a draft as owner/staff and retain that ID. Reopen earlier versions and compare original cycles/pricing. Ordinary staff cannot introduce a one/two-month exception; an already approved exception may retain its terms. Test stale edits, repeated submissions and concurrent edits.
- COPY-B2R-01: verify shared picker wording, no blank Before for creation/comment additions, before/after for real edits, policy-specific card-fee labels, full public duplicate-email recovery text and shorter authorized staff profile links.
- PUBLIC-B2R-01: follow the four visible steps through pending-test completion. Open-only sessions have fixed play text and no supervised instructions; mixed sessions show eligible choices. Sock instructions belong to the field. Method selection stays in Session Details; the price breakdown/save screen is Payment Details.

## Final second-batch review acceptance (new image review pending)

- REFERRAL-B2F-01: new-customer Details collects optional referral after silent phone lookup; Session Details and staff booking forms omit it. Review alone saves nothing; final successful submission saves one profile answer, retry remains idempotent, and failure rolls it back. Returning customers keep their original answer even with forged booking input. Staff edit the profile with readable before/after audit; earlier booking answers remain unchanged.
- FILTER-B2F-01: Today/Bookings initial compact summaries wrap within the column. Open options without increasing row height, select multiple times, choose All sessions, apply filters, and dismiss by Escape/outside click. Verify phone table scrolling, no document overflow, and no-JavaScript explicit All sessions handling.
- UI-B2F-01: #M membership labels link to existing records across list/detail/edit/customer cards; historical versions are read-only with the approved sentence. Supervised Play precedes counts in Create/Edit booking. Public progress never appears in staff screens.
- PUBLIC-B2F-01: show saved email only after the existing verification, and new-customer name/email/referral after no-match lookup. Payment Details removes repeated name-match wording and uses the approved edit action. Open-only slots/details and About link use approved wording without relabelling closed/full/not-yet-open sessions. Completion headline/button match approval with truthful test notices; cancelled receipts retain cancellation wording.

## Motzei Shabbos acceptance

- MOTZEI-01: weekly checkbox/list and dated scheduling use Motzei Shabbos; numeric date inputs retain their actual dates. Verify late UTC timestamps use the correct New York weekday without shifting the saved appointment.
- MOTZEI-02: owner-created public one-time and generated weekly sessions appear and accept pending-test bookings under the usual horizon, closure, mode/cutoff and capacity rules. Backend-only sessions stay hidden and public start is refused. Staff still cannot configure sessions.
- MOTZEI-03: customer calendar/details/receipt and staff booking table/detail/edit/cancellation/customer records use the same wording. Other weekday names and ISO/numeric values are unchanged. No automatic evening start or new default schedule is added. The owner waived screenshots for this change.


## Third owner-feedback batch — deployed per owner report, scenario results separately recorded

- B3-SEARCH: Brawn/Braun Customer and bnot/bnos miriam match in staff lists, Today/Bookings and both pickers; exact results first, possible matches marked, unrelated public profiles never listed. Test partial public surname and exact current email + matched phone recovery, failed matches, stale profile and unchanged saved phone; only an unmatched-phone branch may reuse an already-entered surname, never ask it again.
- B3-FILTER: default year, both dates empty, each single bound, Enter, automatic date/session filtering and refreshed choices, Clear dates versus Clear all, fixed Today and preserved nondate filters/pagination.
- B3-DATE: mark a date backend-only, generate another session on it, verify public hide/direct-start refusal and authorized staff booking; removing the override preserves individual private visibility and closures.
- B3-CUSTOM: preview and confirm 10–2 overlapping standard slots; linked active booking conflicts cause no partial write. Repeat with a concurrent booking, stale preview, duplicate start, custom/program conflict, preserved standard IDs/times and explicit reopening that retains manual/date closures.
- B3-CLOSE: owner booking closure saves atomically; staff forged/direct closure fails; invalid booking leaves no block. Ordinary cancellation keeps blocks; explicit owner reopening removes only the relevant source. Test moved bookings and other bookings in a custom session.
- B3-COVERAGE: generate through a later date, change timing and apply to an earlier date; verify separate contiguous-current and furthest-existing dates, actual timing ranges, gaps, preserved bookings/manual overrides and custom blocks.
- B3-SCHOOL: owner creates/edits School, staff can select an existing School for booking, type filter combines with search, public default remains Family; unsupported future membership filters absent.
- B3-PUBLIC: Canadian/+1 error wording, go back retains chosen session, ready notice creates no early customer, live pretax estimate changes counts/play/socks/method without writes and final Payment Details retains tax; sidebar has no booking buttons; completion text rose/aligned.
- B3-DESIGN: third-batch homepage design changes were excluded. Homepage About/play template and its existing CSS match deployed 34a77c4; no compact-area/smaller-play crop is included. The 52 remaining review JPGs cover staff/customer changes with desktop/phone layouts; retain accessible focus and 390px/320px no-overflow checks.


## Next-stage and shared-experience acceptance — planned, not implemented

| ID | Scope | Required result |
| --- | --- | --- |
| NEXT-CARD-01 | New Credit card ordinary/supervised booking, then arrival | Secure provider card setup/consent and saved waiver; no ordinary charge/hold at booking. Accurate final fee/tax estimate and confirmation. Staff review and explicit final charge only; test failures, unknown outcome and duplicate prevention. |
| NEXT-CARD-02 | New cash/check/Zelle/physical-gift-card intended tender, then arrival | Required backup setup and applicable details, no charge/fee merely for storing backup. Staff verify actual tender or explicitly use fallback; fee/tax follow actual card-funded share. Preserve deletion/optional-reuse rules and partial funds after failure. |
| NEXT-OLD-01 | Upgrade existing pending and cancelled test records | Stable Old test booking classification/badge/filter without rewriting IDs/status/quotes/history/capacity; no charges, signatures, confirmation emails or automatic data reset. New integrated tests use new bookings. |
| NEXT-UX-01 | New membership/waiver list, detail, form and customer card | Existing compact responsive tables/cards, linked records/names, customer picker, field sizing/navigation and readable history. Membership latest-only row/#M ID; distinct waiver signer/minor coverage retained. |
| NEXT-UX-02 | Combine staff search/status/type/date filters on future modules | Shared Enter/automatic valid-change/clear/no-JS behavior; meaningful permitted matches. Explicit module-specific date meanings/defaults; do not hide current membership/coverage because its purchase/signing is earlier. |
| NEXT-UX-03 | Current and earlier records across new modules | Creation history has no Before; edits have readable differences/actor/time. Purchased membership adjustments preserve paid/used facts; signed waiver evidence is never edited in place. |
| NEXT-UX-04 | Customer/public/staff privacy and capability checks | Current email uniqueness applies to customers, not all waiver signers; two-piece public lookup and private shared links. No new session controls on Today or implicit export/owner privilege. |
| NEXT-UX-05 | Public versus staff money displays | Public Session Details has low base-item subtotal only; final Payment Details shows fee/tax for intended tender. Staff/membership estimates keep approved fee information; no charge on Save. |
| NEXT-UX-06 | Scheduling, dates, outputs and cross-module regression | Backend-only/closure/custom blocks and capacity remain enforced even with paid membership/waiver; explicit source reopening; New York/Motzei Shabbos in relevant screens/emails/output; no membership popup until membership stage. |
| NEXT-OPS-01 | Provider/file/message/job/backup operations | Verify actual sandbox outcomes, private signed evidence/access/retention, accurate delivery, durable reconciliation/no auto retry and isolated restore. A screenshot or same-server checkpoint is not proof of those integrations. |

The new list columns/filter choices and affected screenshots must be reviewed
before that stage's deployment. Mark cases Blocked by implementation until they
exist; record actual owner/provider outcomes rather than inheriting a Pass from
the pending-test foundation. No full application suite was rerun for this
planning-only documentation change.


## Fourth owner-feedback batch

Local developer regression/browser checks passed; owner booking-page screenshot
review is pending. Other changed pages/scenarios receive owner interactive tests
after approved deployment, per this batch's explicit review instruction.

- B4-LAYOUT: left-aligned narrow panel with wider outside-card separation; Family/contact,
  Your Group and Choose play type order. No Start again action on Session Details;
  lookup/recovery restart actions remain. Four quantity fields stack left, estimate
  upper right and Payment/Continue bottom right, with Continue right-aligned.
  Extra space surrounds the play choices; quantities and estimate move down together. Quantity labels and separate age
  help, phone stacking and 320px no overflow.
  Check only booking card omits Check the booking page; homepage/About unchanged.
- B4-PLAY: both radios visible, unavailable disabled, Open default/supervised-only
  exception; public zero/lock/popup/estimate, restored Open counts; forged values
  rejected and staff remain editable with validation errors.
- B4-LISTS: Customers compact search/type/Search, All types default. All four
  approved tables page at 10/25/50/100, preserve filters/sort and provide numbered
  Previous/Next links. Today matching/session totals stay complete.
- B4-FILTER: checking/unchecking sessions updates Today/Bookings without closing
  the selector or Apply; multi-select and other filters remain usable; errors,
  row-size changes, pagination and no-JavaScript Apply remain correct.
- B4-A: Yes/current-phone exact name/email/both messages; either/both blank or
  incorrect; name-first/email-first retries and later failures; partial name still
  needs confirmation. Unspecified No/current, previous-phone and unmatched-phone
  paths must not acquire the new exception.
- B4-BOTH: supplied name verifies phone profile and supplied email identifies
  another profile. Other phone/Proceed stays hidden until that profile's own
  name/email verification; reuse matching name, confirm possible spelling,
  explicit final profile choice, stale-profile rejection and unchanged contacts.
- B4-EMAIL-FIRST: email identifies another profile, then requested name matches
  phone profile, email profile only, or neither. Correct restart/help wording;
  never show the other saved phone, especially in the email/name-only match.
  Test the specified Yes/No entry paths and ensure forged choice action fails.
- B4-NOTICE: one conflict notice per flow/profile pair, protected links, owner-only
  viewing/review, readable audit, no repeated notice on retries or outbound email.
- B4-C: new-customer referral blank succeeds without early save; stale/double/back
  submissions retain current step/quote and do not show unrelated required-field
  errors or create another booking. A current review form remains submittable.
