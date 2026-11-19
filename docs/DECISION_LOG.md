# MonkeyDo decision log

## 2026-11-06 — Staging development authorization and framework approval

The owner explicitly authorized staging website/database development and subsequently confirmed: “OK we can go ahead and use Django. Continue development.” Django was a developer recommendation, not a framework selected in the original requirements. PostgreSQL remains the approved database. Django adds no separate software subscription.

Start with staging only on one DigitalOcean server, subject to price approval before provisioning. Before launch assess shared staging/production capacity; a separate staging server is optional. Retain isolated databases/processes/secrets/provider accounts or endpoints/buckets. No production deployment, DNS changes, live payments, customer booking opening or purchases are authorized by this development instruction.

The original images are now supplied and preserved unchanged. Implementation/verification progress: [BUILD_STATUS.md](BUILD_STATUS.md). Setup/architecture: [DEVELOPMENT.md](DEVELOPMENT.md). The owner requested a comprehensive staging scenario document and a final owner video tutorial after working workflows stabilize.

## 2026-11-05 — Coordinated requirements reconstruction (historical checkpoint)

Owner authorized documentation update and creation of a pull request after complete review of history prompts A–AG and later clarifications. This does not authorize application development, purchases, deployment, DNS changes, live payments or opening customer bookings.

Current authority: [documentation index](README.md), [main requirements](MONKEYDO_REQUIREMENTS.md) and specialized linked documents. Source ranges/limitations and observed Git mutations: [RECONSTRUCTION.md](RECONSTRUCTION.md). This is a reconstruction of intended requirements, not recovery of a completed application.

| Subject | Current decision replacing older checkpoint |
|---|---|
| Domain/hosting | Purchased monkeydoplay.com, www redirect, Cloudflare DNS/proxy/strict HTTPS; DO app+PG; protected staging; ~2vCPU4GB subject cost approval |
| Pages/copy | Home/About/combined Memberships-Clubs-Parties/Book Now/Contact; no Play page; exact revised mothers/professionals and four About areas |
| Customers/admin | Last Name only, six-digit IDs, Family/Day Camp, current/previous contact history, Today+Dashboard separate, card-grid records, permissions/exports |
| Capacity | 35children/50combined, babies excluded, manual2yearclosures, owner exclusive/advance overrides and staff arrival override, explicit full/party labels |
| Payments | Banquest selected; no holds, tokens not issuer approval, optional future-use retention, safe last4 history indefinite, review then explicit arrival charge, no automatic payment retries initially |
| Tax/fee | 3% on pretax card-funded amount; tax on taxable goods+their fee portion, one fee/one tax row, proportional splits. Staging6.6%; production UEZ rate pending; retained-fee tax reversed when admission payment is applied to membership, per later accountant clarification |
| Cancellation | $3per applicable ordinary/member/supervised child, partial fee at arrival, no extraadultfee, owner/staff ordinary waiver; party$50ownerwaivable; no ordinary refund program but owner error corrections/member/club exceptions |
| Memberships | Subscription17.99 and Unlimited39.99 anonymous places, documented benefit/adult allocation, three-month new minimum, selected term, exact billing calendars, grace7actualdate/no gap benefits, paid/unpaid conversion and usable customer credit |
| Programs | Supervised18.99/Subscription14.24, clubs279/1298week/dropoff3–8, participants/waivers/attendancefollowup; party28975minutes10+10extras19.99/5member15%beforetax |
| Gift cards/socks | Physical giftcards no system balance/ID/PIN, staff verified atarrival/max2tenders; sock1.99nontax35online/unlimited inperson, bookingpaymentflow |
| Waivers | Owner wording/e-sign approved, insurance-broker approval reported, NO counsel-required gate; valid1year, re-sign nextbooking/newversion, private R2, delete file2yearsfromsigning with minimal history |
| Email | Resend bookings@ sender/Gmailreplyalerts, mandatory email/no number, no appointment reminders, edited membership/club/party and combined templates, no installment receipts, conditional shared waiver/PDF |
| Security/retention | OwneremailMFA30days, staffnoMFA,10charpasswords,12hridle,5failure delays, immediate sessionrevocation, archiveusernames, indefinite businessaudit/90dayoperational/1yearsecurity, no ownerexportreauth |
| Backups | Separate privateR2, encrypted beforeupload,7nightly+12monthly, monthlyisolatedrestore design, keyoutsideDO/R2, owneronlyrestore, monthlyDownloadnow/twolocalcopies/manualdelete |
| Post-launch | SMS, participantmerge, daycamp/groupinvoices, possible owner-approved retryreview, potential paperscans |

The owner re-confirmed the five-child80.98 versus three-child50.98 pretax membership examples; they are different headcounts under one rule, not competing prices. Counsel approval, current sender/domain, cancellation amounts, clubs/parties/gift rules, reminder removal and approved tax formula must not be reopened as unanswered because old files below used different language.

## Historical archive — not current implementation instructions

**Everything below preserves the original dated checkpoint for provenance. Later owner decisions above and the current subject documents supersede conflicting statements here. In particular, draft/legal-review conditions, seven-year waiver retention, full customer names, general appointment reminders, old temporary-domain/Spaces plans, unselected providers and previous field/workflow descriptions are historical. Their presence does not reinstate them.**


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

Decision: The initial/default booking horizon is one calendar day. A booking date becomes available to customers starting at 12:00 AM America/New_York on the previous calendar day.

Example: For an August 4 booking date, customers can begin booking on August 3 at 12:00 AM America/New_York.

## 2026-08-05 — Admin-configurable booking horizon

Decision: The owner can change the customer-facing booking horizon in the admin dashboard to any whole number from 1 through 10 calendar days.

Decision: The horizon is measured in calendar days using the America/New_York time zone and opens at 12:00 AM on the applicable date.

Decision: Changing the horizon does not alter or cancel existing bookings.

## 2026-08-05 — Extended Sunday booking window

Decision: A Sunday appointment must become available to customers no later than Friday at 12:00 AM America/New_York—the midnight immediately following Thursday night.

Decision: If the general booking-horizon setting makes that Sunday available earlier than Friday at 12:00 AM, the earlier opening applies.

Decision: The owner confirmed that “Thursday night at 12 AM” means the beginning of Friday, not the beginning of Thursday.

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

## 2026-08-05 — DigitalOcean VPS hosting

Decision: The owner wants the website and backend hosted on a VPS using DigitalOcean.

Decision: Future implementation should plan for a DigitalOcean Droplet/VPS deployment rather than Vercel hosting.

Reconciliation note: An earlier planning checkpoint listed Vercel and Neon Postgres as recommendations, not owner-confirmed decisions. The owner's later DigitalOcean VPS and same-VPS PostgreSQL decisions supersede those recommendations while preserving the persistent-PostgreSQL requirement.

Decision: Actual provisioning will wait until scoped DigitalOcean access, final domain/DNS details, SSH access, Droplet size, backup settings, and other deployment inputs are available. The region and initial database placement were subsequently finalized below.

## 2026-08-05 — DigitalOcean account capabilities and billing

Decision: The owner's existing DigitalOcean account can create Droplets, Managed PostgreSQL databases, backups/snapshots, and Spaces storage.

Decision: The account currently has free credit. The owner will activate paid billing when the project needs it.

## 2026-08-05 — DigitalOcean region

Decision: Use a New York DigitalOcean region, subject to availability when infrastructure is provisioned.

## 2026-08-05 — Initial PostgreSQL placement

Decision: Run PostgreSQL on the same VPS as the application initially to reduce cost.

Decision: The owner accepts the additional maintenance and recovery responsibility associated with sharing the application VPS. Off-VPS backups and restore testing are still to be configured before production launch.

## 2026-08-05 — Domain and DNS direction

Decision: The owner does not yet own the production domain and is in the process of purchasing it.

Decision: The external domain provider will manage DNS and point the production domain to DigitalOcean.

Decision: Before the production domain is connected, the deployed site may be tested through the Droplet public IP or a deliberately configured temporary hostname. The project must not assume DigitalOcean automatically supplies a permanent browser-ready URL.

## 2026-08-05 — Transactional email provider and credential safety

Decision: Use Resend as the transactional email provider. The owner has created the Resend account.

Security action required: An API credential was disclosed during planning and must be treated as compromised. It must be revoked and replaced before integration or testing. The disclosed value is intentionally not recorded in this repository.

Decision: The replacement credential must be transferred through a secure secret-management channel and stored only as a server-side environment variable or deployment secret. It must not be committed, documented, logged, exposed to client-side code, or shared in chat.

## 2026-08-05 — Resend credential rotation completed

Decision: The owner confirmed that the API credential disclosed during planning was revoked and that a replacement was created.

Decision: The replacement value was not supplied for repository storage and must remain outside source control and documentation.

## 2026-08-05 — Waiver draft supplied

Decision: The owner supplied an image of the current MonkeyDo liability waiver for planning purposes.

This records receipt only. It does not record legal approval of the waiver wording or approval of an electronic-signature implementation. The final legal text and signing workflow remain open pending qualified New Jersey legal review.

## 2026-08-05 — Waiver validity period and source PDF

Decision: A signed waiver remains in effect for one full year from the timestamp when the customer signs it.

Decision at that point in the discussion: The owner had the original waiver as a PDF, but the conversation interface did not permit attaching it. A later entry below records the owner's GitHub upload and supersedes the earlier repository-availability status.

This validity decision does not resolve how later waiver revisions, participant changes, identity matching, or February 29 expirations affect reuse; those implementation and legal rules remain open.

## 2026-08-05 — Waiver PDF reported in GitHub

Decision: The owner provided a GitHub screenshot showing the waiver PDF at the repository root with the exact filename `MD Waiver (1).pdf` on the `main` branch. The screenshot identifies abbreviated upload commit `f2a8ac3`.

Historical verification status at that checkpoint: The screenshot verified the displayed branch, filename, location, and abbreviated commit identifier. The file was not then present in the local checkout, and no Git remote was configured, so the PDF contents, checksum, and full commit object could not be verified at that time. The later 2026-08-06 decision below supersedes this availability status.

## 2026-08-06 — Draft HTML waiver decisions

Decision: Use `MONKEYDO LLC` consistently as the business name in the draft HTML waiver.

Decision: Display a user-facing label identifying the waiver as a draft that is not approved for production.

Decision: Signing the electronic waiver is part of the booking process. The system links the waiver to the booking and confirmation number internally; the customer must not re-enter a confirmation number.

Decision: Approve the proposed accessible electronic-signature interaction, including complete HTML text, affirmative unselected acknowledgments, typed legal name, signer relationship, and a clear signing action. Legal approval remains a production prerequisite.

Decision: Activating a new waiver version requires every customer to sign that version even if an earlier waiver is still within its one-year validity period.

Decision: A waiver signed on February 29 expires at the same local time on February 28 of the following non-leap year using America/New_York.

Decision: Prefer the electronic waiver at arrival. Paper signing is an allowed fallback, may be represented by an admin completion checkbox only after it was actually signed, and does not require an uploaded scan at initial launch. Verbal acceptance is not sufficient.

Superseded decision: Production signed HTML snapshots or generated PDFs would use encrypted DigitalOcean Spaces storage. The 2026-08-13 Cloudflare R2 decision below replaces this storage arrangement; completed signed-waiver files must not be stored in DigitalOcean Spaces.

Decision: Retain signed waivers and their audit records for seven years after expiration, subject to final approval by qualified New Jersey counsel, particularly for records concerning minors.

Decision: Preserve the original source PDF unchanged under `docs/waivers/source/`, record its checksum, and store later approved source versions as separate files.

Decision: The source PDF is now locally verified and preserved as `docs/waivers/source/MD Waiver (1).pdf` with SHA-256 `f159515b1c1c531bc57fce6a8813aa63f38f25da014459807759495f028ccdb6`.

## 2026-08-06 — Returning customer and waiver lookup

Decision: Start booking by asking whether the person is a new customer. A new customer continues to the normal booking fields. A returning customer enters a name and phone number, and the system uses the uniformly formatted phone number to locate the customer profile.

Decision: Customer phone numbers are unique. One customer may have multiple bookings, but multiple customer profiles cannot share a phone number.

Decision: If the initial returning-customer lookup does not match, ask whether the prior booking used a different phone number. Search that prior number if supplied; if it still does not match, treat the person as a new customer.

Decision: A successful public lookup only says that the customer was identified. It must not display prior bookings, email addresses, minor names, or other prior profile data. The supplied phone number is used internally to associate the new booking with the customer profile.

Decision: Booking does not collect minor names. Consequently, the system cannot infer which current minors a prior waiver covers. When an unexpired current-version waiver exists, ask the customer whether minors not listed on the previous waiver will attend. If yes, require an electronic waiver covering those additional minors.

Decision: If the latest applicable waiver is more than one year old, show: “Please sign a waiver again. Waivers are valid for one year.”

Decision: Minor-level electronic waiver lookup is available only to the authenticated owner/admin. Electronically signed waivers record minor names and can be searched for coverage. Paper waivers store only an audited completion checkbox; minor names from paper waivers are not entered into the system and cannot support minor-level lookup.

## 2026-08-13 — Completed signed-waiver storage and staff access

Decision: Customers complete and electronically sign the waiver as part of the website booking process, and the system automatically links each completed waiver to the correct customer, booking, and waiver version.

Decision: Store completed signed-waiver files only in a private Cloudflare R2 bucket. They must not be stored in DigitalOcean, DigitalOcean Spaces, GitHub, or any publicly accessible location.

Decision: Application code, database records, primary customer profiles, booking information, waiver status, and waiver metadata remain in DigitalOcean. Customer information contained within a signed-waiver file necessarily resides with that file in R2, while the primary customer and booking records remain in DigitalOcean.

Decision: The DigitalOcean database stores the secure R2 object reference, customer and booking relationships, signing date, expiration date, waiver version, current status, and verification hash. It must not contain a duplicate copy of the signed-waiver file.

Decision: An authenticated and authorized administrative user can see waiver status, signing date, expiration date, version, and applicable waiver history from the customer's record and view a signed waiver there without signing in to Cloudflare or manually searching R2.

Decision: Every signed-waiver retrieval requires server-side authentication and authorization and uses short-lived authorized access. The application must not expose permanent public R2 links or R2 credentials.

Decision: Cloudflare R2 credentials are server-side DigitalOcean deployment secrets only. They must never appear in browser code, GitHub, documentation, logs, or public links.

Scope clarification: These decisions apply only to completed, signed customer waivers. They do not place unsigned templates or source waiver documents in R2; doing so requires separate owner approval.

## November 2026 — Second owner-feedback batch approved for development

Sources: only green-highlighted additions in First Batch of edits (1).docx, all twenty items/screenshots in Second Batch of edits.docx, and subsequent explicit owner clarifications. The owner approved development and requested desktop/mobile screenshots of all affected pages and states before deployment. Scope and item-level traceability: OWNER_EDITS_BATCH_2.md. Weekly-default closure hides its dated sessions; individual public dated closure displays Not Available. Today gets Add booking for staff/owner, never Add/Edit session. Current email is unique; historical reuse is allowed with staff warnings/public owner Dashboard notices. Multiple weekly defaults and eligible generated dates can change together; every generation outcome explains why. A separate owner-only one/two-month membership exception leaves public minimums intact. Actual payments, active membership benefits and waiver integration remain deferred. Deployment is not authorized by this development approval.

## Second batch — owner response-document clarifications

The owner approved the initial preview and requested only today's response-document changes in the new screenshot set. They authorized continuing implementation and all four related-page extensions. Keep internal membership IDs (no CustomerID+M scheme), add draft editing with preserved versions, show estimates before booking saves and a popup reminder in place of the extra dropdown. Use four visible booking steps, leaving method selection in Session Details and the breakdown/final action in Payment Details. No separate Review label or premature waiver/provider implementation. Screenshot approval precedes PR/deployment-command preparation and hosted deployment. Detailed scope/evidence: OWNER_EDITS_BATCH_2_RESPONSES.md.

## 2026-11-15 — Final second-batch document answers

The owner approved “This previously saved version is read only”, customer-owned one-time referral collection/editing while preserving booking history, and the customer completion headline “You're all set for your MonkeyDo adventure!” with “Book another play session”. The full nine-screenshot review also requests shared compact session dropdowns, M-prefixed existing membership IDs, staff play-type field order, calendar About guidance/Open-only wording, Payment Details copy and explicit returning/new-customer screenshots. Implement and test, then supply only the newly affected screenshots for review. No PR/deployment preparation until image review approval. See OWNER_EDITS_BATCH_2_FINAL_REVIEW.md; these decisions supersede earlier plain-number/referral-ownership instructions.

## 2026-11-15 — Membership version labels belong in history

Owner clarified that routine membership screens should show only the latest details, with earlier versions accessible in Membership history. Remove version text from the table status, current detail heading and edit form. Keep one row per membership, the M-prefixed existing IDs, current-data resolution and preserved read-only history. The two screenshot fixture rows M1/M2 are distinct memberships, not revisions of one membership. No schema/data changes are needed.

## 2026-11-15 — Keep referral information off booking details

The owner requested removal of the “How did you hear about MonkeyDo?” line from the booking details screen as clutter. Customer-profile display/editing and new-customer collection remain unchanged. Earlier booking answers remain stored; this is a template-only visibility change with no migration or data cleanup. This supersedes the prior final-review screenshot that displayed the legacy answer.

## 2026-11-15 — Align Open-only session cards

Owner requested that the Open-only calendar card retain Open above its description and align its information/button with neighboring available cards. Keep a separate status/description/action layout and reserve common description space; bottom-align booking actions across a row. No booking-availability or data changes.

## 2026-11-15 — Align progress-bar completion text

Owner requested that “You’re all set” in the progress bar line up with the other progress text. Remove its top margin, match step-label font sizes and allow responsive wrapping while retaining the four-step customer-only workflow and existing completion wording. This is a CSS-only presentation change.

## 2026-11-15 — Motzei Shabbos labels and owner-controlled public sessions

Owner requested that the civil weekday previously labelled Saturday appear as Motzei Shabbos on staff/customer screens and current documentation. In answer to the explicit availability question, the owner approved allowing owner-opened public sessions under the usual booking rules. This supersedes the historical 2026-08-05 blanket Saturday hiding decision and the corresponding earlier review notes. Backend-only remains private. Keep actual dates/times/weekday indices, normal closures/capacity/cutoffs, staff permissions and the existing Sunday–Friday defaults; no automatic sunset or evening opening is introduced. Owner explicitly waived new screenshots for this change. Historical screenshots/source evidence remain unchanged. No hosted deployment is authorized by this wording change alone.

## 2026-11-15 — Authorize PR and single-command deployment preparation

Owner requested a PR containing all reviewed work since the last deployment, followed by deployment using one command. This supersedes the earlier image-review-only boundary. Add an explicit Functional-only deployment option restricted to checksum-pinned migrations 0023–0025, preflight/duplicate-email checks, a private local staging checkpoint, separate migration identity, runtime grants and service recovery. The default deployment guard still rejects migrations. No payments, new paid services, public production launch or automatic database restoration is authorized. The owner’s existing SSH access is required for actual Droplet execution; local tests do not establish hosted success. See OWNER_FEEDBACK_BATCH_TWO_RELEASE.md.

## Future deployment download preference — owner confirmed

Keep fully automatic one-command deployment, using `curl.exe` for future release downloads. The owner prefers this to both the slower Windows PowerShell 5.1 downloader and returning to a separate manual browser download. Retain commit pinning, HTTPS verification, checked download exit status and archive checksum checks. This is a recorded future preference, not a change to the PR 26 command currently in progress.

Observed follow-up: the owner's Windows curl failed with `CRYPT_E_NO_REVOCATION_CHECK`; the checked command stopped before deployment. The immediate download fallback is the existing working PowerShell downloader with its progress display disabled for that process. Preserve certificate validation and the single-command workflow; do not assume curl works on this machine without addressing that observed limitation.

The owner then clarified that the urgent goal is a faster handoff using a browser-downloaded ZIP followed by PowerShell unpack/deployment. Provide that option directly rather than another automatic PowerShell download. Preserve the exact merged release and reviewed schema/deployment checks, and handle browser duplicate-name suffixes when selecting the completed ZIP.


## 2026-11-17 — Third batch approved; images before PR/deployment

The owner approved the complete third-batch scope and clarification answers,
selected compact 2×2 homepage areas rather than four across, and authorized
implementation. Clear dates must fit existing controls; Clear all restores the
default year. Custom conflicts identify linked blocking bookings; reopening is
explicit and preserves separate closures. Phone/name or current-email/name must
match before revealing family identity; no automatic phone rewrite. Use the
truthful Your details are ready message, retain final atomic creation, and omit
tax only from the live estimate while preserving final tax-inclusive details.
Generate desktop/phone screenshots in GitHub for owner review, then corrections,
PR and one-command deployment preparation. This does not authorize deploying
before image review or implementing the separate next-phase proposal.


## 2026-11-17 — Email recovery reuses the matched phone; estimate lower

Owner clarified that when phone lookup finds a record but the entered surname
fails, the previously entered phone plus matching current email are sufficient.
Do not ask for the name again. Use You can try finding your customer profile by
entering your email address. Keep two matching details before family disclosure,
with current email/phone identifying the same record and saved phone unchanged.
Move the live estimate down beside the attendee inputs to reduce crowding near
Play type. Updated review screenshots precede PR/deployment as before.


## 2026-11-17 — Release third-batch functionality; defer homepage redesign

Owner approved creating the PR and browser-ZIP/one-PowerShell-block deployment
handoff. Exclude all third-batch homepage design proposals and restore deployed
About/play layout, spacing and images. The smaller full-image About proposal and
shorter play-photo crop are not part of this release. Keep approved functional
staff/customer booking changes and remove homepage images from its active gallery.
Prepare only reviewed 0026 from baseline 0025, private checkpoint, atomic runtime
grants and code/schema compatibility checks; never reverse the database or ignore
new reservation restrictions on recovery. No hosted deployment is claimed.


## Owner response after PR #27 deployment — remaining stages and inherited UX

Owner reported the third batch deployed and accepted completing ordinary and
supervised booking before active memberships and remaining business workflows.
Secure card setup must show both intended Credit card and alternate-tender backup
routes; ordinary payment is still after arrival review. Member-information popup
and benefit-adjusted booking prices wait for active memberships. Future sections
must inherit phase-one filters, improved tables/forms/cards/navigation/history and
shared functionality, not only IDs/matching; document affected pages and tests
with each feature using SHARED_WORKFLOW_STANDARDS.md. Preserve draft editing while
handling actual purchased-membership changes with accurate financial/benefit
adjustments and the approved permission matrix. New reservations test the new
completion workflow; plan Old test booking badges/filter for existing records,
including cancellations, without reclassifying status or inventing charges or
signatures. Nightly encrypted backups/jobs are dependencies, not provided by the
current local deployment checkpoint. Update current status documentation and
preserve historical evidence. This is planning only, with no next-phase code,
provider calls, relabelling of hosted data or new deployment.


## Fourth batch — final clarification and implementation go-ahead

Owner clarified the compact booking layout, Name/Email typo, public-only supervised
zero/locking and supervised-only default, paging on Today/Bookings/Customers/
Membership drafts, and separate identity-conflict branches. Simultaneous entered
name/email can lead to another-profile choice only after that profile's own
name/email verification; reuse an already matching name. Email-first then name
matching email profile but not phone profile instead asks restart using the phone
the customer knows, without showing it. The revised Scenario B screenshot
supersedes its earlier phone-update proposal; no reassignment/merge occurs. Retain
owner Dashboard alerts and correct assistance number 848-238-5147. Referral is
optional; owner reproduced a successful single-tab attempt. Later explicit
go-ahead authorizes the whole batch, screenshots now only for the customer booking
page, and one draft PR updated during review. Other owner acceptance follows
approved deployment. Full trace: OWNER_EDITS_BATCH_4.md. The previously aligned
next-stage plan remains planning, not payment/waiver development authorization.


## Fourth-batch booking-page image revision

Owner replaced the first quantity layout while retaining narrower spacing: move
the green panel left, keep space before outside play cards, show Family/contact,
Choose play type, then Your Group; stack all four quantity inputs left, with
estimate upper right and payment/Continue bottom right. Explicit quantity labels
and separate age help remove ambiguity about entering ages. Keep the same draft
PR and refresh booking-page screenshots only. Matching, calculation, permissions
and the deployment review boundary are unchanged.


## Fourth-batch booking-page second image revision

Owner approved the clearer quantity/age separation and requested three changes:
omit Start again only from Session Details, restore Your Group above Choose play
type, and move outside Open/Supervised information cards farther right. Keep the
740px desktop panel and four left-side quantity fields; increase its desktop gap
to the cards to 120px, with existing narrower-screen stacking. Lookup/recovery
restart actions, matching, pricing and validation remain unchanged. Refresh the
same eight booking-page images in draft PR #28; deployment awaits owner approval.


## Fourth-batch booking-page spacing refinement

Owner requested Continue aligned to the right, more space between Your Group and
play choices and between choices and quantities. Add vertical selector margins
without separating the shared quantities/estimate grid row, so their tops remain
parallel. Preserve narrow fields, separate age guidance and wider outside-card
gap. Update the same draft PR and eight booking-page images before deployment.


## Fifth owner-feedback batch — November 19, 2026

Owner confirmed the complete 15-comment review and all four clarifications,
then explicitly authorized implementation and PR together. The two failed-email
introduction removals remain narrowly scoped; do not remove other introductions
globally. Apply the approved guarded verification/conflict behavior to No/silent
current-phone matches and current matches reached by retry; previous-phone
confirmation remains. Duplicate-email link/copy updates apply to both public
email-collection screens, preserving the chosen session. No review screenshots
are needed; owner will accept changes after deployment. Retain browser ZIP plus
one routine PowerShell command. No next-phase payment/waiver work is authorized.
See OWNER_EDITS_BATCH_5.md for all comments and verification boundaries.


## Accountant answer on retained-fee tax — November 19, 2026

Owner supplied the accountant's answer: “If it’s applied towards membership, it
should be refunded. If it’s not applied, then it should not be reversed.” Applied
to the owner's admission-to-nontaxable-membership scenario, the retained $0.45
processing fee remains nonrefundable, but its $0.03 tax reverses along with the
$0.99 admission tax when the paid admission is applied to membership. Of $16.47
paid, $16.02 is available for the replacement purchase; do not refund and credit
the same money twice. No application/payment behavior was changed by recording
this answer. Production tax rate remains open. Companion payment, membership,
open-decision and remaining-stage documents now reflect this clarification.


## Accountant reports later; financial source facts from the start — November 19, 2026

Owner requested eventual income/tax/refund/net-income reports and allowed report
implementation after go-live, asking whether the underlying configuration must
change now. Review found immutable quote snapshots and audit in the current
application; actual payment/tender/refund records remain planned. Add explicit
source-data acceptance criteria to the next payment phase, before real money:
item/category/tax/fee allocations, actual tenders/outcomes, original/correction
links, distinct service/receipt/refund/settlement dates and safe provider IDs.
Keep tax versus income, customer fees versus processor costs, credits versus
external refunds and receipts versus deposits distinct; preserve retention and
exclude sandbox/estimates. Report screens/accounting layout can follow launch;
no server/key change is required solely for reporting. No financial models,
migrations or reporting UI were built in this review. Full detail lives in
ACCOUNTANT_REPORTING_FOUNDATION.md.


## Actual-money report scope and next-stage readiness — November 19, 2026

Owner clarified that accountant reports need actual dollars paid, asking why
discounts were mentioned. Treat original price/approved discounts as internal
reconciliation/refund-tax detail only; do not count them as income or mandate a
report column, new discount feature or extra staff input. Reporting notes now
state this explicitly. Review identified no additional owner business-rule
decision required before the agreed next development scope. Technical payment
records/failure handling, secure card/waiver setup, callback routing, delivery,
worker/resources, backups and migration/recovery remain in that scope. Secrets
are needed for integration tests later, not before local coding; production tax
rate/live activation remain launch inputs. No application development began.
