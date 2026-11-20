# Booking-completion release — browser ZIP and one PowerShell block

PR #30 adds the reviewed ordinary/supervised booking stage. Merge only after the
final checks pass and the handoff identifies the exact approved commit. The command
below uses that commit's browser-downloaded ZIP; it does not download the archive
inside PowerShell. Keep existing SSH host verification.

## One-time setup boundary

The protected staging credentials have been entered separately. Banquest sandbox
read-only authentication and temporary R2 object tests passed; the sending domain
is Verified in Resend. These are not end-to-end card, signature, payment or delivery
acceptance. This release preserves disabled integration flags.

After deployment, finish Banquest/Resend callback registration and protected
signing-secret entry, enable the sandbox booking flags and verify provider events
before testing the full customer flow. Those callbacks require the new routes;
old staging code cannot receive them. Never paste private values into chat or Git.

**Backups remain disabled.** The owner has not yet created the recovery key on an
owner-controlled computer. Create two protected key copies, install only the public
certificate, then verify the first encrypted backup and an isolated restore before
enabling the backup schedule. Credential/storage checks are not a recovery point.

The [owner testing guide](BOOKING_COMPLETION_TEST_GUIDE.md),
[Word download](BOOKING_COMPLETION_TEST_GUIDE.docx) and
[technical setup/recovery guide](BOOKING_STAGING_OPERATIONS.md) explain the remaining
activation and acceptance boundary. No production, DNS or live-payment change.

## Download and run

Download the handoff's exact GitHub ZIP in your browser into Downloads and wait
for it to finish. Substitute the supplied full commit for APPROVED_COMMIT below.
Duplicate browser filenames ending in (1), (2), etc. are supported. The block
extracts only the small deployment wrapper, installs the matching helper, uploads
the archive and performs the explicitly reviewed schema upgrade/deployment.

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
    & "$monkeydoTools\Update-MonkeyDo.ps1" -Target Functional -ApplyReviewedBooking -Archive $monkeydoArchive -Commit $monkeydoCommit
}
```

Use the existing SSH-key passphrase when requested. Keep the window open until
Deployment verified. Do not use the older batch-two/three flags for this stage or
run a general migration to bypass its closed plan.

The helper checks the reviewed 0027–0047 migration and six worker-unit hashes,
resources, protected checkpoint, transactional schema/grants, static/runtime checks
and private/HTTPS health. Old records remain unchanged; new database defaults let
the prior release create legacy bookings during the schema-to-code transition.
Once integrated records exist, an older incompatible code release is refused.
No database rollback can reverse a charge, sent email or private-file operation.

Worker/timer units are installed with the release. Conditions keep disabled
features inactive; installation does not prove a successful provider transaction,
retention run or nightly backup. No server restart is requested by this command.
