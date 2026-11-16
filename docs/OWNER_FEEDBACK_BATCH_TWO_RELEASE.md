# Second owner-feedback batch — PR and deployment handoff

The owner authorized PR creation and deployment preparation for all reviewed updates since deployed PR 25, baseline `9b3803453fc81e3d10241681bfd7c6a9b2683ec1`. The site remains **staging.monkeydoplay.com**, with the existing customer/staff accounts and functional database. No hosted deployment has been performed from this workspace.

## Included work

- Weekly default batch editing and conflict/generation explanations; closed default versus individual-date visibility; Sunday-first ordering and clearer scheduling screens.
- Today/Bookings tables, linked IDs/customer names, phone/email search, compact multi-session filters, clearer field/action placement and consistent history.
- Live itemized booking estimates and the save-time payment-method reminder, with original pricing/history retained.
- Editable test membership drafts, immutable saved history and owner-only short-term exceptions. Lists show current values with #M identifiers; version links belong inside Membership history.
- New/returning customer matching, optional staff email, case-insensitive current-email uniqueness, historical-email notices, shared customer pickers and clearer public messages.
- Customer-owned referral information, collected once for new customers; no referral clutter on booking details. Earlier booking answers remain stored.
- Four-step public progress, revised Payment Details/completion wording, aligned calendar cards/buttons and completion message.
- Motzei Shabbos labels and owner-designated public session availability under the normal booking rules, with actual dates/times and private-session visibility preserved. The owner waived screenshots for this final naming change.

Payments, saved cards, electronic waivers, active membership benefits and booking confirmation delivery remain deferred. These continue to be pending test reservations and inactive membership drafts.

## Reviewed database preparation

This release needs existing migrations **0023–0025**. They add customer email uniqueness/optional email and owner notices, immutable membership draft revisions, and the optional customer referral field; the draft minimum constraint permits the approved owner exceptions. There is no booking/customer merge, data reset, historical referral backfill or destructive table cleanup.

The ordinary deployment command still refuses pending migrations. The explicit `-Target Functional -ApplyReviewedBatchTwo` option additionally verifies the three migration file hashes, isolated database/migration identity, entire pending plan and current-email uniqueness. It refuses unreviewed migrations or duplicate current addresses. It uses the existing separate migration identity, applies only the reviewed suffix and grants the new tables' required runtime access.

The root controller records recovery state before any service pause, makes a private same-server custom-format PostgreSQL checkpoint and verifies its catalogue/digest before schema changes. A normal backup/migration failure restarts/verifies the existing release. A killed process leaves durable recovery state for the next invocation. Completed compatible schema changes remain; code rollback never restores or deletes database data. The checkpoint is not the future encrypted offsite backup system. See [deployment limits](DEPLOYMENT_COMMAND.md).

Existing sessions already marked public on Motzei Shabbos become eligible under the new rule when this release is deployed; normal horizon, closure and capacity gates still apply. The owner controls their times and visibility; no automatic evening opening or new weekly default is added.

## One Windows PowerShell command

After merging the PR, the assistant supplies this entire invocation with `APPROVED_COMMIT` replaced by the exact reviewed 40-character release commit. It downloads that pinned public GitHub archive, refreshes the local/server deployment helper, then prepares the reviewed schema and deploys. It does not follow a moving branch. The review commit's source is included in the merged PR.

Paste the entire block once into ordinary Windows PowerShell. The existing SSH-key passphrase may be requested several times; it is not stored. Any failed download, helper install, preflight, backup or migration stops the remaining operation. No GitHub credential or private application setting is pasted into chat or the command.

```powershell
powershell -NoProfile -ExecutionPolicy RemoteSigned -Command {
    $ErrorActionPreference = 'Stop'
    $monkeydoCommit = 'APPROVED_COMMIT'
    $monkeydoArchive = "$HOME\Downloads\MonkeyDoWebsiteNewCode-$monkeydoCommit.zip"
    $monkeydoTools = "$HOME\MonkeyDoDeploy"
    $monkeydoUnpack = "$monkeydoTools\release-$monkeydoCommit"
    New-Item -ItemType Directory -Force -Path $monkeydoTools | Out-Null
    Invoke-WebRequest -UseBasicParsing -Uri "https://codeload.github.com/MonkeyDo-Site/MonkeyDoWebsiteNewCode/zip/$monkeydoCommit" -OutFile $monkeydoArchive
    Expand-Archive -LiteralPath $monkeydoArchive -DestinationPath $monkeydoUnpack -Force
    Copy-Item -LiteralPath "$monkeydoUnpack\MonkeyDoWebsiteNewCode-$monkeydoCommit\deploy\Update-MonkeyDo.ps1" -Destination "$monkeydoTools\Update-MonkeyDo.ps1" -Force
    Unblock-File -LiteralPath "$monkeydoTools\Update-MonkeyDo.ps1"
    & "$monkeydoTools\Update-MonkeyDo.ps1" -Target Functional -Install -Archive $monkeydoArchive -Commit $monkeydoCommit
    & "$monkeydoTools\Update-MonkeyDo.ps1" -Target Functional -ApplyReviewedBatchTwo -Archive $monkeydoArchive -Commit $monkeydoCommit
}
```

Success ends with **Deployment verified. Previous code and Python environment are retained.** The private checkpoint path is also printed. A stop/error message is not successful deployment; retain the output for diagnosis. The helper never changes DNS, nginx routing, TLS, account passwords or provider configuration.

## Verification before release

Run the full PostgreSQL suite and Windows PowerShell CI. Deployment coverage includes unchanged default migration refusal; explicit Functional-only option; hash/plan/identity/duplicate checks; old-schema migration, repeatability and preservation of customers/bookings/quotes/memberships; runtime grants; backup/migration failure service recovery; durable recovery state; and a real local dump restored into a separate disposable database. A matching PostgreSQL dump client is needed for the latter test. Tests use fictional data and mocked SSH/service commands; the owner's actual command output establishes hosted execution.

After success, check Today/Bookings, one booking edit/estimate/reminder, membership current values/history, weekly generation conflict messages, returning/new customer booking and owner-configured Motzei Shabbos visibility. Keep all testing within the pending-reservation/inactive-membership scope.

Local release verification: **376 PostgreSQL tests passed**; the exact PowerShell example was parsed and exercised with a local download fixture and mocked SSH/SCP. The private checkpoint was restored into a fresh disposable database, and the 0022 → 0025 upgrade/retry preserved existing customer, booking, quote, membership and cycle records. Ruff lint/format, Django checks, migration drift and static collection passed. The reviewed source archive is approximately 181 MiB compressed / 204 MiB expanded, within the existing extraction limits. Actual Droplet execution remains pending.
