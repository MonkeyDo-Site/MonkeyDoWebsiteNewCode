$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$wrapper = Join-Path $root 'deploy/Update-MonkeyDo.ps1'
$tokens = $null; $parseErrors = $null
[void][Management.Automation.Language.Parser]::ParseFile($wrapper, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count -gt 0) { throw 'PowerShell syntax errors.' }
$global:Calls = [Collections.Generic.List[object]]::new()
$global:FailCopy = $false
function global:scp {
    $global:Calls.Add(@{ kind = 'scp'; arguments = @($args) })
    $global:LASTEXITCODE = if ($global:FailCopy) { 9 } else { 0 }
}
function global:ssh {
    $content = $input | Out-String
    $global:Calls.Add(@{ kind = 'ssh'; arguments = @($args); stdin = $content })
    $global:LASTEXITCODE = 0
}
$temporary = Join-Path ([IO.Path]::GetTempPath()) ('monkeydo wrapper ' + [Guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($temporary)
$commit = 'a' * 40
$archive = Join-Path $temporary 'release with spaces.zip'
try {
    $zip = [IO.Compression.ZipFile]::Open($archive, [IO.Compression.ZipArchiveMode]::Create)
    $entry = $zip.CreateEntry("MonkeyDoWebsiteNewCode-$commit/deploy/monkeydo_deploy.py")
    $writer = [IO.StreamWriter]::new($entry.Open())
    $writer.Write("print('fixture')"); $writer.Dispose()
    $wrapperEntry = $zip.CreateEntry("MonkeyDoWebsiteNewCode-$commit/deploy/Update-MonkeyDo.ps1")
    $writer = [IO.StreamWriter]::new($wrapperEntry.Open())
    $writer.Write([IO.File]::ReadAllText($wrapper)); $writer.Dispose(); $zip.Dispose()
    & $wrapper -Archive $archive -Commit $commit
    if ($global:Calls.Count -ne 2) { throw 'Deploy must upload then invoke SSH once.' }
    if ($global:Calls[0].arguments[-2] -ne $archive) { throw 'Archive path with spaces was not preserved.' }
    $hashStream = [IO.File]::OpenRead($archive)
    $hashAlgorithm = [Security.Cryptography.SHA256]::Create()
    try { $expectedDigest = [BitConverter]::ToString($hashAlgorithm.ComputeHash($hashStream)).Replace('-', '').ToLowerInvariant() } finally { $hashStream.Dispose(); $hashAlgorithm.Dispose() }
    if ($global:Calls[1].arguments -notcontains $expectedDigest) { throw 'Checksum not passed.' }
    if ($global:Calls[1].arguments -notcontains 'StrictHostKeyChecking=yes') { throw 'Host verification missing.' }
    $global:Calls.Clear()
    & $wrapper -Target Functional -Archive $archive -Commit $commit
    if ($global:Calls[0].arguments[-1] -notmatch '/srv/monkeydo-functional/incoming/' -or $global:Calls[1].arguments -notcontains '--target' -or $global:Calls[1].arguments -notcontains 'functional') { throw 'Functional deployment target is not isolated.' }
    if ($global:Calls[1].arguments -contains '--apply-reviewed-batch-two') { throw 'Routine deployment must not opt into schema changes.' }
    $global:Calls.Clear()
    & $wrapper -Target Functional -ApplyReviewedBatchTwo -Archive $archive -Commit $commit
    if ($global:Calls[1].arguments -notcontains '--apply-reviewed-batch-two') { throw 'Explicit reviewed batch-two option was not forwarded.' }
    $global:Calls.Clear()
    $failed = $false
    try { & $wrapper -ApplyReviewedBatchTwo -Archive $archive -Commit $commit } catch { $failed = $true }
    if (-not $failed -or $global:Calls.Count -ne 0) { throw 'Reviewed schema option must reject Design before remote calls.' }
    $global:Calls.Clear()
    & $wrapper -Target Functional -Install -Archive $archive -Commit $commit
    if ($global:Calls[1].stdin -notmatch '/etc/monkeydo/functional.env' -or $global:Calls[1].stdin -notmatch '/var/lib/monkeydo-functional-deploy') { throw 'Functional installer used the design environment.' }
    $global:Calls.Clear()
    & $wrapper -Target Functional -Rollback
    if ($global:Calls[0].arguments -notcontains 'functional' -or $global:Calls[0].arguments[-1] -ne 'rollback') { throw 'Functional rollback target missing.' }
    $global:Calls.Clear()
    & $wrapper -Install -Archive $archive -Commit $commit
    if ($global:Calls.Count -ne 2 -or $global:Calls[1].stdin -notmatch 'hashlib.sha256') { throw 'Installation checksum/bootstrap missing.' }
    if ($global:Calls[1].stdin -match 'systemctl.*restart') { throw 'Installation must not deploy/restart.' }
    $global:Calls.Clear()
    & $wrapper -Rollback
    if ($global:Calls.Count -ne 1 -or $global:Calls[0].arguments[-1] -ne 'rollback') { throw 'Rollback command incorrect.' }
    $global:Calls.Clear()
    & $wrapper -Status
    if ($global:Calls.Count -ne 1 -or $global:Calls[0].arguments[-1] -ne 'status') { throw 'Status command incorrect.' }
    $global:Calls.Clear(); $global:FailCopy = $true
    $failed = $false
    try { & $wrapper -Archive $archive -Commit $commit } catch { $failed = $true }
    if (-not $failed -or $global:Calls.Count -ne 1) { throw 'Failed upload must prevent remote activation.' }
    $global:FailCopy = $false; $global:Calls.Clear()
    $failed = $false
    try { & $wrapper -Archive $archive -Commit 'invalid' } catch { $failed = $true }
    if (-not $failed -or $global:Calls.Count -ne 0) { throw 'Invalid commit must fail locally.' }
    # Execute the documented single-paste bootstrap with local fixture download
    # and mocked transport, keeping every write under this test's temporary folder.
    $handoff = [IO.File]::ReadAllText((Join-Path $root 'docs/OWNER_FEEDBACK_BATCH_TWO_RELEASE.md'))
    $sample = [regex]::Match($handoff, '```powershell\r?\n([\s\S]*?)```').Groups[1].Value
    $sampleErrors = $null; $sampleTokens = $null
    [void][Management.Automation.Language.Parser]::ParseInput($sample, [ref]$sampleTokens, [ref]$sampleErrors)
    if ($sampleErrors.Count -gt 0) { throw 'Published single-command example has PowerShell syntax errors.' }
    $body = [regex]::Replace($sample, '(?s)^powershell[^\n]*\{\r?\n(.*)\}\s*$', '$1')
    $body = $body.Replace('APPROVED_COMMIT', $commit).Replace('$HOME\Downloads', "$temporary\bootstrap\Downloads").Replace('$HOME\MonkeyDoDeploy', "$temporary\bootstrap\MonkeyDoDeploy")
    [void][IO.Directory]::CreateDirectory((Join-Path $temporary 'bootstrap/Downloads'))
    $global:ArchiveFixture = $archive
    function global:Invoke-WebRequest {
        param([string]$Uri, [string]$OutFile, [switch]$UseBasicParsing)
        $global:Calls.Add(@{ kind = 'download'; uri = $Uri })
        Copy-Item -LiteralPath $global:ArchiveFixture -Destination $OutFile
    }
    function global:Unblock-File { param([string]$LiteralPath) }
    $global:Calls.Clear()
    & ([scriptblock]::Create($body))
    if ($global:Calls.Count -ne 5 -or $global:Calls[0].kind -ne 'download' -or $global:Calls[0].uri -notmatch "/$commit`$" -or $global:Calls[-1].arguments -notcontains '--apply-reviewed-batch-two') { throw 'Single-command handoff must download the pinned archive, install, then deploy with the explicit schema option.' }
    Write-Output 'PASS: PowerShell parse, upload/hash, safe install, rollback/status, spaces, failure stop and strict host-key verification. SSH/SCP calls were mocked.'
} finally {
    Remove-Item Function:\scp -ErrorAction SilentlyContinue
    Remove-Item Function:\ssh -ErrorAction SilentlyContinue
    Remove-Item Function:\Invoke-WebRequest -ErrorAction SilentlyContinue
    Remove-Item Function:\Unblock-File -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $temporary -Recurse -Force
}

# The deliberate native-command failure test must not leak its simulated exit
# status into GitHub runner shell epilogues.
$global:LASTEXITCODE = 0
