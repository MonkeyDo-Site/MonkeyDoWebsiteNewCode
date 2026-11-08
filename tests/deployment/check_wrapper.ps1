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
    $writer.Write("print('fixture')"); $writer.Dispose(); $zip.Dispose()
    & $wrapper -Archive $archive -Commit $commit
    if ($global:Calls.Count -ne 2) { throw 'Deploy must upload then invoke SSH once.' }
    if ($global:Calls[0].arguments[-2] -ne $archive) { throw 'Archive path with spaces was not preserved.' }
    $hashStream = [IO.File]::OpenRead($archive)
    $hashAlgorithm = [Security.Cryptography.SHA256]::Create()
    try { $expectedDigest = [BitConverter]::ToString($hashAlgorithm.ComputeHash($hashStream)).Replace('-', '').ToLowerInvariant() } finally { $hashStream.Dispose(); $hashAlgorithm.Dispose() }
    if ($global:Calls[1].arguments -notcontains $expectedDigest) { throw 'Checksum not passed.' }
    if ($global:Calls[1].arguments -notcontains 'StrictHostKeyChecking=yes') { throw 'Host verification missing.' }
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
    Write-Output 'PASS: PowerShell parse, upload/hash, safe install, rollback/status, spaces, failure stop and strict host-key verification. SSH/SCP calls were mocked.'
} finally {
    Remove-Item Function:\scp -ErrorAction SilentlyContinue
    Remove-Item Function:\ssh -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $temporary -Recurse -Force
}

# The deliberate native-command failure test must not leak its simulated exit
# status into GitHub runner shell epilogues.
$global:LASTEXITCODE = 0
