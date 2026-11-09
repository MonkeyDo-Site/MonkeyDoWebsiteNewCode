# Windows PowerShell 5.1+; uses your existing SSH key and verified known-host entry.
[CmdletBinding(DefaultParameterSetName = 'Deploy')]
param(
    [Parameter(Mandatory = $true, ParameterSetName = 'Deploy')]
    [Parameter(Mandatory = $true, ParameterSetName = 'Install')]
    [string]$Archive,
    [Parameter(Mandatory = $true, ParameterSetName = 'Deploy')]
    [Parameter(Mandatory = $true, ParameterSetName = 'Install')]
    [ValidatePattern('^[a-fA-F0-9]{40}$')]
    [string]$Commit,
    [Parameter(Mandatory = $true, ParameterSetName = 'Install')]
    [switch]$Install,
    [Parameter(Mandatory = $true, ParameterSetName = 'Rollback')]
    [switch]$Rollback,
    [Parameter(Mandatory = $true, ParameterSetName = 'Status')]
    [switch]$Status,
    [ValidatePattern('^[a-zA-Z0-9][a-zA-Z0-9.-]*$')]
    [string]$Server = '107.170.1.143',
    [ValidateSet('Design','Functional')]
    [string]$Target = 'Design'
)
$ErrorActionPreference = 'Stop'

function Invoke-CheckedNative {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Program failed (exit $LASTEXITCODE). See the preceding message; do not bypass SSH host verification."
    }
}

function Get-MonkeyDoDigest {
    param([string]$Path)
    $stream = [IO.File]::OpenRead($Path)
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
        return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-', '').ToLowerInvariant()
    } finally { $algorithm.Dispose(); $stream.Dispose() }
}

$sshOptions = @('-o', 'StrictHostKeyChecking=yes')
$targetArguments = @()
if ($Target -eq 'Functional') { $targetArguments = @('--target', 'functional') }
$targetBase = if ($Target -eq 'Functional') { '/srv/monkeydo-functional' } else { '/srv/monkeydo' }
$targetConfiguration = if ($Target -eq 'Functional') { '/etc/monkeydo/functional.env' } else { '/etc/monkeydo/staging.env' }
$targetDomain = 'staging.monkeydoplay.com'
$targetDesignFlag = if ($Target -eq 'Functional') { '0' } else { '1' }
$targetState = if ($Target -eq 'Functional') { '/var/lib/monkeydo-functional-deploy' } else { '/var/lib/monkeydo-deploy' }
if ($Rollback -or $Status) {
    $operation = if ($Rollback) { 'rollback' } else { 'status' }
    Invoke-CheckedNative 'ssh' ($sshOptions + (@("root@$Server", '/usr/local/sbin/monkeydo-deploy') + $targetArguments + @($operation)))
    return
}
$Commit = $Commit.ToLowerInvariant()
$archivePath = (Resolve-Path -LiteralPath $Archive).Path
if (-not (Test-Path -LiteralPath $archivePath -PathType Leaf)) { throw 'Choose the approved downloaded ZIP file.' }
$digest = Get-MonkeyDoDigest $archivePath
$uploadId = [Guid]::NewGuid().ToString('N')

if ($Install) {
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $package = [IO.Compression.ZipFile]::OpenRead($archivePath)
    $temporary = Join-Path ([IO.Path]::GetTempPath()) ("monkeydo-helper-$uploadId.py")
    try {
        $entry = $package.GetEntry("MonkeyDoWebsiteNewCode-$Commit/deploy/monkeydo_deploy.py")
        if ($null -eq $entry) { throw 'The archive does not contain the deployment helper for this commit.' }
        if ($entry.Length -gt 2MB) { throw 'Deployment helper is unexpectedly large.' }
        $inputStream = $entry.Open()
        $outputStream = [IO.File]::Open($temporary, [IO.FileMode]::CreateNew)
        try { $inputStream.CopyTo($outputStream) } finally { $inputStream.Dispose(); $outputStream.Dispose() }
        $helperHash = Get-MonkeyDoDigest $temporary
        $remote = "/usr/local/sbin/monkeydo-deploy-new-$uploadId"
        Invoke-CheckedNative 'scp' ($sshOptions + @($temporary, "root@${Server}:$remote"))
        # Only validated hex values enter this fixed bootstrap. Never downloads
        # code as root, changes the app release, or reads a private SSH key.
        $bootstrap = @"
import hashlib, os, pathlib, grp, subprocess
source = pathlib.Path('$remote')
if source.is_symlink() or source.stat().st_uid != 0:
    raise SystemExit('Unexpected helper ownership/type.')
if hashlib.sha256(source.read_bytes()).hexdigest() != '$helperHash':
    raise SystemExit('Helper checksum mismatch; nothing installed.')
base = pathlib.Path('$targetBase')
configuration = pathlib.Path('$targetConfiguration')
if configuration.is_symlink() or not configuration.is_file() or configuration.stat().st_uid != 0:
    raise SystemExit('Existing protected staging configuration is required.')
settings = dict(line.split('=', 1) for line in configuration.read_text().splitlines() if line and not line.startswith('#'))
if settings.get('APP_ENV') != 'staging' or settings.get('MONKEYDO_DESIGN_ONLY') != '$targetDesignFlag' or settings.get('DJANGO_ALLOWED_HOSTS') != '$targetDomain':
    raise SystemExit('This is not the approved private staging target.')
if not (base / 'staging/current').is_symlink():
    raise SystemExit('Existing pinned staging release is required.')
os.chmod(source, 0o755)
os.replace(source, '/usr/local/sbin/monkeydo-deploy')
for relative in ('releases', 'staging'):
    directory = base / relative
    if directory.is_symlink():
        raise SystemExit('Unexpected directory symlink.')
    directory.mkdir(exist_ok=True)
    os.chown(directory, 0, 0)
    os.chmod(directory, 0o755)
incoming = base / 'incoming'
if incoming.is_symlink():
    raise SystemExit('Unexpected incoming directory symlink.')
incoming.mkdir(exist_ok=True)
os.chown(incoming, 0, grp.getgrnam('monkeydo-deploy').gr_gid)
os.chmod(incoming, 0o770)
state = pathlib.Path('$targetState')
if state.is_symlink():
    raise SystemExit('Unexpected state directory symlink.')
state.mkdir(exist_ok=True)
os.chown(state, 0, 0)
os.chmod(state, 0o700)
print('Helper installed. Website release, database and services were not changed.')
arguments = ['/usr/local/sbin/monkeydo-deploy']
if '$Target' == 'Functional':
    arguments += ['--target', 'functional']
subprocess.run(arguments + ['status'], check=True)
"@
        $bootstrap | & ssh @sshOptions "root@$Server" python3 -
        if ($LASTEXITCODE -ne 0) { throw 'Installation/status verification failed. No application deployment was requested.' }
    } finally {
        $package.Dispose()
        Remove-Item -LiteralPath $temporary -ErrorAction SilentlyContinue
    }
    return
}

$remoteArchive = "$targetBase/incoming/$uploadId.zip"
Invoke-CheckedNative 'scp' ($sshOptions + @($archivePath, "monkeydo-deploy@${Server}:$remoteArchive"))
Invoke-CheckedNative 'ssh' ($sshOptions + (@("root@$Server", '/usr/local/sbin/monkeydo-deploy') + $targetArguments + @('deploy', '--archive', $remoteArchive, '--sha256', $digest, '--commit', $Commit)))
