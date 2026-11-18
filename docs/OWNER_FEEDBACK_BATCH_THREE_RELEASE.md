# Third-batch release: browser ZIP plus one PowerShell command

This release includes the reviewed staff/customer booking and scheduling changes.
**Homepage design changes are excluded.** The homepage About/play template and
its existing styling match the deployed `34a77c4` baseline. The separate About
page is unchanged too. The earlier homepage proposals remain in Git history for
later discussion; their screenshots are excluded from this release gallery.

## Download, then deploy after merging

The release handoff supplies the exact reviewed 40-character commit and a pinned
GitHub ZIP link. Download the ZIP in your browser and wait until it completes in
Downloads. Do not download a moving `main` archive. A reviewed branch commit can
be deployed after its PR is merged: its exact content is the content reviewed in
the PR, even if GitHub creates a separate merge commit.

Paste this **single block** in ordinary Windows PowerShell, replacing
`APPROVED_COMMIT` with the pinned commit from the release handoff. It makes no
PowerShell web download. It accepts the browser's ` (1)`/` (2)` duplicate suffix,
selecting the newest completed ZIP for that exact commit. It extracts only the
wrapper rather than expanding the large image galleries on your computer, then
installs the matching server helper and uploads/deploys the same archive.

```powershell
powershell -NoProfile -ExecutionPolicy RemoteSigned -Command {
    $ErrorActionPreference = 'Stop'
    $monkeydoCommit = 'APPROVED_COMMIT'
    if ($monkeydoCommit -notmatch '^[a-f0-9]{40}$') { throw 'Use the exact approved release commit.' }
    $monkeydoFiles = @(Get-ChildItem -LiteralPath "$HOME\Downloads" -File | Where-Object { $_.Name -match "^MonkeyDoWebsiteNewCode-$monkeydoCommit( \([0-9]+\))?\.zip$" } | Sort-Object LastWriteTime -Descending)
    if ($monkeydoFiles.Count -eq 0) { throw 'Download the approved ZIP in your browser first and wait for it to finish.' }
    $monkeydoArchive = $monkeydoFiles[0].FullName
    $monkeydoTools = "$HOME\MonkeyDoDeploy"
    New-Item -ItemType Directory -Force -Path $monkeydoTools | Out-Null
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $monkeydoPackage = [IO.Compression.ZipFile]::OpenRead($monkeydoArchive)
    try {
        $monkeydoEntry = $monkeydoPackage.GetEntry("MonkeyDoWebsiteNewCode-$monkeydoCommit/deploy/Update-MonkeyDo.ps1")
        if ($null -eq $monkeydoEntry -or $monkeydoEntry.Length -gt 2MB) { throw 'The ZIP does not contain the expected release wrapper.' }
        [IO.Compression.ZipFileExtensions]::ExtractToFile($monkeydoEntry, "$monkeydoTools\Update-MonkeyDo.ps1", $true)
    } finally { $monkeydoPackage.Dispose() }
    Unblock-File -LiteralPath "$monkeydoTools\Update-MonkeyDo.ps1"
    & "$monkeydoTools\Update-MonkeyDo.ps1" -Target Functional -Install -Archive $monkeydoArchive -Commit $monkeydoCommit
    & "$monkeydoTools\Update-MonkeyDo.ps1" -Target Functional -ApplyReviewedBatchThree -Archive $monkeydoArchive -Commit $monkeydoCommit
}
```

Enter the existing SSH-key passphrase when requested. The passphrase is not
saved. Keep the window open until **Deployment verified**. If an error occurs,
stop and report it; do not bypass host/certificate checks or run manual migrations.
No extra configuration, password, email-provider or DNS steps are planned.

## Reviewed database preparation

Only `-Target Functional -ApplyReviewedBatchThree` authorizes migration
`0026_owner_feedback_batch_three`. The helper checks its exact SHA-256 and requires
the existing reviewed 0025 baseline, expected migration database/identity and
restricted runtime role. Reverse migrations, other pending migrations and unknown
core history are rejected. Routine deployments still refuse pending migrations;
the earlier batch-two flag does not authorize 0026.

After building the candidate while the site continues running, the controller
persists recovery state, stops writes, creates a root-only PostgreSQL custom dump,
verifies the archive catalogue and records its checksum. It then applies 0026 and
the new reservation-block table's limited row/sequence permissions in one atomic
transaction using the separate migration identity. No customer, booking, price
quote or membership details are rewritten. It restarts/verifies the current
release, checks the candidate's migration/preflight, switches code, and checks the
private gate, local socket and public HTTPS. A short service interruption is
expected for the database step and code switch.

Retained checkpoint: `/var/lib/monkeydo-functional-deploy/schema-checkpoints/`.
It is a private local recovery aid, not the future encrypted offsite backup.
Existing releases and Python environments are retained. A retry can safely find
0026 already applied and re-establish the required limited grants.

## Compatible recovery

The controller checks code/schema compatibility with writes paused before every
switch, including rollback and interrupted recovery. Older code can be restored
while no new backend-only dates, custom sessions or active source-specific blocks
exist. Once that state exists, older code would ignore restrictions; the switch
is refused and the current service is restarted without changing its release
pointer. Use a release supporting 0026 for further recovery. A compatible release
is recognized by the pinned migration. No database rollback/restoration or
automatic removal of owner settings occurs. Never restore a checkpoint over
newer bookings without a separately reviewed recovery plan.

## Validation

407 local PostgreSQL tests passed; record both GitHub CI jobs in the PR. Tests cover
actual 0025→0026 PostgreSQL migration, existing-record preservation, runtime grants,
atomic rollback on grant failure, repeat application, backup/migration failure
recovery, persisted interrupted recovery and refusal of incompatible old code.
Windows PowerShell tests exercise this exact browser-download handoff with mocked
SSH/SCP, including duplicate filenames and no PowerShell web download. Hosted
installation and deployment are verified only when the owner runs the handoff.
