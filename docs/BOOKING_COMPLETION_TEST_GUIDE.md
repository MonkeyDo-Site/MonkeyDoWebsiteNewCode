# MonkeyDo — booking completion testing guide

Prepared November 19, 2026 · PR #30 · Ordinary and Supervised Play

This describes the features built in this stage and how to review them after
staging deployment. Developer tests run before deployment; your acceptance testing
happens afterward. A passing developer test does not replace your review or prove
that a private provider connection works.

## Start here

Use https://staging.monkeydoplay.com, fictional families, email addresses you
control and the Banquest-provided sandbox cards. Keep a few new bookings for each
scenario so that an earlier payment or cancellation does not affect the next test.
Use the owner login and a separate ordinary staff login for permission checks.

**Deploying the code and activating the integrations are separate one-time steps.**
The release preserves disabled integration flags. Before testing the new workflow,
finish the signed Banquest/Resend callback setup, enable the sandbox booking flags
and check that the worker is running. Until then the existing test workflow remains
available; that does not mean the new workflow is missing from the release.

### Setup evidence and work still pending

| Item | Current evidence / next action |
| --- | --- |
| Banquest server credentials | Saved privately; read-only sandbox API check returned HTTP 200. Browser card entry, actual sandbox collection and provider callbacks still need acceptance. |
| Waiver storage | Separate private staging bucket; temporary upload, read-back and deletion passed. Test an actual signed waiver through the website after activation. |
| Backup storage credentials | Separate private bucket; read/write and read-only download passed, read-only writing was denied, and temporary files were cleaned up. |
| Email | Existing API key retained; monkeydoplay.com is Verified, as reported during setup. New booking delivery and signed status callbacks still need acceptance. |
| Backup encryption | Disabled. The owner must create and retain the recovery key on an owner-controlled computer, keep a second protected copy separately, and install only the public certificate on the server. Then test an encrypted backup and isolated restore. |

The earlier `monkeydowaivers` bucket was left unchanged. The new staging buckets
are `monkeydo-staging-waivers` and `monkeydo-staging-backups`.

## What this stage adds

- Secure saved-card setup for customers selecting Credit Card and a backup card
  for customers selecting another tender. No admission charge or card hold online.
- Saved electronic waivers, current coverage, shared parent signing links, paper
  coverage records and protected staff waiver search/viewing.
- Queued booking confirmations, conditional unsigned PDF attachments, email
  correction/resend and actual delivery/failure histories.
- Staff booking setup, reviewed arrival collection, actual receipt dates, split
  payments, balance-only recovery, cancellations and no-shows.
- Owner special admissions pricing, fully complimentary bookings, linked payment
  correction records and Dashboard follow-up.
- Financial source facts for later accountant reports; encrypted backup/restore
  tooling and the reviewed deployment/database upgrade.

Memberships remain test drafts. Active membership purchases/benefits, conversion
credits, installments, party management, standalone gift-card/sock sales and club
operations remain later stages. Clubs stay hidden publicly. Homepage design is
unchanged.

## 1. Existing records and familiar navigation

1. Open Today, Bookings and a customer profile. Existing bookings retain their IDs,
   dates, quotes, customer links and history. Earlier records show **Old test
   booking**; they are not silently confirmed, charged, signed or emailed.
2. Try the old/new workflow filter. Clear the date range if an older example falls
   outside the selected dates. The badge refers to the workflow, not visit age.
3. Check linked booking IDs/family names, filters, searches, pagination and phone
   layouts. The approved matching/verification and scheduling rules remain.
4. Where a Motzei Shabbos session is public and eligible, check that screens and
   emails use **Motzei Shabbos**. Backend-only sessions remain private.

## 2. Customer booking — Credit Card

1. Choose an available Open Play session and complete the customer lookup/details.
2. On Session Details, check the approved layout, quantities and live estimate.
   The live estimate excludes processing fees and tax. Select Credit Card.
3. Complete the Waiver step. Read the full legal text, enter the legal signer and
   covered minors, and select the three initially unchecked acknowledgments.
   Leaving required signing information blank should retain the form and show errors.
4. On Payment Details, use the provider-controlled sandbox card fields. Accept
   the applicable payment/cancellation terms. Try both booking-only use and the
   separate optional future-use choice on different bookings.
5. Check the final itemized fee/tax total before confirming. The card is the
   intended payment source at arrival; a second backup card is not required.
6. Confirm once, then inspect the saved booking, capacity and Messages history.
   There must be one booking, no admission money received online, and an accurate
   confirmation state. A queued email must not claim inbox delivery.

The progress bar includes Choose Session, Customer Details, Session Details,
Waiver and Payment Details. The final review is inside Payment Details.

## 3. Alternate tenders and Supervised Play

Repeat with Cash, Check, Zelle and Gift Card on separate bookings. A backup card
is required unless the owner explicitly makes the entire booking complimentary.
Saving a backup does not itself add a card fee to an alternate-tender estimate.

For Zelle, enter the sender name/account; the instructions use
monkeydoplay@gmail.com. A physical gift card must be presented and verified at
arrival. This stage does not create an online gift-card balance system.

Repeat a booking with Supervised Play. Public adult/baby counts become zero and
unavailable for editing. Open Play defaults remain as approved. In a
supervised-only session, Open Play is unavailable and Supervised Play starts
selected. Cutoffs, eligible ages, capacity and the selected play price still apply.
Staff editors validate invalid counts rather than automatically locking them.

## 4. Online group — other parents sign later

1. Include minors and select the option requesting a waiver link for other parents.
   You may continue while their signatures are still pending.
2. Complete card setup and final save. The places are reserved immediately and
   remain held while waivers are pending; no automatic waiver-pending expiry is added.
3. Check **Waiver pending** in the booking/list/Dashboard. The confirmation includes
   the shared signing link and original unsigned PDF.
4. Open the shared link in a separate private browser window. Each parent can sign
   independently. Appointment context is visible, but other parents' contacts,
   signatures, customer details and payments must not be exposed.
5. Check the booking's linked signatures and the completion notice to the booking
   customer's current email. Signing does not create a second booking or release
   places. An individual signature does not declare the whole group covered.
6. At arrival, staff must review coverage for everyone before play. Test both
   electronic coverage and actually signed paper waivers.

## 5. Returning customers, saved cards and waivers

Make another booking for a fictional returning family. The approved phone/name/
email verification branches should continue to work, including conflict messages
and owner notices, without exposing an unrelated profile.

Select valid current coverage where available. Expired/earlier-version evidence
remains in history but cannot substitute for the current required coverage.
Additional minors need coverage; different parents can have separate current
waivers.

Try an available saved method, then replacement. A booking-only replacement
preserves the older reusable method if the customer does not choose to replace it
for future use. A booking-only card must not be removed while another outstanding
booking still depends on it. Historical transaction last four remain after removal.

## 6. Staff-created bookings and card replacement

Use **Add booking** from Today or the usual Bookings/customer action. Save the
session, attendee counts, play type and intended tender, then select **Complete
booking setup**.

Complete secure card entry/consent and either select actual current coverage or
leave coverage pending with Single Waiver/Multiple waivers instructions. Multiple
instructions include the unsigned PDF and shared signing link. Confirm the sandbox
booking. No admission payment is collected during setup.

Try **Change booking card** before collection. Confirm the reviewed source is used;
a stale browser tab must not silently overwrite newer setup. Ordinary staff can
add bookings, but session configuration stays on owner Scheduling.

## 7. Arrival — opening and previewing do not collect money

1. Select **Start arrival**. Opening the page must not charge or mark arrival.
2. Change actual attendees and socks. Choose whether a waiver was signed for
   everyone. Selecting No should preserve entries and direct you back to coverage,
   with no final payment or arrival action recorded.
3. Review actual coverage, choose the actual tender, then select **Review price and
   payment**. Check the revised itemized total and intended payment action.
4. Changing inputs afterward requires a fresh review. Returning to the booking
   without the final confirmation must not collect payment.
5. Confirm the explicitly labelled charge or manual-receipt action once. Check
   both attendance and payment status; these are separate facts.

Ordinary pricing: absent children's admission is removed and the applicable $3
partial-cancellation fee is itemized. An absent extra adult loses its $5 charge
without an adult cancellation fee. Owner-priced bookings use the exception below.
Staff can explicitly allow unexpected arrival attendees over capacity; advance
capacity overrides remain owner-only.

## 8. Actual payment and fee/tax checks

| Test | Expected result |
| --- | --- |
| Card | Only the explicitly confirmed arrival amount is submitted. Check the final provider outcome and the booking/payment history. |
| Cash / Check | Record actual money received. No card-processing fee on those funds. |
| Zelle | Verify receipt in the business bank account; a screenshot alone is insufficient. Record the sender and actual bank receipt date, including an earlier date when applicable. |
| Gift Card | Explicitly verify the presented physical card. Redemption is distinguishable from new bank cash; no invented online balance. |
| Alternate tender not received | Explicitly choose the card fallback; review its applicable fee/tax total before confirming. |
| Split payment | Enter the actual inclusive cash/check/Zelle/gift-card amounts received; review the remaining card amount. Fee applies only to the card-funded portion. |

For the configured staging example of one $15 admission and 6.6% tax, Cash is
$15.99. Card is $15 + $0.45 processing + $0.99 admission tax + $0.03 fee tax =
$16.47. This is an example using the current test policy, not approval of a
production tax rate. Socks remain separately itemized. Compare the final reviewed
policy rather than assuming later settings changes rewrite earlier bookings.

Payment details distinguish base, processing fee, item tax, fee tax, actual receipt
or provider time, and recorded time. No successful receipt should exist for an
estimate, a saved card or an uncertain/declined operation.

## 9. Declines, uncertain outcomes and a remaining balance

Use the Banquest-provided processor-specific test instructions; establish the
actual sandbox processor before selecting decline/timeout test amounts.

- A decline must not appear as Paid. Check the booking, Payments and Dashboard.
- A timeout/uncertain outcome is not a decline. The owner uses **Check provider
  result** to reconcile; the system must not automatically send another charge.
- Record the next follow-up step without falsely marking the balance paid.
- With a received cash portion and a failed card remainder, the cash stays
  received. **Review remaining payment** shows only the unpaid balance.
- After resolving uncertainty, explicitly collect only that remaining amount.
  Switching the unpaid remainder to non-card removes uncharged card fees while
  retaining any fees already received in history.
- Repeated clicks/reloads must not create duplicate financial postings. Controlled
  timeout/concurrency/recovery exercises also have developer test coverage.

## 10. Owner special pricing and complimentary visits

For an unpaid integrated booking, open **Owner pricing / complimentary booking**.

For a special price, enter an admissions total. Socks, tax and applicable card
fees remain separate. Then change attendee counts in Edit booking or Start arrival:

- The agreed admissions total stays unless the owner chooses to adjust it.
- The owner sees a prompt and optional adjustment field; reviewing alone does not save.
- No automatic partial-cancellation fee is added for these count changes.
- Staff retain the special price and cannot adjust it; their saved count changes
  create an owner Dashboard notice. Consult the owner before final collection if
  a price adjustment is wanted.
- History preserves the earlier quote and owner adjustment.

A fully complimentary booking is a separate owner choice: all charges and
cancellation fees become $0, no card is required, and waiver coverage still applies.
Complete the revised setup where requested. Ordinary staff cannot grant special
prices or complimentary status.

## 11. Cancellation and no-show

Use separate unpaid bookings to try Cancel booking and Mark as no show. Review
and explicitly choose charge/no-charge; opening the page or selecting Cancel/back
does not charge. Ordinary applicable fees are $3 per child admission, with the
approved minimum-admission rules and no extra-adult fee. Fully owner-comped
bookings have no fee. Previously pending partial fees must not be stacked twice.

Changing counts on a special-price booking has no automatic fee; cancelling the
whole booking/no-show remains its separate explicit charge/no-charge action.

When an owner reopens affected sessions, only blocks belonging to that
booking/custom session are removed. Independent closures remain. Staff cannot
change owner-only session configuration.

## 12. Waiver, payment and message pages

Open the new Waivers, Payments and Messages pages and the corresponding customer/
booking cards. Check linked IDs, family links, useful searches, combined filters,
date ranges, pagination and phone layouts. Ordinary staff see permitted records;
owner-only financial correction, recovery and backup actions remain protected.

On Waivers, check signer/minor coverage, version, signing/expiry dates, history
and permission-protected evidence. A paper record is an audited staff assertion,
not an electronic signature. Signed evidence cannot be overwritten by an edit.
Two-year retention/deletion is covered by technical tests and still needs its
hosted timer/operational acceptance.

## 13. Confirmation delivery, correction and resend

Check the controlled recipient's inbox and Messages history. Staging messages
have TEST identification and staging links; their family, appointment, prices,
actual payment state, arrival instructions and applicable waiver attachment/link
must be accurate. Sent means provider acceptance; Delivered is a separate event.

On the completion page, use the email-correction link. It affects the current
completed booking/customer context, preserves contact history and uniqueness,
and must not send a confirmation for every older booking. A group correction
retains the shared-waiver instructions and unsigned PDF.

For staff correction, update the customer and explicitly resend only the affected
booking from its message detail page. Unknown earlier sending is flagged for
review instead of an automatic duplicate. Test delivery/bounce reporting after
signed callbacks are connected; failures appear in history/Dashboard. Owner
alerts remain private to the owner. No appointment reminders or installment
receipt emails are introduced.

## 14. Owner payment corrections and future reports

This stage does not add an ordinary customer refund program. For a genuine
sandbox correction, the owner completes the approved action in Banquest, then
uses **Record an already completed refund or void** and verifies/imports it
against the original payment. This action does not issue another refund.

Check original links, partial/full component limits, actual date/status and
preserved history. Staff may view permitted payment history but cannot use owner
correction powers. A refund must not fabricate a new amount due automatically.
Settlement refresh records observations without posting the receipt twice.

Financial source facts now support later accountant reports. The report screens,
active memberships and admission-to-membership conversions are not in this stage.
The accountant's retained-fee tax decision is preserved for that later conversion.

## 15. Backups — complete after owner recovery-key setup

Storage tests alone are not a recoverable backup. Keep this section pending until
the owner's protected key copies and server public certificate are ready.

After activation, verify a nightly encrypted archive and read-back integrity,
owner-only download/integrity files, failure alerts, seven nightly/twelve distinct
monthly retention points, and the desktop-copy reminder. Download on the owner's
computer and keep the two newest desktop copies; the website cannot choose another
computer's download folder or delete its files.

Run the isolated restore verifier on the protected recovery workstation, check
its result, then record the completed restore check in Backups. Recording a check
alone does not perform a restore. An unattended monthly restore runner is not
configured. A private recovery key must not be placed on DigitalOcean or R2.
Actual hosted backup/restore acceptance is still pending.

## Sending comments

Your Word documents with screenshots and clear instructions remain suitable.
For each issue, include the page, booking/customer reference if useful, choices
entered, expected result and what happened. Distinguish a design preference from
a blocked booking/payment. Do not include raw card fields, credentials, private
recovery keys or another parent's signed waiver in feedback.

Record each scenario as Pass, Needs change, or Blocked by setup. If a scenario
needs a special provider response or dated fixture, note that instead of treating
an unperformed test as passed.
