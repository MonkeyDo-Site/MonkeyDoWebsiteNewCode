# Customer self-booking and isolated functional staging

Current deployed status: owner reports PR #27 deployed on the single protected
staging.monkeydoplay.com site, with public pending-test booking and /staff sign-in.
The functional cutover and owner account-email delivery were owner-confirmed.
The setup checklist below is historical, not an instruction to create another
site/database or repeat the cutover. Card/waiver/booking-email/arrival completion
remains unbuilt; the [next-stage plan](NEXT_PHASE_REVIEW.md) includes both card
payment and alternate-tender backup-card paths and uses new test reservations.
The [shared standards](SHARED_WORKFLOW_STANDARDS.md) govern future UI/functionality.

This checkpoint connects customer self-booking to the existing owner/staff workspace. Reservations remain **Setup pending**, clearly marked as tests. It does not confirm a visit or take payment. The owner selected one shared staging site: design review and booking tests use `staging.monkeydoplay.com`, with protected `/staff` sign-in. Everyone sees the same deployed design. Frozen source files remain unchanged as historical artifacts; they no longer serve the shared staging root.

## Customer and staff workflow

Enable `MONKEYDO_CUSTOMER_TEST_BOOKING=1` only in the functional environment, with `MONKEYDO_DESIGN_ONLY=0`. The default is off. Customers start at the homepage and choose a session from `/book/`. Available sessions respect the existing New York horizon, closures, play types, capacity and booking cutoffs.

The flow collects phone number and returning/new status. A current-phone match requires the approved Last Name check. A previous-phone match shows the current phone and asks the approved Yes/No question. Ambiguous matches stop for staff assistance. The new-customer choice cannot bypass an existing phone match. This is the approved matching workflow, not independent proof of identity; use fictional customer records during testing.

New customers enter the optional “How did you hear about MonkeyDo?” with their name/email. It belongs to the customer profile. Customers then enter attendees, play type, socks and intended payment method, then review a server-calculated itemized quote. They can revise before submitting. The explicit test acknowledgement creates one pending reservation and immutable quote. No customer record or capacity reservation is created merely by reviewing a quote. Duplicate submissions are idempotent; final submission rechecks pricing, contact revision, availability and capacity inside a transaction. Capacity races and failed writes do not leave orphan customer records.

Authorized staff find these records in Bookings and inspect the customer/test source and quote. They can use **Cancel booking** when cancellation is wanted; this is not a required review or approval step. A customer's same-browser receipt reflects a later cancellation. Receipt access is bound to the browser flow, not a public booking ID. Staff routes remain unlinked from public navigation and enforce staff permissions.

There is no checkout payment, stored card, waiver/signature, active membership allocation, arrival workflow or customer confirmation email here. Booking-linked customer email correction/resending remains future work. Pending records reserve capacity until staff cancel them; no automatic expiry/reset job is provided. Test with fictional data. Cancellation is optional and makes the cancelled booking’s spaces available again.

## Controlled account email

`MONKEYDO_EMAIL_TRANSPORT=resend` selects the staging-only transport for existing account MFA/reset mail. It requires a private `RESEND_API_KEY` and explicit comma-separated `MONKEYDO_TEST_EMAIL_RECIPIENTS`. Every To/CC/BCC recipient must be allowlisted; sender is fixed to `bookings@monkeydoplay.com`. Resend sender/domain verification was completed and inbox receipt was owner-confirmed. No booking confirmation is sent.

The transport has a bounded timeout, rejects redirects and does not retry uncertain deliveries. Errors omit message bodies and secrets; existing account alerts report unconfirmed delivery. Provider acceptance is not proof of inbox delivery. Automated transport tests use mocked responses. The original implementation checkpoint made no real call; later host setup included an owner-confirmed Resend inbox check. Booking mail remains unimplemented.

## Historical one-time shared-site setup checklist — completed

The following records the original operator setup, subsequently completed. Do not repeat it for an ordinary release; the installed update helper is the routine deployment path. Keep the existing design release/database intact for recovery. Replace its public routing only after preparing and checking the functional service. There will be one public staging URL, not a second testing hostname. See [SHARED_STAGING_CUTOVER.md](SHARED_STAGING_CUTOVER.md) for the activation/recovery sequence.

1. Prepare a distinct Linux/runtime SQL user `monkeydo-functional`, migration user/SQL owner `monkeydo-functional-migrate`, and database `monkeydo_functional`. Use peer authentication. Revoke public schema CREATE and give the runtime role only required row/sequence access; it must have no schema CREATE, superuser, CREATEDB or CREATEROLE. Set migration-owner default table/sequence privileges for future migrations. Keep migration credentials inaccessible to the application service.
2. Extract the exact approved release under `/srv/monkeydo-functional/releases/`, prepare its virtualenv/static files and initial `/srv/monkeydo-functional/staging/current` link. Apply migrations through **0021** using the separate migration role, after reviewing the migration and backup procedure. Migration 0021 adds customer-test source/referral/fingerprint fields and permits a null quote actor for customer-created quotes. It does not rewrite existing quotes. Do not migrate the design database for this functional setup.
3. Put actual values from `deploy/functional.env.example` in `/etc/monkeydo/functional.env`, owned root:monkeydo-functional, mode 0640. Generate a distinct Django secret. Enter the Resend key privately on the server, never in chat, source control or command history. Allowlist the owner/recovery and intended staff test addresses. Do not copy the placeholder values or the design environment's secret.
4. With this environment loaded, create exactly one active owner interactively (`manage.py createsuperuser`), run `manage.py configure_staff_group`, and set the shared gate with `manage.py set_functional_staging_password` (hidden prompt). The owner can create staff through the existing workspace. Do not copy real customers or staff passwords from another database.
5. Install the separate `deploy/monkeydo-functional.service.example` as `monkeydo-functional.service`. Its runtime user, environment, current link and Unix socket are isolated. Replace the existing staging nginx virtual host using the example, preserving a private copy of the prior configuration and its existing TLS certificate. Do not add a duplicate server_name block. No DNS or new certificate is needed. Preserve all other web/mail/DNS records. The socket must stay private; nginx must overwrite `X-Real-IP`. Never expose the Gunicorn socket through a public TCP listener or trust arbitrary forwarded IP headers.
6. Run `manage.py check --deploy`, `manage.py migrate --check` and `manage.py functional_staging_preflight` as the functional runtime identity with its environment. Preflight checks hostname, secure cookies/proxy, owner/gate/email configuration and actual runtime database privileges; it makes no external call or data mutation. Check service startup, private gate, HTTPS, static assets and unauthorized staff access.
7. Verify real allowlisted owner MFA/reset delivery and recovery behavior privately, then run the acceptance scenarios below. No tester should receive a functional link until the gate, permissions and complete pending-reservation journey pass on the host.
8. Reinstall the updated deployment engine/wrapper from the approved release, selecting `-Target Functional`. Installation requires the functional service/current release to exist already; it does not perform this bootstrap. Thereafter updates, status and rollback can use the existing wrapper with `-Target Functional`. Default commands continue to select Design. See [DEPLOYMENT_COMMAND.md](DEPLOYMENT_COMMAND.md).

The helper checks for pending migrations and **never applies them**. Rollback restores code, Python environment and service override only, not database schema or records. Functional releases/state are separate from design releases/state. No production deployment or paid-service purchase is included.

## Acceptance and verification

Use fake contacts and distinct browser sessions for customers and staff:

- New family: choose Open Play, review/revise attendees/socks, submit, find the same amount in staff Bookings, cancel, refresh customer receipt.
- Returning family: current phone plus Last Name; wrong name stops. Previous phone plus approved current-phone confirmation. Staff contact changes invalidate an already-verified flow.
- Supervised Play: only eligible slots, no accompanying adults, cutoff and capacity enforced.
- Two customers compete for the last space; only one reservation succeeds. Duplicate confirmation creates one record. Price/closure changes between review and submit require a fresh review.
- Another browser cannot retrieve a receipt; public sessions cannot open staff pages. POST without CSRF fails. No card fields or confirmation claims appear.
- Real host only: HTTPS/private gate, owner MFA/reset delivery, staff permission isolation, new account/recovery, proxy IP buckets and code rollback smoke test. These checks remain unperformed on DigitalOcean.

Local evidence: 278 tests passed on PostgreSQL 17, including concurrent final-space/duplicate submissions, transaction rollback, privacy/CSRF and mocked mail/deployment guards. Portable PowerShell wrapper tests passed with SSH/SCP mocked. Chromium completed customer review/revision/save, actual staff sign-in/search/cancellation and updated customer receipt at 1440px and 390px, without overflow or JavaScript errors. These results do not establish actual provider delivery, Windows execution, hosted TLS or real service switching.

Terminology follow-up: the planned action is **Cancel booking**, with status **Cancelled**. The staff message/history and customer receipt now match. Existing stored cancellation values and immutable audit records are preserved; no database migration or change to fee behavior is required. All 33 staff/public booking tests passed after the wording change. The browser evidence above predates this label correction.

## Second owner-feedback batch

Returning unmatched numbers offer a prior-number retry or explicit new-customer continuation. A close spelling match reveals only the phone-selected surname and entered number before Continue; no additional checkbox, no record rename and no unrelated matches. Customer/customir and the owner-approved Zorger variants are accepted. Public email stays required, including existing staff-created profiles missing email; an email collected for an identified profile is persisted atomically with final submission. Current addresses are case-insensitively unique, and race-time email validation returns to the contact/email form. Historical-only matches are allowed and create owner-only Dashboard notices. New-customer email errors remain inline. CSRF remains enforced; a friendly HTTP 403 recovery screen replaces raw framework instructions. The original hosted CSRF incident's exact trigger cannot be established from its screenshot alone; no claim is made that duplicate email caused it.

## Approved review follow-up

A four-step leaf progress indicator maps phone/name/email states to Customer Details, group fields to Session Details, and the existing itemized-review/save screen to Payment Details. There is no extra visible Review step; method selection stays in Session Details. Receipt marks all four complete and explicitly identifies the pending test reservation. Waiver/payment-provider steps remain deferred.

Shared availability determines offered play types, including remaining supervised capacity and the start cutoff. A sole play type is text plus a hidden validated value; forged/unavailable selections are rejected. Supervised instructions are omitted when unavailable. Grip-sock instructions label the quantity field; credit-card choices show the applicable rate. Missing-email copy and public duplicate-email recovery wording match the response document. Staff duplicates use a separate concise error/profile-link treatment.

## Final review wording and referral ownership

Customer Details collects optional referral only for new profiles; returning customers skip it. The final atomic save stores it on Customer, with the customer-created audit, and leaves new booking-level referral blank. Review alone does not persist it. Existing booking answers remain stored and untouched, but booking details does not display them. Staff can edit the profile field with existing customer permissions/revision checks and before/after history. Migration 0025 adds the optional field without a historical-data backfill.

The four-step progress indicator is absent from staff templates. Payment Details omits the repeated name-match success and uses the approved “Change your session details or your payment method” link. Customer completion uses “You're all set for your MonkeyDo adventure!” and “Book another play session”, while retaining explicit pending-test notices. Cancelled receipts retain cancellation wording and do not show the success headline. Staff Setup pending remains unchanged. The calendar preserves unavailable labels, adds the linked About guidance below group instructions, and uses the Open-only wording also used by Session Details.

Available public session cards retain Open as their status, followed by the Open-only or Supervised Play availability description in the same reserved text area. Align Choose this session buttons at the bottom across cards in each row. Preserve unavailable labels and their absence of booking buttons.

Align the progress-bar completion message vertically with the step labels, using the same text size and no extra top margin. Keep the four numbered steps; let the completion message wrap onto its own line on smaller screens without crowding the steps.

## Motzei Shabbos public booking

Owner-designated public sessions on Motzei Shabbos now use the normal availability and pending-test booking path; private sessions remain hidden and blocked from public start. The public calendar, Details, Payment Details and saved-test receipt render the business weekday wording through the app-wide date filter. Actual dates/times remain unchanged. No default weekly session, evening threshold, automatic visibility, payment or waiver functionality is added.


## Approved third owner-feedback batch

The approved third batch adds exact-current-email plus tolerant surname recovery when no phone matches or phone-selected surname matching fails. Reveal the family only after matching both values, then confirm; retain the saved phone and never identify customers from historical-only email. New-customer continuation has the approved go back link. Success! Your details are ready precedes final atomic creation. Session Details has a read-only pretax live estimate and compact shared play information; final Payment Details retains full tax. No card, waiver, benefit or email delivery is enabled by these screens.

Implementation and image-review record: [OWNER_EDITS_BATCH_3.md](OWNER_EDITS_BATCH_3.md).


## Image-review follow-up — consolidated contact choices

The new-customer continuation paragraph now uses the owner's exact expanded
wording, with go back and enter an email address as inline hyperlinks. It replaces
the duplicated phone/email actions beneath that contact form. Email recovery
accepts navigation by GET as well as its existing POST entry; this only changes
the in-progress browser flow and still requires matching email and surname before
family disclosure. Final customer/booking persistence, saved phone and selected
session are unchanged. Remove the obsolete duplicate-email hint that referred to
the removed standalone button; the approved full error wording remains.


## Image-review clarification — lower estimate and no repeated name entry

The owner clarified the failed-name case: the phone number was already found,
so that phone plus matching current email are sufficient. Recovery now asks for
email only, reuses the earlier phone and reveals the family only after both
identify the same profile. A mismatching email cannot switch a phone-selected
customer to a different record. The wording is You can try finding your customer
profile by entering your email address. The surname is never requested again.
For the earlier unmatched-phone branch, only a surname already supplied in the
contact step can serve as the second detail; otherwise email alone cannot reveal
the record. Historical-only email remains excluded, and saved phones are unchanged.
Confirmation rechecks the same details and profile revision. After recovery the
success message says Your details match our records, avoiding a false claim that
the originally mismatched surname was accepted.

The desktop live estimate is vertically centered lower beside the attendee
fields instead of starting next to Play type. Its narrow-screen placement after
the fields is unchanged. Screens 24–27 were refreshed where affected.


## Final estimate presentation clarification

The live estimate is now low beside socks/payment method on desktop and omits
both processing fees and tax from its rows and total, displaying the base item
subtotal. Final Payment Details and saved quotes keep their full fee/tax totals;
payment-choice percentage information remains. The failed-name recovery notice
retains its original first sentence before the revised email-search sentence,
while direct recovery omits an inapplicable failed-name claim. The repeated name
field remains absent.


## Fourth batch — public layout and scoped verification

The narrower public panel aligns left with space before the outside play cards.
Its order is Family/contact links, Choose play type, then Your Group. All four
quantity inputs stack on the left, with the estimate upper right and Payment
method/Continue bottom right. Quantity labels are explicit and age guidance is
separate; this supersedes the initial fourth-batch layout after image review. Always show both play
choices, disabling unavailable ones. Open defaults when possible; supervised-only
uses Supervised. Public Supervised sets/locks adults/babies to zero, reports an
attempted edit with the approved popup and recalculates the estimate. Switching
back restores prior Open values. Staff keep validation rather than locking.
The booking information card alone omits Check the booking page wording.

The approved [branch matrix](OWNER_EDITS_BATCH_4.md) supersedes earlier generic
recovery descriptions only for its named scenarios. Yes/current-phone offers
name/email or both, with appropriate success/retry messages. Name/email entered
together can reach a verified profile-choice exception; name/email verification
of the second profile is required before its phone/Proceed action is available.
Email-first conflicts instead ask for a name and end in restart/help; the other
saved phone is never shown in that branch, including when name matches email
profile but not phone profile. No customer phone/email is changed, reassigned or
merged. Owner-only Dashboard notices persist per flow/profile pair. Unspecified
new-customer/previous-phone/unmatched-phone branches retain existing behavior.

Referral remains optional. Browser forms carry flow/step markers; stale tab/back
submissions show the current step with a useful warning and preserve its data.
Clean single-tab blank-referral tests pass; this protection does not claim that
the original intermittent report was definitively reproduced. Only booking-page
screenshots are requested now. This batch remains pending-test booking, without
cards, signed waivers, actual payments or next-phase integration.
