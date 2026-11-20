# Booking-stage technical setup and recovery

This is an operator configuration document, not the owner's final as-built test
guide. The PR remains draft while the remaining business branches and release
checks are completed. Nothing below means these services, credentials or offsite
recovery points have already been installed on the existing Droplet.

## Existing site and release boundary

Keep the existing functional database, staff accounts, private staging gate,
HTTPS/domain and application secret. No production DNS or live payments. The new
closed schema command accepts only the reviewed 0027–0047 suffix after deployed
0026; the older batch-two/three switches cannot apply this stage. A normal code
deployment continues to run migration checks without applying migrations.

The final reviewed path will use a browser-downloaded commit ZIP and one pasted
PowerShell block, installing the checksum-verified helper and passing the explicit
`-Target Functional -ApplyReviewedBooking` option. Do not use PowerShell's slow
`Invoke-WebRequest` archive download or bypass SSH host verification. The final
commit and download link must be pinned after review; this document does not
instruct deploying the current draft.

The helper retains the old release/environment, takes a root-private local schema
checkpoint, checks resources, applies the closed additive migration plan and
least-privileged grants, verifies HTTPS and installs the six checksum-pinned
worker/timer units. That local checkpoint is **not** the encrypted offsite backup.

Once new integrated/card/waiver/message/backup records exist, older code lacking
the booking-completion capability is refused on rollback. Database rollback cannot
undo a provider charge, sent email or private-file operation. Keep compatible code
or perform an operator-reviewed fix forward; do not manually erase financial
records or drop schema to force an older release to run.

## Private configuration, entered once

Actual values go directly into root-controlled files on the server, never chat,
a Word document, repository, PR, screenshot or deployment archive.

`/etc/monkeydo/functional.env` keeps its existing protected permissions and values.
[deploy/functional.env.example](../deploy/functional.env.example) lists the new
**disabled** flags and private installation slots:

- Banquest **sandbox** source key/PIN, tokenization public `pk_` key and webhook
  HMAC key. Only the public key is placed in the browser; the fixed API/SDK hosts
  are the Banquest sandbox hosts. Saving a card does not charge or place a hold.
- Existing Resend booking sender plus a separate `whsec_` webhook signing secret.
  Register `/integrations/resend/webhook/` for sent/delivered/bounced/complained/
  failed/suppressed events. Register the signed Banquest endpoint at
  `/integrations/banquest/webhook/`. Browser staging passwords do not substitute
  for callback signatures. Authentication-email allowlists remain unchanged.
- Dedicated **private** staging waiver bucket/account with server-side credentials
  scoped to that bucket. Keep public hosting and public object URLs disabled.
- Dedicated private staging backup bucket plus **Get-only** credentials for the
  owner's protected download route. Keep it separate from waiver storage.

The dedicated backup process uses a different OS/DB identity,
`monkeydo-functional-backup`, and a separate root:root 0600
`/etc/monkeydo/backup.env`. The web process must not receive its backup write/delete
credentials. [deploy/backup.env.example](../deploy/backup.env.example) contains
only the command's separate application secret, peer-authenticated backup DB
identity, R2 backup-bucket credentials and public encryption certificate path.
It has no Banquest, waiver-storage, Resend API or private recovery key.

The reviewed installer creates the fixed nonlogin OS service account and
least-privileged peer DB role; it does not change existing users/passwords. Backup
reads cover the database dump; writes are limited to backup status and durable
alert creation. Runtime financial/evidence/history grants exclude schema/admin,
record deletion and updates to immutable facts.

Run `manage.py booking_stage_preflight` under the existing functional runtime
identity after schema preparation. It checks configuration and grants without
sending a charge, email or upload. A pass is not proof of actual provider
acceptance. The usual functional staging preflight still runs too.

## Recovery key and offsite encryption

Generate the RSA recovery key/certificate on a protected owner-controlled recovery
workstation **outside DigitalOcean and R2**. For example, with a reviewed local
OpenSSL installation:

```text
openssl req -x509 -newkey rsa:4096 -keyout monkeydo-recovery-private.pem -out monkeydo-recovery-public.pem -days 3650 -subj /CN=MonkeyDo-Recovery-v1
```

Use a strong local passphrase when prompted. Keep at least two protected private
key copies in separate owner-controlled locations. The owner's BitLocker desktop
can be one protected location; select another protected location without storing
the private key with the archive or emailing it. Only the **public certificate**
goes to `/etc/monkeydo/backup-public.pem`, root-owned and not group/world writable.
Never set a private-key path in server configuration.

The nightly process streams `pg_dump --format=custom` into OpenSSL CMS
AES-256-GCM encryption. Plaintext does not touch the application server's temporary
disk. Temporary ciphertext is private; the private recovery key is not needed.
Each run uses fresh encryption material and a random, nonreused object name.
Upload is conditional; read back and verify full ciphertext hash/size before
retention removes any older recovery point. R2 object metadata carries the hash,
certificate fingerprint and format; the owner can also download an integrity JSON
file. A failed/uncertain upload is not a verified recovery point.

Keep seven newest nightly points and twelve distinct monthly points. The same
physical archive can satisfy both; do not count a duplicate month as another
month. The current single-PUT implementation caps encrypted archives at 4 GiB;
review storage/client design before larger databases. It checks temporary-disk
headroom before dumping. Never expire old verified points after a failed new run.

## Workers and resource checks

The reviewed helper requires at least 1.5 GiB total RAM, 512 MiB currently available
and 3 GiB free release disk before this stage's schema step. It does not buy or
resize infrastructure. If the actual Droplet fails, inspect its current size and
price and present a concrete resize cost before purchasing. Existing owner
preauthorization for a necessary resize does not justify inventing a price.

- Jobs timer: bounded batches of three, five seconds after the prior batch ends.
  Unknown financial POSTs are never replayed. Owner recovery can resume an original
  request only if it has not started, or run read-only reconciliation.
- Waiver retention: hourly bounded batches, only after the two-year signing date.
  Confirm remote deletion, then remove contact/IP/browser details and retain
  minimal signing/history metadata. Paper signing is not electronic evidence.
- Backup timer: nightly 07:00 UTC with jitter, separate UID/config. Missing private
  backup configuration causes a skip; do not call that a working backup.

Units have memory limits, private temporary directories, no new privileges and
read-only system/home protections. The backup role has no payment-source secrets.
Failed/unknown job and mail states stay visible. Backup/upload/retention failure
persists on Dashboard even when its owner email cannot be sent. Marking a backup
issue reviewed preserves its failed history and does not claim a recovery point.

## Monthly desktop copies and restore verification

The owner Backups page and a deduplicated monthly business-email reminder link to
an owner-authenticated encrypted download. Download the archive and its integrity
file. Keep the two newest desktop copies; the owner manually removes older desktop
files. The website cannot choose browser download folders or delete desktop files.

The isolated verifier is [deploy/verify_encrypted_backup.py](../deploy/verify_encrypted_backup.py).
Run it on a protected isolated recovery workstation with local PostgreSQL,
matching client tools, Python/psycopg, OpenSSL and a dedicated local CREATEDB role
that is neither superuser nor CREATEROLE. For example:

```text
python verify_encrypted_backup.py --archive downloaded.cms --manifest downloaded.json --private-key protected-recovery-private.pem --isolated-workstation
```

It checks the encrypted hash, authenticates/decrypts the complete file before any
SQL runs, restores only to a random `monkeydo_restore_check_...` database, checks
required tables/migration history and removes that temporary database. It never
starts Django/workers or replaces the real application database. Temporary
plaintext exists only on that protected isolated workstation and is removed when
the verifier exits. Do not give the runner production/provider credentials.

Record a completed check on the owner Backups page. That record is explicitly an
owner-reported check. An unattended monthly restore runner/key-access arrangement
has **not** been configured; do not claim automated restoration until that separate
protected runner is actually installed and tested. A private key must not be put
on DO/R2 merely to automate a test.

Local developer verification has exercised an encrypted dump of fictional
PostgreSQL fixtures through a real isolated-role restore (62 tables, migration
0047). This is not an R2/owner-key/hosted recovery claim.

## Any future real restoration

Production restore is not implemented by this staging helper. An operator must
preserve the current database, restore and validate an isolated copy, present the
result to the owner and obtain authorization before replacing a real database.

Before connecting any recovered snapshot to the application, stop jobs/backup
workers and set `MONKEYDO_RECOVERY_HOLD=1`. A snapshot can contain Ready jobs whose
external charge/email happened after the backup. The hold blocks new bookings,
card/financial dispatch and email sending; owner read-only provider reconciliation
remains available. Reconcile the recovery interval with provider/message records,
including missing references and partial receipts, **before** lifting the hold.
Do not reinterpret a restored Ready job as proof it was never sent or automatically
replay it. Reapply expired waiver-file retention/deletion state. Preserve actual
external effects and audit; do not reverse them by editing a restored row.
