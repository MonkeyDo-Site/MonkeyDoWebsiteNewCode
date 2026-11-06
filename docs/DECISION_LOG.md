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
| Tax/fee | 3% on pretax card-funded amount; tax on taxable goods+their fee portion, one fee/one tax row, proportional splits. Staging6.6%; production UEZ rate and retained-fee tax reversal still pending |
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
