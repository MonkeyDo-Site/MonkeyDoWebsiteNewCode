# Third batch of comments — review and proposed scope

Reviewed November 17, 2026 (owner's New York time).

**Historical review followed by approved clarifications.** The owner answered
all six questions, selected a compact 2×2 homepage arrangement and authorized
development plus screenshot review. The third batch is now implemented locally;
see [implementation and image-review record](OWNER_EDITS_BATCH_3.md). Staging is
unchanged. The owner subsequently authorized PR/deployment preparation excluding
all homepage design changes; see the final release note below. The next-phase proposal
remains separate and pending.

## Sources and coverage

Read the entire **THird batch of comments.docx**: all 20 numbered comments,
the two final homepage design requests, and all 26 embedded screenshots. Read
the screenshots in context with their paragraphs. Checked the relevant current
forms, matching functions, filters, generation coverage calculation, scheduling
overlap rules, public booking save flow, pricing and shared templates. Compared
with the prior owner-feedback records and approved requirements.

The private document and extracted screenshots are not included in this review
file or proposed for publication. Existing screenshot galleries and original
photos are not changed.

## Item-by-item interpretation

| Comment | Interpretation and proposed work | Related scope |
| --- | --- | --- |
| 1 | Show **Closed for reservation** with a checked checkbox meaning closed, rather than the inverse Open checkbox. Apply consistently to weekly-default creation, editing and bulk editing; reconcile related closure wording without changing the approved visibility distinctions. | Weekly defaults currently store an active/open flag, so changing only the label would reverse the meaning incorrectly. Map the UI deliberately and preserve existing records' actual states. |
| 2 | Improve typo suggestions for names such as Braun/Brawn, including a surname within a longer saved name such as Braun Customer. | Same underlying issue as 14; extend the shared staff matching used by Customers, Today/Bookings and booking/membership customer pickers. Exact/direct matches stay first; possible matches are labelled. |
| 3 | Remove the redundant visible Bookings caption above the filters/table. Retain an accessible table name without consuming that visible row. | Shared tables should not repeat the page heading unnecessarily; preserve useful captions in other contexts where no heading identifies the table. |
| 4 | Bookings defaults to today through the same calendar date next year. Both date fields can be cleared for all-history searches; a single bound can mean from that date onward or through that date. Changing valid dates refreshes results and the session choices. Closing the session dropdown after selection applies its filter without Apply. | This explicitly supersedes the old required-date/default-today-only Bookings rule. Today stays fixed to today. Preserve other filters, selected times that remain applicable and pagination; reset the page when filtering. Clarify Clear all versus Clear dates below. |
| 5 | Add an owner-controlled **Backend only** flag for an entire date. It hides all sessions on that date, including sessions generated later, while allowing normal authorized backend booking unless another closure prevents it. | This is a visibility override, separate from closing a date. Turning it off restores each session's own visibility, not public visibility for every session. Existing bookings/history remain. |
| 6 | Staff Create booking chooses a date with a calendar picker, then a session from that date. Avoid an undifferentiated multi-date session list. | Also apply to Edit booking and Change timing; preserve the current booking/session selection and prefilled dates from Today/Owner Scheduling. Private sessions remain available to authorized staff under normal rules. |
| 7 | Add **School** as a customer-level type alongside Family and Day Camp. Use it on backend customer records and type filters. | Public new customers still default to Family. Keep the existing permissions for selecting/changing customer type; staff can book for an existing School customer. No new school-specific fields, pricing or public question were requested. |
| 8 | Add the owner's **Close this entire session to additional reservations** checkbox near capacity override on a booking form. Save booking and closure together; show resulting closure in Scheduling. | Owner-only shortcut, including appropriate edit use; it is not a new staff scheduling permission. Closure must not occur if the booking save fails. Existing other bookings remain and must be clearly disclosed; closing a session does not remove them or retrospectively make it exclusive. Reopening behavior needs agreement. |
| 9 | Owner Scheduling can add a custom one-time session, such as 10 AM–2 PM, which blocks overlapping standard sessions for that date. | Use an explicit custom/blocking option and preview the affected intervals. Retain standard session IDs/times/history. Ordinary session creation retains its normal overlap checks. Existing-booking conflicts and later cancellation/reopening need agreement. The custom session keeps explicit public/backend-only and play/capacity settings. |
| 10 | Change the progress-bar completion sentence to the same rose used for active progress leaves, retaining the approved alignment and responsive wrapping. | Public completion only; no extra progress step or staff progress bar. |
| 11 | Selecting a valid date in Individual Date immediately loads that date, without a visible View date button in the normal interactive flow. | Align with the read-only date/filter interactions in 4 and 6. Changing a date must not automatically save date settings or other edits. Retain a usable no-JavaScript navigation fallback. |
| 12 | Replace the ambiguous single generated-through message with a current-schedule coverage summary and dated/time-specific detail. | Explain the current timing coverage, remaining earlier timings, preserved booked/manual exceptions, custom blocks and missing expected dates. Do not silently move bookings or regenerate dates merely by displaying the page. Proposed presentation below. |
| 13 | Move Create customer above the search area, compact its spacing and add an All/Family/Day Camp/School customer-type filter that combines with search. | Membership/waiver filters remain deferred because they were mentioned as possible future work, not requested for this batch. Do not describe saved drafts as active memberships. |
| 14 | Improve typo matching for bnot versus bnos within bnos miriam. | Same shared word/partial-name matching improvement as 2, rather than a second independent search implementation. |
| 15 | Replace ten-digit US phone number wording with **ten-digit phone number** throughout active public/staff forms, model validation and relevant current guidance. | Existing normalization already accepts a ten-digit Canadian number and strips a leading +1. Preserve that behavior and the stored ten-digit format; historical migration evidence need not be rewritten. |
| 16 | Use the requested no-match wording: **You can continue below as a new customer, go back to try another number, or call/text us at 848-238-5147 for assistance.** Make **go back** a functioning link to number entry for the same booking. | Cover both no-match continuation paths without losing the chosen session. |
| 17 | Remove the old no-customer-found notice once contact details have been accepted. Requested replacement says the customer has been created. | Currently the customer is only persisted on final booking submission. Clarify truthful earlier wording versus changing the save point; do not claim a record exists when it does not. |
| 18 | Make public surname confirmation more tolerant of partial names/spellings. Offer email-based recovery where matching fails, requiring matching name and email before displaying the family for confirmation. | A new identification branch, superseding the old phone-only failure/stop rule. Keep it separate from broad staff suggestions. Resolve which failures offer it, current versus historical email and saved-phone handling before building. Update duplicate-email recovery wording/links so they agree. |
| 19 | On public Session Details, shorten input widths to make room for an adjacent live itemized estimate inside the form panel. Update with counts/play type/socks/method. Do not display tax there; label **Total before applicable taxes**. | Reuse authoritative pricing rules and the backend estimate approach; no saving or capacity hold just to calculate an estimate. Recommend including the applicable card-processing fee in that pretax total. Clarify whether final Payment Details still shows tax. |
| 20 | Outside the form panel on the right, stack compact Open Play and Supervised Play information cards with no booking buttons. | Reuse approved information from the shared play cards rather than duplicating different prices/copy. Recommend text-focused versions to keep the booking page usable. Actual available options still follow the chosen session; the cards do not activate membership discounts or unavailable Supervised Play. Stack below the form on phones. |
| Design A | Owner clarification: use a compact 2×2 homepage About arrangement with smaller image heights and tighter spacing, rather than four across. | Scope the layout to Home; retain legible text and responsive two/one-column arrangements as space requires. Keep the standalone About page's approved layout unless separately requested. |
| Design B | Reduce the homepage Open/Supervised Play cards' image height, padding and spacing. | Scope their compact presentation to Home. Preserve copy, approved images and aligned booking buttons; the booking sidebar can reuse the information in its own compact layout. |

## Findings behind the overlapping requests

### Name matching

Read-only checks of the existing matching function returned:

- Brawn versus Braun: match.
- Brawn versus Braun Customer: no match.
- bnot versus bnos: match.
- bnot versus bnos miriam: no match.

The function currently compares the complete normalized strings. The examples
therefore need word/partial-name handling, not just a larger whole-string typo
allowance. Propose a shared matching improvement for staff searches, with public
matching limited to the profile selected by phone or an exact current-email
match. Do not fuzzy-match phone numbers/email addresses, list unrelated public
profiles, automatically rename a customer or merge records.

### Date selection and automatic filtering

Handle 4, 6 and 11 together for consistent behavior. Automatic actions are
read-only searches/navigation: dates and session choices can update immediately,
but customer/session/booking edits still require Save. Keep Enter/search
submission and non-JavaScript fallbacks. Today remains today's workspace;
unrestricted history applies to Bookings.

### Closures, private visibility and custom sessions

Keep these separate:

- **Closed for reservation:** prevents new reservations while preserving
  existing bookings. Individual public sessions remain Not Available under the
  previously approved rule.
- **Backend only:** hides public calendar/booking access but permits normal
  authorized backend booking if otherwise eligible.
- **Custom blocking session:** reserves a time interval and prevents conflicting
  standard-session reservations without deleting or shifting those sessions.

The present overlap checker includes closed sessions, which explains the custom
10–2 creation failure. Simply ignoring every closed session would weaken the
existing protections. Propose a deliberate custom-block relationship and an
atomic save, with the owner's review of affected sessions. Generation must
respect and explain these blocks instead of recreating bookable overlaps.

### Generated schedule presentation

The present generated-through calculation takes the greatest future source date
and checks missing dates; it does not compare that date's actual timing with the
current default. The owner's screenshot can therefore report March 16 while
some later sessions still use an earlier timing.

Propose a compact summary per default:

- Current default timing.
- **Current schedule fully applied through [date]**, stopping at the first
  expected missing/different date rather than assuming the furthest date is
  complete.
- Separate **Sessions exist through [date]** when this differs.
- A **View generated schedule** expansion with date ranges, actual start/end
  times and status: matches current default, earlier timing, preserved booked or
  individual override, blocked by custom session, or missing/not generated.
- Links to review/update the affected dates, plus the existing clear generation
  outcome/reason messages.

For example, sessions can exist through March 16 while the revised timing is
only fully applied through an earlier date. Both facts should be visible.
Earlier timing outside the selected generation range remains unchanged until
the owner explicitly applies an update. Preserve booking history and manual
overrides.

### Public booking layout and saving

Treat 19 and 20 as one responsive layout: group fields plus live estimate within
the main panel; a separate right-hand column for play/pricing information.
Avoid shrinking controls/text excessively to fit three columns on small screens.
Keep the actual final save in Payment Details and the current four public steps.
This batch does not itself add card collection, waivers or payment processing.

The proposed new-customer success wording in 17 intersects the deliberately
atomic save behavior. Entering details currently creates no customer or booking;
both save together at final submission. Earlier creation would leave customer
records from abandoned/failed bookings and requires an explicit decision rather
than an unnoticed copy change.

## Clarifications before implementation

1. **Clearing dates (4):** should Clear all filters restore the default
   today-to-next-year range, with a separate Clear dates action for all-history
   searches? That is the recommendation. Alternatively, Clear all can leave
   both dates empty; the initial page would still use the default year.
2. **Custom-session conflicts (9):** approve refusing to block an overlapping
   session that already has a noncancelled booking, even if that session is
   closed? Recommend showing its time/bookings and requiring individual moves
   or cancellations first; no automatic rescheduling/cancellation.
3. **Reopening (8–9):** when a private/custom booking is cancelled or moved,
   should the owner be offered **Reopen affected sessions** rather than reopening
   automatically? Recommend an explicit choice which removes only blocks caused
   by that operation and preserves independent closures/visibility settings.
   Editing/removing a custom time interval needs the same treatment.
4. **Email recovery (18):** should it be available both when no phone matches and
   when a phone matches but the entered surname does not? Recommend both, using
   an exact current email plus tolerant surname matching, then family
   confirmation. Recommend keeping the saved phone unchanged; staff can correct
   contact details if needed. Historical-only emails would retain their existing
   warning/reuse behavior rather than identifying a possibly different customer.
5. **New-customer success (17):** may the early screen say **Success! Your details
   are ready. Please proceed with your booking.**, preserving customer creation
   at final submission? If the exact requested created wording is essential,
   confirm that the customer should instead be saved before booking completion.
6. **Tax visibility (19):** should tax be omitted only from the new live estimate,
   while final Payment Details and saved/staff quotes still show tax and the
   complete total? Recommend yes; include any applicable card fee in the live
   pretax estimate. No tax calculation or collection rule changes are inferred.

## Requirements and release implications after approval

Reconcile the main requirements, customer-flow/search documentation, booking and
scheduling guides, recurring-generation coverage and staging acceptance cases
with the answers. Mark the previous required-date rule, Family/Day Camp-only
type list and phone-only public failure branch as superseded rather than leaving
contradictory instructions. Extend related behavior across existing pages as
requested, while keeping specifically homepage-only design changes scoped there.

School type, date-level visibility and persistent custom-blocking state are
expected to require a reviewed database migration. Determine the exact schema
after agreement. Preserve existing records, quotes and roles, and prepare the
appropriate reviewed deployment path instead of treating the previous
batch-specific migration option as permission to apply new migrations.

Development, screenshots/verification, PR and deployment follow the owner's next
go-ahead and review process. Do not open a PR, deploy, activate next-phase
payments/memberships, or convert this review into approved requirements yet.


## Approved answers and review sequence

The owner approved separate compact Clear dates and default-restoring Clear all;
refusal with linked bookings for custom conflicts; explicit owner reopening;
email recovery on either missing phone or surname mismatch using current email
plus surname without changing the saved phone; the truthful Your details are
ready message; and tax omission only on the live estimate, with tax retained in
final Payment Details. Checked Closed for reservation means closed. Homepage
areas remain two across/two down on desktop. Desktop/phone JPG review in GitHub
precedes PR and deployment. These answers supersede the unresolved questions
above; no additional answer is required to start this authorized batch.


## Release authorization and homepage deferral

The owner approved PR and one-command deployment preparation, excluding all
homepage design changes. Restore deployed About/play imagery and spacing for
this release. Homepage proposals, including full-image small scaling, are
superseded and deferred; staff/customer booking changes remain approved.
See OWNER_FEEDBACK_BATCH_THREE_RELEASE.md for the reviewed 0026 preparation and
browser-downloaded ZIP handoff. No hosted deployment has occurred at preparation.
