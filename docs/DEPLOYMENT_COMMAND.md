# One-command private-preview updates and rollback

The helper targets only the existing **design-only** service at staging.monkeydoplay.com / 107.170.1.143. It does not deploy production or enable functional staff/booking/payment routes. Preparing/installing this helper does not update the website; a separate explicit deployment command selects an approved release.

## What an update does

1. The Windows wrapper calculates the downloaded ZIP's SHA-256, uploads it with your existing SSH key, and invokes the root-owned server helper. SSH host-key verification stays strict. No personal key, passphrase, GitHub token or preview password is copied into the script.
2. The server checks the staging target/private configuration, service identity, existing gate/HTTPS and exclusive deployment lock. It copies the upload into private root-owned storage, checks its digest and expected commit folder, and rejects unsafe ZIP entries/links, oversized archives and low disk space.
3. It extracts into a separate release, creates that release's own Python virtualenv and installs pinned requirements as the unprivileged deploy user. It collects static files, runs Django checks, verifies design-only routing and checks the migration plan. The old site continues serving during preparation.
4. **Pending migrations stop the update before switching. No migrations are applied by this script.** Schema updates need a separately reviewed compatible migration/backup procedure; reversing code cannot undo a destructive database change.
5. It records a durable recovery checkpoint, briefly stops the preview service, atomically changes the current symlink/systemd override, and starts the selected code with its own virtualenv. It checks local socket responses, password-gate redirects, private headers, static CSS and public HTTPS with certificate verification.
6. If activation or verification fails, it restores the preceding code link and exact service override/Python environment, restarts and verifies it. Existing owner accounts, preview passwords, cookies/secrets and database records are not reset. If restoration cannot be verified it reports failure and retains recovery information; it does not claim success.

The initial manually installed virtualenv is left intact. The first successful managed deployment records the initial release as the rollback target. Subsequent manual rollback can be undone by invoking rollback again. Older releases are not deleted automatically.

## One-time installation on your Windows computer

Use regular Windows PowerShell, not ISE. Download the **approved installer ZIP at its full commit** through your authenticated GitHub browser and save it in Downloads. The helper does not fetch a moving main/latest release or require a repository token on the server.

Replace `INSTALLER_COMMIT` with the exact 40-character commit supplied with the tested release:

```powershell
$monkeydoCommit = 'INSTALLER_COMMIT'
$monkeydoArchive = "$HOME\Downloads\MonkeyDoWebsiteNewCode-$monkeydoCommit.zip"
$monkeydoTools = "$HOME\MonkeyDoDeploy"
New-Item -ItemType Directory -Force -Path $monkeydoTools | Out-Null
Expand-Archive -LiteralPath $monkeydoArchive -DestinationPath "$monkeydoTools\installer-$monkeydoCommit" -Force
Copy-Item "$monkeydoTools\installer-$monkeydoCommit\MonkeyDoWebsiteNewCode-$monkeydoCommit\deploy\Update-MonkeyDo.ps1" "$monkeydoTools\Update-MonkeyDo.ps1"
Unblock-File "$monkeydoTools\Update-MonkeyDo.ps1"
powershell -NoProfile -ExecutionPolicy RemoteSigned -File "$monkeydoTools\Update-MonkeyDo.ps1" -Install -Archive $monkeydoArchive -Commit $monkeydoCommit
```

This uses a process-scoped execution policy, not a permanent machine-policy change. Organizational Group Policy still applies; report an execution-policy error rather than disabling organizational controls.

You may be asked for your existing SSH-key passphrase. Installation copies only the verified helper to `/usr/local/sbin/monkeydo-deploy`, prepares private deployment state/incoming storage, protects the top-level staging/releases directories, and checks the existing site. It does **not** restart the app, change its release, migrate its database, rotate passwords or edit DNS/nginx/TLS. Keep the verification output for the host checkpoint; local tests are not proof of successful installation on the Droplet.

## Routine update: one command after downloading the approved ZIP

Each release handoff must supply the full approved commit and ZIP link. Then run one command, substituting that commit in both places:

```powershell
powershell -NoProfile -ExecutionPolicy RemoteSigned -File "$HOME\MonkeyDoDeploy\Update-MonkeyDo.ps1" -Archive "$HOME\Downloads\MonkeyDoWebsiteNewCode-APPROVED_COMMIT.zip" -Commit APPROVED_COMMIT
```

The wrapper handles SCP, checksum, preparation, switching, checks and automatic code rollback on failure. The SSH-key passphrase may still be requested; it is not stored. Downloading the private GitHub ZIP remains a browser action until separate repository-download credentials or CI deployment access are deliberately configured.

To restore the preceding managed release:

```powershell
powershell -NoProfile -ExecutionPolicy RemoteSigned -File "$HOME\MonkeyDoDeploy\Update-MonkeyDo.ps1" -Rollback
```

To check the active release/private gate/HTTPS without deploying:

```powershell
powershell -NoProfile -ExecutionPolicy RemoteSigned -File "$HOME\MonkeyDoDeploy\Update-MonkeyDo.ps1" -Status
```

Keep V1 fixed during its current design review. Use deployment only at an agreed design checkpoint; backend development continues in separate branches. This helper never automatically chooses or publishes a newer version.

## Failure and recovery limits

- Code/Python rollback is not a database backup or a database rollback. No plaintext database dump or reverse migration is created. Approved encrypted backup/restore work remains separate.
- A killed process or power loss can leave a durable pending checkpoint. The next deploy/rollback command restores and verifies that preceding release first, then asks you to rerun the requested operation. It is not an automatic disaster-recovery/boot service. `-Status` reports pending recovery without changing it.
- A broken certificate, DNS, systemd, disk or host can prevent health verification or restoration. The script reports that condition; manual host repair may still be necessary. It does not change these services or undo out-of-band OS/schema changes.
- Root-owned state and redacted command logs live under `/var/lib/monkeydo-deploy` (private). Release provenance includes commit, upload digest and preparation time. No credentials are printed. Incoming ZIPs/failed candidates/old releases are retained for explicit operator cleanup; no data is deleted to make room.
- Candidate code and dependencies must be approved. Checking a supplied ZIP's hash and commit folder verifies transfer/identity consistency, not that arbitrary code is trustworthy.
- The controller is deliberately limited to the current peer-auth database, hostname, design-only environment and service. Functional staging/schema updates require an extended, separately tested deployment procedure.

## Testing

Python tests cover actual extraction/ZIP guards, config privacy/target rejection, locks, redaction, real Unix HTTP checks, real symlink/systemd-override writes with service commands mocked, staged build failure, restart/health failures, interrupted recovery, manual rollback, rollback failure and durable-state commit failure. PostgreSQL integration creates a pending test migration and runs Django's real `migrate --check`, verifying that its table was never created.

The PowerShell test uses mocked SSH/SCP to exercise installer/hash, paths with spaces, native failure propagation, strict known-host checking, rollback/status and argument validation. It runs locally in official portable PowerShell and in CI on **Windows PowerShell**. It never contacts the actual Droplet. Real service switching/host installation must be smoke-tested through the owner's SSH access before claiming hosted deployment evidence.
