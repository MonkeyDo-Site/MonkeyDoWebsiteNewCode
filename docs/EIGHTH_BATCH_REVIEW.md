# Eighth batch: public booking, wording and confirmation review

The owner authorized development and a concurrent draft PR after review of all 28 comments and 27 screenshots in Eighth batch of comments.docx. Update the same PR for review comments. Provide a clearly labelled GitHub screenshot gallery; merge and prepare the browser ZIP/single deployment block only after the owner's review is complete. Active membership planning/implementation remains on hold.

## Accepted scope

1. About-only Open Play membership sentence; approved membership/party wording; Member capitalization; singular Membership navigation; reservation-only footer; remove the second home-tagline period; rose Save More. Preserve existing homepage layouts and images.
2. Revised schedule introduction and Choose your slot heading; suppress only the redundant Open status for available public sessions and retain other statuses; revised supervised-availability sentence.
3. Mandatory indicators for required Last Name and Email on Your details; Open Play requires at least one adult, without removing baby-only/adult-only visits; prevent mouse-wheel count changes while retaining explicit spinner/keyboard edits; visible required errors; formatted public phones and example 732-555-0147; revised sock guidance with $1.99 per pair.
4. Backup-payment arrival wording; conditional saved-card replacement sentence; consistent MonkeyDo branding; approved cancellation wording ($3 per each $15 or $18.99 admission), retaining all existing calculations and membership exceptions. Preserve prior evidence, consents and frozen emails.
5. Investigate unexpected legacy pending-test screens reported after deployment. Prevent new completed-flow bookings from dropping into legacy confirmation, without rewriting historical bookings or inventing saved waivers/cards.
6. Hide waiver version from customer signing page while retaining stored/staff version evidence. Gray and disable Continue to payment when additional signing is selected; preserve shared-parent coverage behavior.
7. One public Confirm booking button orchestrates secure card saving then explicit booking confirmation, with processing dots/status and prominent errors. No online ordinary admission charge or verification hold. Preserve duplicate/stale/uncertain-outcome protections and separate staff setup behavior.
8. Zelle instructions on the saved Zelle confirmation page; end time in confirmation emails; correct singular/plural participant/sock wording. The subject includes a hyphen followed by session date/time, without year or booking reference. No booking reference in the email body. Do not repeat appointment information in a preheader. Date/time under Your play session gets a subtle highlight.

## Review output

Create labelled desktop and phone screenshots, including Your details and Session Details with 732-555-0147; payment before confirmation, processing, card error and success states; conditional card-reuse copy; waiver choice/signing error; schedule/public marketing corrections; Zelle confirmation and email design. Link the gallery from the PR. Use fictional records and synthetic provider/email adapters locally; hosted provider behavior still needs deployment testing.

## Implemented workflow boundaries

The old screenshots correspond to the legacy pending-test branch. The code allowed an uncompleted browser flow without integrated_v1 to reach that branch even after completion became enabled. Current flows are now upgraded back to required Session Details; stale legacy navigation checkpoints cannot reopen old confirmation. Service-level enforcement rejects a new legacy write when completion is required. A staging site whose completion flag is missing pauses booking instead of accepting new pending-test reservations. Historical completed legacy records remain unchanged. This identifies and closes the code paths; it is not a claim to have inspected the owner's original server session/logs.

Single confirmation preserves separate card/setup consent and final booking validation internally. It saves/chooses the card only after both forms validate, shows processing while unconfirmed and submits booking only after setup succeeds. Duplicate submits during setup are ignored. Unknown card outcomes offer safe status/reload recovery rather than another exchange; the restored saved choice is visible and requires explicit booking confirmation. No admission charge is performed. Policy wording is versioned MD-PAYMENT-2026-04; fresh email snapshots are MD-EMAIL-2026-03. Earlier records and versions are retained.

The gallery uses fictional customer Greenfeld / 732-555-0147 and a synthetic provider frame. The local card/storage adapters cannot collect payments or send emails; message jobs remain queued. Local captures do not prove the real Banquest iframe or merchant configuration. Public website copy changes preserve existing layout/assets; Clubs remain hidden in the review fixture and no active membership features are built.

## Review gallery and verification

[GitHub screenshot gallery](design-review/eighth-review/README.md): 21 numbered screens with full desktop and phone images (42 PNGs), mapped to document comment numbers. The gallery includes the requested 732-555-0147 examples, normal one-click confirmation, invalid card entry, processing, confirmed bookings, conditional saved-card text, waiver errors/disabled continuation, Zelle receipt/email and safe interrupted-response recovery. The mail preview adds a simulated inbox header outside the actual body for reviewing the subject.

The complete updated 654-test PostgreSQL regression suite passes, including the pending-policy regression and shared time-range cases. The 27 focused presentation/email/weekday checks also pass. Checks cover preserved legacy history, stale checkpoint rejection, card/waiver/booking boundaries, email subjects and counts, Zelle instruction reuse, required adults, retained card selection, existing financial/waiver integrations and deployment guards. Ruff/formatting, JavaScript syntax, Django checks and migration drift pass. Browser checks verified normal and saved-card confirmation, duplicate submission suppression, error focus on phone/desktop, numeric wheel behavior, supervised/open counts and interrupted-response recovery without repeating the card exchange. The final review database contains three completed integrated bookings, one card exchange, one signed waiver, three queued emails and zero payment operations/postings. No message job was run.

The recovery test caught the browser rule that requestSubmit inside an active submit event is ignored. Final submission now runs on the next browser task, so an already-saved/recovered card completes normally. A card saved under older policy wording is offered for explicit current-policy acceptance instead of automatically recovering obsolete consent. Existing accepted booking agreements remain intact.

PR #34 stays draft throughout owner review. No merge, hosted deployment, ZIP handoff, credential update or integration activation is performed at this point. This batch introduces no schema migration. Later review comments update this same PR and gallery; final testing-guide/ZIP/command preparation follows approval.


## Responses to the eighth screenshot gallery

Reviewed the complete follow-up Word document and all 12 screenshots before editing. The same draft PR #34 and numbered gallery are updated; version 4 supersedes all version 3 images.

| Follow-up comment | Resolution |
|---|---|
| 1 | The washed-out appearance came from scroll-linked opacity, not GitHub. Content and photos retain full opacity during the existing movement. |
| 2 | Phone membership photos use two columns and two rows. |
| 3 | Lower the contact address with additional space below its divider. |
| 4, 6 | Rose Choose your slot; roomier desktop slot spacing. Phone cards retain their existing padding/gap and move the description down within its reserved area. |
| 5 | Phone progress uses steps 1–3 in the first column and 4–5 in the second; leaf icons align with the first line. |
| 7 | Required markers follow the colon: Last Name: *. |
| 8 | The box was the browser focus outline on the validation message, not an annotation. Keep focus/scroll and remove that container outline; normal keyboard outlines on interactive controls remain. |
| 9 | Give expiry/security fields reserved space through Banquest's documented style keys, leaving the card number flexible and labels unwrapped. The simulated gallery frame reflects the intended proportions; actual provider rendering requires hosted review. |
| 10 | Cream Zelle instruction panel, without warning border. First sentence: Please send payment by Zelle at any time to monkeydoplay@gmail.com. Shared confirmation-email wording matches. |
| 11 | Explain the exceptional uncertain-response example: the card-saving response was interrupted. Check card setup checks the existing attempt or reloads the durable saved-card selection; it does not charge or repeat the exchange. Recovery still requires explicit Confirm booking. Normal successful bookings do not show this message. |
| 12 | Shared live time-range formatting uses 2:30–3:45 PM / 9:00–10:15 AM, while crossing noon retains 11:30 AM–12:45 PM. New emails and live schedule/booking summaries use it. Historical frozen emails and signed evidence are unchanged. |

The refreshed gallery keeps all 21 screen numbers and desktop/phone widths. Its explanations distinguish ordinary confirmation from deliberately simulated connection interruption. Screenshots await complete image decoding so lazily loaded photos are present. Card inputs are simulated in local review; no real card or external provider request is used.
