# Fourth-batch release — browser ZIP and one PowerShell block

Status: draft PR, awaiting the owner's customer-booking-page image approval.
Do not deploy this branch before approval and merge. The release handoff will
supply the exact reviewed full commit and pinned ZIP link.

Download that ZIP using the browser into Downloads and wait for completion.
The block extracts only the small wrapper locally, installs its matching helper,
then uploads and deploys the same archive. Browser duplicate-name suffixes are
supported. No PowerShell download or certificate bypass is used.

Replace APPROVED_COMMIT with the exact handoff commit:

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
    & "$monkeydoTools\Update-MonkeyDo.ps1" -Target Functional -Archive $monkeydoArchive -Commit $monkeydoCommit
}
```

Enter the existing SSH-key passphrase when requested. Keep the window open until
Deployment verified. No migration is introduced in this batch: the normal
pending-migration guard must pass. Do not use a batch-two/three schema flag or
manually migrate to bypass it. Routine deployment retains the current per-release
Python environment/code and compatibility/recovery checks; it does not restore
or reset database records. Current encrypted offsite backups remain planned
next-stage work, separate from existing private migration checkpoints.

The shared staging URL remains staging.monkeydoplay.com. No extra configuration,
provider, DNS, password or paid-service setup is required for this batch. No
payment, waiver or active-membership integration is being activated.
